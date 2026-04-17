from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from datetime import timedelta

from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import EmployeeAuthenticationForm, EmployeeRegistrationForm, StaffRegistrationForm
from .models import Employee, Notification, NotificationRead


class EmployeeLoginView(LoginView):
    template_name = "registration/login.html"
    authentication_form = EmployeeAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        import logging

        resp = super().form_valid(form)
        try:
            from shop.points_awards import try_award_daily_login

            granted, _ = try_award_daily_login(self.request.user)
            if granted > 0:
                messages.success(self.request, f"今日登录获得 {granted} 积分。")
        except Exception:
            logging.getLogger(__name__).exception("每日登录积分发放失败")
        return resp


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    try:
        from courses.models import LoginLog

        LoginLog.objects.create(
            employee=user,
            ip_address=(request.META.get("REMOTE_ADDR") or "").strip() or None,
            user_agent=(request.META.get("HTTP_USER_AGENT") or "").strip()[:300],
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("登录日志写入失败")


@require_http_methods(["GET", "POST"])
def employee_register(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = EmployeeRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            try:
                from shop.points_awards import try_award_daily_login

                g, _ = try_award_daily_login(user)
                if g > 0:
                    messages.success(request, f"注册成功，已自动登录。今日登录获得 {g} 积分。")
                else:
                    messages.success(request, "注册成功，已自动登录。")
            except Exception:
                messages.success(request, "注册成功，已自动登录。")
            return redirect("home")
    else:
        form = EmployeeRegistrationForm()
    return render(request, "registration/employee_register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def staff_register(request):
    if request.user.is_authenticated:
        return redirect("admin:index")
    if not (getattr(settings, "ADMIN_REGISTER_SECRET", "") or "").strip():
        messages.error(
            request,
            "未配置管理员邀请码（ADMIN_REGISTER_SECRET），无法自助注册管理员。请使用 python manage.py createsuperuser。",
        )
        return redirect("home")
    if request.method == "POST":
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            try:
                from shop.points_awards import try_award_daily_login

                g, _ = try_award_daily_login(user)
                if g > 0:
                    messages.success(
                        request,
                        f"管理员账号已创建。今日登录获得 {g} 积分（与员工规则一致，可在后台调整）。",
                    )
                else:
                    messages.success(request, "管理员账号已创建，请从「工作台」进入后台。")
            except Exception:
                messages.success(request, "管理员账号已创建，请从「工作台」进入后台。")
            return redirect("admin:index")
    else:
        form = StaffRegistrationForm()
    return render(request, "registration/staff_register.html", {"form": form})


@login_required
def notification_open(request, pk):
    """打开通知链接并标记为已读（单人通知写 read_at，全体通知仅写已读记录）。"""
    n = get_object_or_404(
        Notification.objects.filter(Q(employee__isnull=True) | Q(employee=request.user)),
        pk=pk,
    )
    if n.employee_id == request.user.id and n.read_at is None:
        Notification.objects.filter(pk=pk).update(read_at=timezone.now())
    NotificationRead.objects.get_or_create(notification=n, employee=request.user)
    target = (n.link or "").strip()
    if not target:
        return redirect("home")
    if target.startswith("http://") or target.startswith("https://"):
        return redirect(target)
    return redirect(target)


DEFAULT_ADMIN_SHORTCUTS = [
    {"key": "employees", "title": "员工管理", "desc": "员工档案与账号", "href": "/admin/users/employee/"},
    {"key": "courses", "title": "课程中心", "desc": "课程新建与维护", "href": "/admin/courses/course/"},
    {"key": "exams", "title": "考试中心", "desc": "考试配置与答卷", "href": "/admin/courses/exam/"},
    {"key": "trainings", "title": "培训活动", "desc": "活动与报名管理", "href": "/admin/shop/training/"},
    {"key": "focus_courses", "title": "课程切屏明细", "desc": "学习页监测数据", "href": "/admin/courses/coursefocusaccum/"},
    {"key": "focus_exams", "title": "考试监测会话", "desc": "考试中间页监测", "href": "/admin/courses/examfocussession/"},
    {"key": "notifications", "title": "站内通知", "desc": "通知与公告发布", "href": "/admin/users/notification/"},
    {"key": "instructors", "title": "讲师管理", "desc": "讲师档案与维护", "href": "/admin/courses/instructor/"},
    {"key": "categories", "title": "课程分类", "desc": "课程目录配置", "href": "/admin/courses/coursecategory/"},
    {"key": "forced_zero", "title": "切屏判零答卷", "desc": "快速定位异常答卷", "href": "/admin/courses/examrecord/?focus_forced_zero__exact=1"},
]
DEFAULT_SHORTCUT_KEYS = [item["key"] for item in DEFAULT_ADMIN_SHORTCUTS]
DEFAULT_SHORTCUT_BY_KEY = {item["key"]: item for item in DEFAULT_ADMIN_SHORTCUTS}
ADMIN_SHORTCUT_FIXED_COUNT = 8


@login_required
@require_http_methods(["GET"])
def admin_shortcuts_config(request):
    if not request.user.is_staff:
        return JsonResponse({"detail": "forbidden"}, status=403)

    user: Employee = request.user
    saved_keys = user.admin_shortcuts if isinstance(user.admin_shortcuts, list) else []
    valid_saved_keys = [k for k in saved_keys if k in DEFAULT_SHORTCUT_BY_KEY]
    if len(valid_saved_keys) < ADMIN_SHORTCUT_FIXED_COUNT:
        for key in DEFAULT_SHORTCUT_KEYS:
            if len(valid_saved_keys) >= ADMIN_SHORTCUT_FIXED_COUNT:
                break
            if key not in valid_saved_keys:
                valid_saved_keys.append(key)

    valid_saved_keys = valid_saved_keys[:ADMIN_SHORTCUT_FIXED_COUNT]
    selected = [DEFAULT_SHORTCUT_BY_KEY[k] for k in valid_saved_keys]
    return JsonResponse(
        {
            "selected": selected,
            "available": DEFAULT_ADMIN_SHORTCUTS,
            "selected_keys": valid_saved_keys,
        }
    )


@login_required
@require_POST
def admin_shortcuts_save(request):
    if not request.user.is_staff:
        return JsonResponse({"detail": "forbidden"}, status=403)

    keys = request.POST.getlist("keys[]")
    if len(keys) != ADMIN_SHORTCUT_FIXED_COUNT:
        return JsonResponse({"detail": f"keys must be {ADMIN_SHORTCUT_FIXED_COUNT}"}, status=400)

    cleaned = []
    seen = set()
    for k in keys:
        if k in DEFAULT_SHORTCUT_BY_KEY and k not in seen:
            cleaned.append(k)
            seen.add(k)

    if len(cleaned) != ADMIN_SHORTCUT_FIXED_COUNT:
        return JsonResponse({"detail": f"valid keys must be {ADMIN_SHORTCUT_FIXED_COUNT}"}, status=400)

    request.user.admin_shortcuts = cleaned
    request.user.save(update_fields=["admin_shortcuts"])
    return JsonResponse({"ok": True, "selected_keys": cleaned})


@login_required
@require_http_methods(["GET"])
def admin_dashboard_chart_data(request):
    if not request.user.is_staff:
        return JsonResponse({"detail": "forbidden"}, status=403)

    from courses.models import Course, ExamRecord, Instructor, LearningRecord
    from shop.models import ExchangeRecord, PointsLedger, Product, TrainingRegistration
    from users.models import Employee

    today = timezone.localdate()
    range_key = (request.GET.get("range") or "month").strip()

    def month_window(anchor):
        start_date = anchor.replace(day=1)
        if anchor.month == 12:
            next_month = anchor.replace(year=anchor.year + 1, month=1, day=1)
        else:
            next_month = anchor.replace(month=anchor.month + 1, day=1)
        return start_date, next_month - timedelta(days=1)

    def week_window(anchor):
        # 周一到周日；当前周上限截到今天
        start_date = anchor - timedelta(days=anchor.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date

    if range_key == "day":
        start = today
        end = today
    elif range_key == "week":
        start, end = week_window(today)
        if end > today:
            end = today
    elif range_key == "year":
        start = today.replace(month=1, day=1)
        end = today
    else:
        start, end = month_window(today)
        if end > today:
            end = today
        range_key = "month"

    axis_days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    # 口径说明：
    # - 活跃人数：按登录（Employee.last_login）去重统计
    # - 学习人数：按学习行为（LearningRecord.updated_at）去重统计
    # - 活跃时长 / 学习时长：暂无会话明细时采用人数驱动的估算值（用于趋势展示）
    #
    # 线上（MySQL）若未导入时区表，`__date` 可能触发 CONVERT_TZ 返回 NULL，
    # 导致“明明有登录/学习却统计为 0”。这里改为“时间范围过滤 + Python 本地日期聚合”，
    # 避免依赖数据库时区函数。
    learning_people_counts = {d: 0 for d in axis_days}
    exam_counts = {d: 0 for d in axis_days}
    active_people_counts = {d: 0 for d in axis_days}

    range_start = timezone.make_aware(timezone.datetime.combine(start, timezone.datetime.min.time()))
    range_end_exclusive = timezone.make_aware(
        timezone.datetime.combine(end + timedelta(days=1), timezone.datetime.min.time())
    )

    learning_people_seen = {d: set() for d in axis_days}
    learning_rows = LearningRecord.objects.filter(
        updated_at__gte=range_start,
        updated_at__lt=range_end_exclusive,
    ).values_list("updated_at", "employee_id")
    for updated_at, employee_id in learning_rows:
        if not updated_at or not employee_id:
            continue
        day = timezone.localtime(updated_at).date()
        if day in learning_people_seen:
            learning_people_seen[day].add(employee_id)
    for day, ids in learning_people_seen.items():
        learning_people_counts[day] = len(ids)

    exam_rows = ExamRecord.objects.filter(
        submitted_at__gte=range_start,
        submitted_at__lt=range_end_exclusive,
    ).values_list("submitted_at", flat=True)
    for submitted_at in exam_rows:
        if not submitted_at:
            continue
        day = timezone.localtime(submitted_at).date()
        if day in exam_counts:
            exam_counts[day] += 1

    active_people_seen = {d: set() for d in axis_days}
    active_rows = Employee.objects.filter(
        last_login__isnull=False,
        last_login__gte=range_start,
        last_login__lt=range_end_exclusive,
    ).values_list("last_login", "id")
    for last_login, employee_id in active_rows:
        if not last_login or not employee_id:
            continue
        day = timezone.localtime(last_login).date()
        if day in active_people_seen:
            active_people_seen[day].add(employee_id)
    for day, ids in active_people_seen.items():
        active_people_counts[day] = len(ids)

    if range_key == "year":
        labels = [d.strftime("%m") for d in axis_days]
    elif range_key == "day":
        labels = [d.strftime("%m-%d") for d in axis_days]
    else:
        labels = [d.strftime("%m-%d") for d in axis_days]
    dates = [d.isoformat() for d in axis_days]

    employee_total = Employee.objects.count()
    employee_active = Employee.objects.filter(is_active=True).count()
    employee_inactive = max(0, employee_total - employee_active)

    training_regs = TrainingRegistration.objects.count()
    learning_total = LearningRecord.objects.count()
    learning_completed = LearningRecord.objects.filter(is_completed=True).count()
    exam_total = ExamRecord.objects.count()
    points_daily_login = PointsLedger.objects.filter(source=PointsLedger.Source.DAILY_LOGIN).count()
    points_learning = PointsLedger.objects.filter(source=PointsLedger.Source.COURSE_COMPLETE).count()
    points_admin_adjust = PointsLedger.objects.filter(source=PointsLedger.Source.ADMIN_ADJUST).count()
    points_total = PointsLedger.objects.count()
    product_total = Product.objects.count()
    exchange_total = ExchangeRecord.objects.count()
    product_in_stock = Product.objects.filter(stock__gt=0).count()
    product_out_stock = max(0, product_total - product_in_stock)

    login_active_total = Employee.objects.filter(last_login__isnull=False).count()

    instructor_qs = Instructor.objects.annotate(course_count=Count("courses", distinct=True))
    instructor_with_courses = instructor_qs.filter(course_count__gt=0)
    instructor_top = instructor_with_courses.order_by("-course_count", "sort_order", "id").first()
    instructor_ordered = list(instructor_with_courses.order_by("-course_count", "sort_order", "id")[:10])
    instructor_bar_labels = [i.name for i in instructor_ordered]
    instructor_bar_values = [int(i.course_count or 0) for i in instructor_ordered]

    course_required = Course.objects.filter(course_type=Course.CourseType.REQUIRED).count()
    course_elective = Course.objects.filter(course_type=Course.CourseType.ELECTIVE).count()

    radar_indicator = [
        {"name": "登录活跃", "max": max(10, employee_total)},
        {"name": "课程学习", "max": max(10, learning_total)},
        {"name": "考试参与", "max": max(10, exam_total)},
        {"name": "培训报名", "max": max(10, training_regs)},
        {"name": "完课人次", "max": max(10, learning_completed)},
    ]

    return JsonResponse(
        {
            "range": range_key,
            "line_people": {
                "labels": labels,
                "dates": dates,
                "active_people": [active_people_counts[d] for d in axis_days],
                "learning_people": [learning_people_counts[d] for d in axis_days],
            },
            "line_hours": {
                "labels": labels,
                "dates": dates,
                "active_hours": [round(active_people_counts[d] * 0.8, 1) for d in axis_days],
                "learning_hours": [round(learning_people_counts[d] * 0.6, 1) for d in axis_days],
            },
            "pie": {
                "data": [
                    {"name": "在职可用", "value": employee_active},
                    {"name": "未启用", "value": employee_inactive},
                ]
            },
            "radar": {
                "indicator": radar_indicator,
                "value": [
                    login_active_total,
                    learning_total,
                    exam_total,
                    training_regs,
                    learning_completed,
                ],
            },
            "points_bar": {
                "labels": ["登录积分", "学习积分", "完课积分", "管理员调整"],
                "values": [points_daily_login, points_learning, learning_completed, points_admin_adjust],
            },
            "product_bar": {
                "labels": ["商品种类", "订单数量", "库存总数"],
                "values": [product_total, exchange_total, product_in_stock],
            },
            "points_summary": {
                "login_total": int(points_daily_login),
                "learning_total": int(points_learning),
                "completed_total": int(learning_completed),
                "adjust_total": int(points_admin_adjust),
                "product_total": int(product_total),
                "exchange_total": int(exchange_total),
            },
            "instructor_bar": {
                "labels": instructor_bar_labels,
                "values": instructor_bar_values,
            },
            "instructor_pie": {
                "data": [
                    {"name": "必修", "value": course_required},
                    {"name": "选修", "value": course_elective},
                ]
            },
            "instructor_summary": {
                "total": int(instructor_qs.count()),
                "with_courses": int(instructor_with_courses.count()),
                "course_total": course_required + course_elective,
                "required_total": course_required,
                "elective_total": course_elective,
                "top_name": getattr(instructor_top, "name", "—") if instructor_top else "—",
                "top_courses": int(getattr(instructor_top, "course_count", 0) or 0),
            },
        }
    )
