import re
from types import SimpleNamespace

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.db.models import F, Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.forms import LearningPreferenceForm
from courses.models import (
    Course,
    CourseCategory,
    Exam,
    ExamRecord,
    Instructor,
    LearningPreference,
    LearningRecord,
)
from learning_system.oss_signed_urls import sign_oss_get_url
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


@login_required
def course_catalog(request):
    """全部课程列表（公开），支持左侧目录与 ?category= 筛选。"""
    qs = Course.objects.select_related("catalog_category").order_by("-created_at")
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
    course = get_object_or_404(Course, pk=pk)
    rec, created = LearningRecord.objects.get_or_create(
        employee=request.user,
        course=course,
        defaults={"progress_percentage": 100, "is_completed": True},
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
    return redirect("courses:course_detail", pk=pk)


@login_required
def course_detail(request, pk):
    """课程详情：视频播放与简介（登录可访问，点击即计入浏览量）。"""
    course = get_object_or_404(Course, pk=pk)
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

    return render(
        request,
        "courses/course_detail.html",
        {
            "course": course,
            "learning_record": learning_record,
            "youtube_embed_url": _youtube_embed_url(course.video_url or ""),
            "course_video_src": course_video_src,
            "required_deadline_state": required_deadline_state,
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
