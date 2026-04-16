import json
import re
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import DatabaseError, transaction
from django.db.models import Count, F, Prefetch, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.forms import LearningPreferenceForm
from courses.models import (
    Course,
    CourseCategory,
    CourseFocusAccum,
    Exam,
    ExamFocusSession,
    ExamRecord,
    Instructor,
    LearningPreference,
    LearningRecord,
)
from learning_system.oss_signed_urls import sign_oss_get_url
from shop.models import Training
from users.models import LeaderboardConfig


def _course_category_roots():
    return (
        CourseCategory.objects.filter(parent__isnull=True)
        .prefetch_related(
            Prefetch(
                "children",
                queryset=CourseCategory.objects.order_by("sort_order", "id"),
            )
        )
        .order_by("sort_order", "id")
    )

User = get_user_model()

_EXAM_SCHEDULE_LABELS = {
    "pending": "待开始",
    "ongoing": "进行中",
    "done": "已结束",
}


def _exam_passes_result_filter(exam, rec, pass_status: str) -> bool:
    if not pass_status:
        return True
    if pass_status == "none":
        return rec is None or rec.score is None
    if pass_status == "passed":
        return rec is not None and rec.score is not None and rec.score >= exam.pass_score
    if pass_status == "failed":
        return rec is not None and rec.score is not None and rec.score < exam.pass_score
    return True


def _exam_passes_schedule_filter(exam, pending_filter: str) -> bool:
    if not pending_filter:
        return True
    return exam.schedule_status() == pending_filter


def _exam_result_summary(exam, rec) -> str:
    if rec is None or rec.score is None:
        return "暂无成绩"
    if rec.score >= exam.pass_score:
        return f"{rec.score} 分 · 已通过"
    return f"{rec.score} 分 · 未通过"


def _youtube_embed_url(url: str) -> str | None:
    if not url:
        return None
    m = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})", url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    return None


def _course_has_playable_video(course: Course) -> bool:
    """是否存在可播放的视频区域（上传、直链或 YouTube 等）。"""
    if course.content_kind != Course.ContentKind.VIDEO:
        return False
    if course.video_file:
        return True
    return bool((course.video_url or "").strip())


def _instructor_courses_summary(instructor: Instructor):
    """讲师页：按课程主讲讲师归类，展示讲过的课与级别。"""
    related_courses = list(
        Course.objects.filter(instructor=instructor)
        .order_by("-created_at")
        .select_related("instructor")
    )
    course_rows = [
        {
            "course": course,
            "level": course.course_type,
            "level_label": course.get_course_type_display(),
            "content_label": course.get_content_kind_display(),
            "reward_points": course.reward_points,
        }
        for course in related_courses
    ]

    training_rows = []
    if instructor.name:
        related_trainings = (
            Training.objects.filter(instructor_name__icontains=instructor.name)
            .order_by("-created_at")
            .distinct()
        )
        training_rows = [
            {"training": t, "category_label": t.get_applications_category_display()}
            for t in related_trainings
        ]

    course_total = len(course_rows)
    required_count = sum(1 for row in course_rows if row["level"] == Course.CourseType.REQUIRED)
    elective_count = course_total - required_count

    return course_rows, training_rows, {
        "course_total": course_total,
        "required_count": required_count,
        "elective_count": elective_count,
    }


def _required_video_must_ack_playthrough(course: Course) -> bool:
    """必修 + 视频 + 已有视频源：须先确认完整观看，才允许标记学完。"""
    return (
        course.course_type == Course.CourseType.REQUIRED
        and course.content_kind == Course.ContentKind.VIDEO
        and _course_has_playable_video(course)
    )


@login_required
def course_catalog(request):
    """全部课程列表（公开），支持左侧目录与 ?category= 筛选。"""
    qs = Course.objects.select_related("catalog_category", "instructor", "instructor__employee").order_by("-created_at")
    search_q = request.GET.get("q", "").strip()
    raw_cat = request.GET.get("category", "").strip()

    if raw_cat.isdigit():
        cat = CourseCategory.objects.filter(pk=int(raw_cat)).first()
        if cat:
            if cat.parent_id:
                qs = qs.filter(catalog_category_id=cat.pk)
            else:
                sub_ids = cat.children.values_list("pk", flat=True)
                qs = qs.filter(catalog_category_id__in=sub_ids)

    if search_q:
        qs = qs.filter(name__icontains=search_q)

    active_category_id = int(raw_cat) if raw_cat.isdigit() else None
    courses = list(qs[:200])
    return render(
        request,
        "courses/course_catalog.html",
        {
            "courses": courses,
            "search_q": search_q,
            "course_category_roots": _course_category_roots(),
            "active_category_id": active_category_id,
        },
    )


@login_required
@require_POST
def course_mark_complete(request, pk):
    """学员标记学完：写入学习记录并触发完课积分（若首次且未触达每日上限）。"""
    course = get_object_or_404(Course.objects.select_related("catalog_category", "instructor", "instructor__employee"), pk=pk)
    if course.focus_monitor_enabled and course.focus_max_blurs is not None:
        if course.focus_on_course_exceed == Course.FocusCourseAction.BLOCK_COMPLETE:
            acc = CourseFocusAccum.objects.filter(employee=request.user, course=course).first()
            if acc and acc.blur_count >= course.focus_max_blurs:
                messages.error(
                    request,
                    f"检测到离开页面次数较多（≥{course.focus_max_blurs} 次），暂不可标记学完。请关闭其他标签页后重新学习本页，或联系管理员。",
                )
                return redirect("courses:course_detail", pk=pk)

    from_video_end = request.POST.get("from_video_end") == "1"
    needs_video_ack = _required_video_must_ack_playthrough(course)
    existing = LearningRecord.objects.filter(employee=request.user, course=course).first()
    ack_ok = (existing and existing.video_playthrough_acknowledged) or from_video_end
    if needs_video_ack and not ack_ok:
        messages.error(
            request,
            "本课程为必修视频课，请先完整观看视频后再标记学完。"
            "本地或直链视频请播放到结尾（系统将自动尝试记录）；"
            "若为页面内嵌视频（如 YouTube），请先点击视频区域下方的「我已完整观看本视频」再标记学完。",
        )
        return redirect("courses:course_detail", pk=pk)

    defaults = {"progress_percentage": 100, "is_completed": True}
    if needs_video_ack and from_video_end:
        defaults["video_playthrough_acknowledged"] = True

    rec, created = LearningRecord.objects.get_or_create(
        employee=request.user,
        course=course,
        defaults=defaults,
    )
    pref = LearningPreference.objects.filter(employee_id=request.user.pk).first()
    verbose = pref is None or pref.verbose_completion_message

    if not created:
        if rec.is_completed:
            messages.info(
                request,
                "您已标记学完该课程。" if verbose else "已标记学完。",
            )
            return redirect("courses:course_detail", pk=pk)
        if from_video_end:
            rec.video_playthrough_acknowledged = True
        rec.progress_percentage = 100
        rec.is_completed = True
        rec.save()

    granted = int(getattr(rec, "_points_granted_on_complete", 0) or 0)
    reason = getattr(rec, "_points_grant_reason", "") or ""

    if not verbose:
        if reason == "daily_cap":
            messages.warning(request, "今日学习类积分已达每日上限，本次未再发放积分。")
        elif reason == "already":
            messages.info(request, "已记录为学完。")
        else:
            messages.success(request, "已记录为学完。")
    elif granted > 0:
        messages.success(request, f"已记录为学完，获得 {granted} 积分。")
    elif reason == "daily_cap":
        messages.warning(request, "今日学习类积分已达每日上限，本次未再发放积分。")
    elif reason == "already":
        messages.info(request, "已记录为学完（该课程积分此前已发放）。")
    else:
        messages.success(request, "已记录为学完。")
    CourseFocusAccum.objects.filter(employee=request.user, course=course).delete()
    return redirect("courses:course_detail", pk=pk)


@login_required
@require_POST
def video_playthrough_ack(request, pk):
    """嵌入视频（如 YouTube）无法由本站检测播放结束，由学员确认已完整观看后再允许标记必修学完。"""
    course = get_object_or_404(Course, pk=pk)
    if not _required_video_must_ack_playthrough(course):
        messages.error(request, "该课程不需要此观看确认。")
        return redirect("courses:course_detail", pk=pk)
    rec, _ = LearningRecord.objects.get_or_create(
        employee=request.user,
        course=course,
        defaults={"progress_percentage": 0, "is_completed": False},
    )
    rec.video_playthrough_acknowledged = True
    rec.save(update_fields=["video_playthrough_acknowledged", "updated_at"])
    messages.success(request, "已记录观看确认，您可点击下方「标记为已学完」。")
    return redirect("courses:course_detail", pk=pk)


def _focus_warn_message(count: int, kind: str) -> str:
    if kind == "exam":
        return f"您已离开本页 {count} 次。考试期间请尽量保持本页打开，频繁切屏可能被记为违规交卷。"
    return f"您已离开学习页面 {count} 次，请尽量保持在本页完成学习。"


def _should_show_focus_warn(blur_count: int, warn_after: int, warn_every: int) -> bool:
    if blur_count < warn_after:
        return False
    return (blur_count - warn_after) % warn_every == 0


@login_required
@require_POST
def focus_blur_report(request):
    """前端上报一次有效「切屏/失焦」事件，返回累计次数与是否提示。"""
    try:
        body = json.loads(request.body.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid json"}, status=400)

    scope = body.get("scope")
    if scope == "course":
        course_id = body.get("course_id")
        if not isinstance(course_id, int) and not (isinstance(course_id, str) and str(course_id).isdigit()):
            return JsonResponse({"error": "course_id required"}, status=400)
        course = get_object_or_404(Course, pk=int(course_id))
        if not course.focus_monitor_enabled:
            return JsonResponse({"blur_count": 0, "toast": ""})

        throttle_key = f"focusblur:{request.user.pk}:c:{course.pk}"
        if cache.get(throttle_key):
            acc = CourseFocusAccum.objects.filter(employee=request.user, course=course).first()
            return JsonResponse({"blur_count": acc.blur_count if acc else 0, "toast": ""})
        cache.set(throttle_key, 1, timeout=1)

        with transaction.atomic():
            accum, _ = CourseFocusAccum.objects.select_for_update().get_or_create(
                employee=request.user,
                course=course,
                defaults={"blur_count": 0},
            )
            CourseFocusAccum.objects.filter(pk=accum.pk).update(blur_count=F("blur_count") + 1)
            accum.refresh_from_db(fields=["blur_count"])

        c = accum.blur_count
        toast = ""
        if _should_show_focus_warn(c, course.focus_warn_after_blurs, course.focus_warn_every):
            toast = _focus_warn_message(c, "course")
        out = {"blur_count": c, "toast": toast, "toast_level": "warning"}
        if (
            course.focus_max_blurs is not None
            and c >= course.focus_max_blurs
            and course.focus_on_course_exceed == Course.FocusCourseAction.BLOCK_COMPLETE
        ):
            out["toast"] = (
                f"已超过允许离开次数（{course.focus_max_blurs} 次），将无法标记学完，"
                "如需申诉请联系管理员。"
            )
            out["toast_level"] = "error"
        return JsonResponse(out)

    if scope == "exam":
        sid = body.get("session_id")
        if not sid:
            return JsonResponse({"error": "session_id required"}, status=400)
        throttle_key = f"focusblur:{request.user.pk}:e:{sid}"
        if cache.get(throttle_key):
            sess = ExamFocusSession.objects.filter(pk=sid, employee=request.user).first()
            bc = sess.blur_count if sess else 0
            return JsonResponse({"blur_count": bc, "toast": ""})
        cache.set(throttle_key, 1, timeout=1)

        with transaction.atomic():
            session = (
                ExamFocusSession.objects.select_for_update()
                .filter(pk=sid, employee=request.user, force_ended=False)
                .select_related("exam")
                .first()
            )
            if not session:
                return JsonResponse({"error": "session not found"}, status=404)
            exam = session.exam
            if not exam.focus_monitor_enabled:
                return JsonResponse({"blur_count": 0, "toast": ""})

            ExamFocusSession.objects.filter(pk=session.pk).update(blur_count=F("blur_count") + 1)
            session.refresh_from_db(fields=["blur_count"])

        c = session.blur_count
        toast = ""
        if _should_show_focus_warn(c, exam.focus_warn_after_blurs, exam.focus_warn_every):
            toast = _focus_warn_message(c, "exam")

        force_redirect = None
        toast_level_out = "warning"
        if (
            exam.focus_max_blurs is not None
            and c >= exam.focus_max_blurs
            and exam.focus_on_exam_exceed == Exam.FocusExamAction.FORCE_SUBMIT_ZERO
        ):
            with transaction.atomic():
                session2 = ExamFocusSession.objects.select_for_update().filter(pk=sid).first()
                if session2 and not session2.force_ended:
                    rec = ExamRecord.objects.filter(employee=request.user, exam=exam).first()
                    if rec and rec.score is not None and rec.score >= exam.pass_score:
                        session2.force_ended = True
                        session2.save(update_fields=["force_ended"])
                        toast = "您已通过该考试，切屏监测已结束。"
                        toast_level_out = "success"
                    else:
                        session2.force_ended = True
                        session2.save(update_fields=["force_ended"])
                        if rec is None or rec.score is None or rec.score < exam.pass_score:
                            if rec:
                                rec.score = 0
                                rec.submitted_at = timezone.now()
                                rec.focus_forced_zero = True
                                rec.focus_blur_count_reported = c
                                rec.save(
                                    update_fields=[
                                        "score",
                                        "submitted_at",
                                        "focus_forced_zero",
                                        "focus_blur_count_reported",
                                    ]
                                )
                            else:
                                ExamRecord.objects.create(
                                    employee=request.user,
                                    exam=exam,
                                    score=0,
                                    submitted_at=timezone.now(),
                                    focus_forced_zero=True,
                                    focus_blur_count_reported=c,
                                )
                        toast = (
                            f"离开页面次数达到 {exam.focus_max_blurs} 次，系统已按规则记 0 分交卷。"
                            "您可在测练中心查看成绩。"
                        )
                        force_redirect = "/courses/my/exams/?mode=exam&focus_ended=1"
                        toast_level_out = "error"

        return JsonResponse(
            {
                "blur_count": c,
                "toast": toast,
                "toast_level": toast_level_out,
                "force_redirect": force_redirect or "",
            }
        )

    return JsonResponse({"error": "invalid scope"}, status=400)


@login_required
def exam_launch(request, pk):
    """有切屏监测的考试：经本页再打开外链，便于保留本标签计次。"""
    exam = get_object_or_404(Exam, pk=pk)
    if not exam.entry_url:
        messages.error(request, "该考试未配置答题入口链接。")
        return redirect("courses:my_exams")
    if not exam.focus_monitor_enabled:
        return redirect(exam.entry_url)
    session = ExamFocusSession.objects.create(exam=exam, employee=request.user)
    return render(
        request,
        "courses/exam_launch.html",
        {
            "exam": exam,
            "focus_session": session,
        },
    )


@login_required
def instructor_detail(request, pk):
    """讲师详情：展示讲师讲过的课程与关联培训。"""
    instructor = get_object_or_404(Instructor.objects.select_related("employee"), pk=pk)
    if not Course.objects.filter(instructor=instructor).exists():
        raise Http404("该讲师暂无关联课程")
    course_rows, training_rows, stats = _instructor_courses_summary(instructor)
    return render(
        request,
        "courses/instructor_detail.html",
        {
            "instructor": instructor,
            "course_rows": course_rows,
            "training_rows": training_rows,
            "stats": stats,
        },
    )


@login_required
def course_detail(request, pk):
    """课程详情：视频播放与简介（登录可访问，点击即计入浏览量）。"""
    course = get_object_or_404(Course.objects.select_related("catalog_category", "instructor", "instructor__employee"), pk=pk)
    Course.objects.filter(pk=pk).update(view_count=F("view_count") + 1)
    course.refresh_from_db(fields=["view_count"])

    learning_record = None
    if request.user.is_authenticated:
        learning_record = LearningRecord.objects.filter(
            employee=request.user, course_id=pk
        ).first()

    course_video_src = None
    if course.video_file:
        if settings.USE_OSS_MEDIA:
            course_video_src = sign_oss_get_url(course.video_file.name)
        else:
            course_video_src = course.video_file.url

    required_deadline_state = None
    if course.course_type == Course.CourseType.REQUIRED:
        done = bool(learning_record and learning_record.is_completed)
        required_deadline_state = course.get_required_deadline_state(is_completed=done)

    focus_monitor_config = None
    if request.user.is_authenticated and course.focus_monitor_enabled:
        focus_monitor_config = {
            "scope": "course",
            "course_id": course.pk,
            "grace_seconds": course.focus_grace_seconds,
            "min_hidden_ms": course.focus_min_hidden_ms,
            "report_url": reverse("courses:focus_blur_report"),
        }

    youtube_embed_url = _youtube_embed_url(course.video_url or "")
    # 视频课：只要有切屏监测就显示「观看前提示」遮罩（含尚未上传视频占位区），不依赖是否已有可播放地址
    focus_video_gate = bool(
        focus_monitor_config and course.content_kind == Course.ContentKind.VIDEO
    )
    focus_pre_video = None
    if focus_video_gate:
        blocks = (
            course.focus_on_course_exceed == Course.FocusCourseAction.BLOCK_COMPLETE
        )
        focus_pre_video = {
            "max_blurs": course.focus_max_blurs,
            "blocks_complete": blocks,
            "grace_seconds": course.focus_grace_seconds,
            "min_hidden_ms": course.focus_min_hidden_ms,
        }

    required_video_need_ack = _required_video_must_ack_playthrough(course)
    video_playthrough_ack_done = bool(
        learning_record and learning_record.video_playthrough_acknowledged
    )

    return render(
        request,
        "courses/course_detail.html",
        {
            "course": course,
            "course_instructor": course.instructor,
            "learning_record": learning_record,
            "youtube_embed_url": youtube_embed_url,
            "course_video_src": course_video_src,
            "required_deadline_state": required_deadline_state,
            "focus_monitor_config": focus_monitor_config,
            "focus_video_gate": focus_video_gate,
            "focus_pre_video": focus_pre_video,
            "required_video_need_ack": required_video_need_ack,
            "video_playthrough_ack_done": video_playthrough_ack_done,
        },
    )


def get_dashboard_context(request):
    """首页与「知识殿堂」共用的榜单、课程与学习记录数据。"""
    lb_cfg = LeaderboardConfig.get_solo()
    qs = User.objects.all().order_by("-points_balance", "emp_id")
    if lb_cfg.exclude_staff:
        qs = qs.filter(is_staff=False, is_superuser=False)
    n = min(int(lb_cfg.home_rank_count), 50)
    leaderboard_list = list(qs[:n])
    mid = (len(leaderboard_list) + 1) // 2
    leaderboard_first = leaderboard_list[:mid]
    leaderboard_second = leaderboard_list[mid:]
    sidebar_n = min(int(lb_cfg.sidebar_rank_count), len(leaderboard_list))
    leaderboard_sidebar = leaderboard_list[:sidebar_n]

    courses_recommended = Course.objects.filter(is_recommended=True).order_by("-created_at")[
        :8
    ]
    if not courses_recommended:
        courses_recommended = Course.objects.order_by("-created_at")[:8]

    courses_latest = Course.objects.order_by("-created_at")[:8]
    courses_hottest = (
        Course.objects.filter(exclude_from_hot_ranking=False)
        .order_by("-view_count", "-created_at")[:8]
    )

    instructors = list(
        Instructor.objects.filter(is_published=True)
        .annotate(course_count=Count("courses", distinct=True))
        .filter(course_count__gt=0)
        .select_related("employee")
        .order_by("sort_order", "id")[:8]
    )

    learning_history = []
    learning_task_rows = []
    if request.user.is_authenticated:
        learning_history = list(
            LearningRecord.objects.filter(employee=request.user)
            .select_related("course")
            .order_by("-updated_at")[:6]
        )
        done_ids = LearningRecord.objects.filter(
            employee=request.user, is_completed=True
        ).values_list("course_id", flat=True)
        raw_required = list(
            Course.objects.filter(course_type=Course.CourseType.REQUIRED).exclude(
                id__in=done_ids
            )
        )
        for c in raw_required:
            st = c.get_required_deadline_state(is_completed=False)
            if st is not None:
                learning_task_rows.append(
                    {"task_type": "course", "course": c, "deadline_state": st}
                )

        for ex in Exam.objects.filter(kind=Exam.Kind.EXAM, is_published=True).order_by(
            "-created_at"
        )[:80]:
            st = ex.get_learning_task_state(request.user)
            if st is not None:
                learning_task_rows.append(
                    {"task_type": "exam", "exam": ex, "deadline_state": st}
                )

        def _task_sort_key(row):
            st = row["deadline_state"]
            ts = st.get("sort_ts")
            tsv = ts.timestamp() if ts is not None else 1e30
            return (st["sort_priority"], tsv)

        learning_task_rows.sort(key=_task_sort_key)
        learning_task_rows = learning_task_rows[:12]

    return {
        "leaderboard": leaderboard_list,
        "leaderboard_settings": lb_cfg,
        "leaderboard_first": leaderboard_first,
        "leaderboard_second": leaderboard_second,
        "leaderboard_split_at": len(leaderboard_first),
        "leaderboard_sidebar": leaderboard_sidebar,
        "courses_recommended": courses_recommended,
        "courses_latest": courses_latest,
        "courses_hottest": courses_hottest,
        "course_category_roots": _course_category_roots(),
        "instructors": instructors,
        "learning_history": learning_history,
        "learning_task_rows": learning_task_rows,
    }


def get_public_home_context(request):
    """未登录首页：仅课程列表与目录导航，不查积分榜与讲师。"""
    courses_recommended = Course.objects.filter(is_recommended=True).order_by("-created_at")[:8]
    if not courses_recommended:
        courses_recommended = Course.objects.order_by("-created_at")[:8]
    courses_latest = Course.objects.order_by("-created_at")[:8]
    courses_hottest = (
        Course.objects.filter(exclude_from_hot_ranking=False)
        .order_by("-view_count", "-created_at")[:8]
    )
    return {
        "leaderboard": [],
        "leaderboard_settings": SimpleNamespace(time_range_label="", display_footnote=""),
        "leaderboard_first": [],
        "leaderboard_second": [],
        "leaderboard_split_at": 0,
        "leaderboard_sidebar": [],
        "courses_recommended": list(courses_recommended),
        "courses_latest": list(courses_latest),
        "courses_hottest": list(courses_hottest),
        "course_category_roots": _course_category_roots(),
        "instructors": [],
        "learning_history": [],
        "learning_task_rows": [],
    }


def _my_learning_sidebar_stats(user):
    """「知识殿堂」侧栏三项：今日学习类积分、合格考试数、已完课累计时长（分钟）。"""
    from shop.models import PointsLedger
    from shop.points_awards import shanghai_day_bounds, shanghai_today

    d = shanghai_today()
    start, end = shanghai_day_bounds(d)
    today_learning_points = (
        PointsLedger.objects.filter(
            employee=user,
            source__in=(
                PointsLedger.Source.DAILY_LOGIN,
                PointsLedger.Source.COURSE_COMPLETE,
            ),
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(s=Sum("amount"))["s"]
        or 0
    )

    certificates_count = ExamRecord.objects.filter(
        employee=user,
        score__isnull=False,
    ).filter(score__gte=F("exam__pass_score")).count()

    total_study_minutes = (
        LearningRecord.objects.filter(employee=user, is_completed=True).aggregate(
            s=Sum("course__duration_minutes")
        )["s"]
        or 0
    )

    return {
        "today_learning_points": int(today_learning_points),
        "certificates_count": certificates_count,
        "total_study_minutes": int(total_study_minutes),
    }


def _my_learning_hottest_blocks(ctx):
    """按前三个一级目录拆分最热课程；无目录或各类均无课时回退为单列「最热课程」。"""
    roots = list(ctx["course_category_roots"])[:3]
    base = Course.objects.filter(exclude_from_hot_ranking=False).select_related(
        "catalog_category"
    )
    if not base.exists():
        base = Course.objects.all().select_related("catalog_category")

    blocks = []
    for root in roots:
        sub_ids = list(root.children.values_list("pk", flat=True))
        if sub_ids:
            qs = base.filter(catalog_category_id__in=sub_ids).order_by(
                "-view_count", "-created_at"
            )[:4]
        else:
            qs = base.filter(catalog_category_id=root.pk).order_by(
                "-view_count", "-created_at"
            )[:4]
        blocks.append({"category": root, "courses": list(qs)})

    if not any(b["courses"] for b in blocks):
        hot = list(ctx["courses_hottest"])[:9]
        if not hot:
            hot = list(
                Course.objects.order_by("-view_count", "-created_at")
                .select_related("catalog_category")[:9]
            )
        return [
            {
                "category": None,
                "title": "最热课程",
                "courses": hot,
            }
        ]
    return blocks


@login_required
def my_learning(request):
    ctx = get_dashboard_context(request)
    ctx["courses_hottest_blocks"] = _my_learning_hottest_blocks(ctx)
    ctx.update(_my_learning_sidebar_stats(request.user))
    return render(request, "courses/my_learning.html", ctx)


@login_required
@require_POST
def my_profile_update(request):
    """「知识殿堂」侧栏：更新头像与签名档。"""
    employee = request.user
    employee.signature = (request.POST.get("signature") or "").strip()[:500]

    if request.POST.get("clear_avatar"):
        if employee.avatar:
            employee.avatar.delete(save=False)
        employee.avatar = None
    elif request.FILES.get("avatar"):
        employee.avatar = request.FILES["avatar"]

    try:
        employee.save()
    except DatabaseError as exc:
        err = str(exc)
        if "1366" in err or "Incorrect string value" in err:
            messages.error(
                request,
                "签名或资料中含特殊符号/表情，当前数据库该表字符集尚未支持。请暂用普通文字，或联系管理员执行 "
                "`python manage.py migrate`（含 users 与 courses 的 utf8mb4 迁移）后重试。",
            )
            return redirect("courses:my_learning")
        raise

    employee.refresh_from_db()
    login(
        request,
        employee,
        backend=settings.AUTHENTICATION_BACKENDS[0],
    )
    messages.success(request, "头像与签名档已保存。")
    return redirect("courses:my_learning")


def _learning_section_context(request, *, primary: str):
    """主 Tab：training / external / projects；子 Tab：joined=我参与的，applied=我申请的。"""
    role = request.GET.get("role", "joined")
    if role not in ("joined", "applied"):
        role = "joined"
    return {
        "learning_primary": primary,
        "learning_role": role,
        "search_q": request.GET.get("q", "").strip(),
        "status_filter": request.GET.get("status", ""),
    }


@login_required
def my_training(request):
    ctx = _learning_section_context(request, primary="training")
    req_courses = list(
        Course.objects.filter(course_type=Course.CourseType.REQUIRED).order_by("-created_at")[:80]
    )
    req_ids = [c.pk for c in req_courses]
    rec_map = {}
    if req_ids:
        rec_map = {
            r.course_id: r
            for r in LearningRecord.objects.filter(employee=request.user, course_id__in=req_ids)
        }
    required_course_rows = []
    for c in req_courses:
        rec = rec_map.get(c.pk)
        done = bool(rec and rec.is_completed)
        required_course_rows.append(
            {
                "course": c,
                "record": rec,
                "deadline_state": c.get_required_deadline_state(is_completed=done),
            }
        )
    ctx.update(
        {
            "page_title": "我的培训",
            "empty_title": "暂无线下/活动培训报名记录",
            "empty_hint": "在「活动广场」报名通过后，将显示在「我参与的」列表。上方「必修课程」为系统指派在线课。",
            "required_course_rows": required_course_rows,
        }
    )
    return render(request, "courses/learning_section.html", ctx)


@login_required
def my_external(request):
    ctx = _learning_section_context(request, primary="external")
    ctx.update(
        {
            "page_title": "我的外训",
            "empty_title": "暂无外训项目，去其他模块转转吧",
            "empty_hint": "",
        }
    )
    return render(request, "courses/learning_section.html", ctx)


@login_required
def my_projects(request):
    ctx = _learning_section_context(request, primary="projects")
    ctx.update(
        {
            "page_title": "项目",
            "empty_title": "暂无项目，去其他模块转转吧",
            "empty_hint": "立项与任务将在此处汇总。",
        }
    )
    return render(request, "courses/learning_section.html", ctx)


@login_required
def my_exams(request):
    """测练中心：考试 / 练习（数据来自后台「考试与练习」）。"""
    if request.GET.get("focus_ended"):
        messages.warning(
            request,
            "因离开页面次数达到上限，本次考试已按规则自动交卷（0 分）。如有疑问请联系管理员。",
        )
    mode = request.GET.get("mode", "exam")
    if mode not in ("exam", "practice"):
        mode = "exam"
    sort_key = request.GET.get("sort", "default")
    if sort_key not in ("default", "start", "end"):
        sort_key = "default"
    pass_status = request.GET.get("pass_status", "")
    pending_filter = request.GET.get("pending", "")
    search_q = request.GET.get("q", "").strip()

    kind = Exam.Kind.EXAM if mode == "exam" else Exam.Kind.PRACTICE
    qs = Exam.objects.filter(kind=kind, is_published=True)
    if search_q:
        qs = qs.filter(title__icontains=search_q)

    if sort_key == "start":
        qs = qs.order_by(F("starts_at").asc(nulls_last=True), "-id")
    elif sort_key == "end":
        qs = qs.order_by(F("ends_at").asc(nulls_last=True), "-id")
    else:
        qs = qs.order_by("-created_at")

    exams_list = list(qs)
    exam_ids = [e.id for e in exams_list]
    rec_map = {
        r.exam_id: r
        for r in ExamRecord.objects.filter(employee=request.user, exam_id__in=exam_ids)
    }

    exam_rows = []
    for exam in exams_list:
        rec = rec_map.get(exam.id)
        if not _exam_passes_result_filter(exam, rec, pass_status):
            continue
        if not _exam_passes_schedule_filter(exam, pending_filter):
            continue
        sched = exam.schedule_status()
        exam_rows.append(
            {
                "exam": exam,
                "record": rec,
                "schedule_label": _EXAM_SCHEDULE_LABELS[sched],
                "result_summary": _exam_result_summary(exam, rec),
            }
        )

    return render(
        request,
        "courses/my_exams.html",
        {
            "exam_mode": mode,
            "pass_status": pass_status,
            "pending_filter": pending_filter,
            "search_q": search_q,
            "sort_key": sort_key,
            "exam_rows": exam_rows,
        },
    )


@login_required
@require_POST
def add_to_plan(request, pk):
    """将课程加入自学计划：创建学习记录（进度 0），已存在则提示。"""
    course = get_object_or_404(Course, pk=pk)
    rec, created = LearningRecord.objects.get_or_create(
        employee=request.user,
        course=course,
        defaults={"progress_percentage": 0, "is_completed": False},
    )
    if created:
        messages.success(request, f"已将《{course.name}》加入自学计划。")
    else:
        messages.info(request, f"《{course.name}》已在你的自学计划中。")
    next_url = (request.POST.get("next") or "").strip()
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    ref = request.META.get("HTTP_REFERER")
    if ref:
        return redirect(ref)
    return redirect("courses:my_courses")


@login_required
def my_courses(request):
    """自学计划：当前用户的学习记录（课程）。"""
    tab = request.GET.get("filter", "all")
    if tab not in ("all", "learning", "completed"):
        tab = "learning"
    search_q = request.GET.get("q", "").strip()
    recommended_only = request.GET.get("recommended") == "1"

    records = LearningRecord.objects.none()
    course_count = 0
    if request.user.is_authenticated:
        records = (
            LearningRecord.objects.filter(employee=request.user)
            .select_related("course")
            .order_by("-updated_at")
        )
        if tab == "learning":
            records = records.filter(is_completed=False)
        elif tab == "completed":
            records = records.filter(is_completed=True)
        if search_q:
            records = records.filter(course__name__icontains=search_q)
        if recommended_only:
            records = records.filter(course__is_recommended=True)
        course_count = records.count()
    
    return render(
        request,
        "courses/my_courses.html",
        {
            "course_filter": tab,
            "search_q": search_q,
            "recommended_only": recommended_only,
            "learning_records": records,
            "course_count": course_count,
        },
    )


@login_required
def learning_settings(request):
    """学习提醒、完课提示、积分通知等偏好设置。"""
    pref, _ = LearningPreference.objects.get_or_create(employee=request.user)
    if request.method == "POST":
        form = LearningPreferenceForm(request.POST, instance=pref)
        if form.is_valid():
            form.save()
            messages.success(request, "学习设置已保存。")
            return redirect("courses:learning_settings")
    else:
        form = LearningPreferenceForm(instance=pref)
    return render(
        request,
        "courses/learning_settings.html",
        {
            "form": form,
            "pref": pref,
        },
    )


@login_required
def my_applications_redirect(request):
    """「知识殿堂 → 我的报名」入口：统一到活动广场的报名列表页。"""
    return redirect("shop:my_applications")
