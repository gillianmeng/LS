from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
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

    from courses.models import ExamRecord, LearningRecord
    from shop.models import TrainingRegistration
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
    learning_counts = {d: 0 for d in axis_days}
    exam_counts = {d: 0 for d in axis_days}
    active_people_counts = {d: 0 for d in axis_days}

    learning_rows = (
        LearningRecord.objects.filter(updated_at__date__gte=start, updated_at__date__lte=end)
        .values("updated_at__date")
        .annotate(c=Count("id"))
    )
    for row in learning_rows:
        d = row["updated_at__date"]
        if d in learning_counts:
            learning_counts[d] = row["c"]

    exam_rows = (
        ExamRecord.objects.filter(submitted_at__date__gte=start, submitted_at__date__lte=end)
        .values("submitted_at__date")
        .annotate(c=Count("id"))
    )
    for row in exam_rows:
        d = row["submitted_at__date"]
        if d in exam_counts:
            exam_counts[d] = row["c"]

    active_people_rows = (
        LearningRecord.objects.filter(updated_at__date__gte=start, updated_at__date__lte=end)
        .values("updated_at__date")
        .annotate(c=Count("employee", distinct=True))
    )
    for row in active_people_rows:
        d = row["updated_at__date"]
        if d in active_people_counts:
            active_people_counts[d] = row["c"]

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

    radar_indicator = [
        {"name": "员工活跃", "max": max(10, employee_total)},
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
                "learning_people": [learning_counts[d] for d in axis_days],
            },
            "line_hours": {
                "labels": labels,
                "dates": dates,
                "active_hours": [round(active_people_counts[d] * 0.8, 1) for d in axis_days],
                "learning_hours": [round(learning_counts[d] * 0.6, 1) for d in axis_days],
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
                    employee_active,
                    learning_total,
                    exam_total,
                    training_regs,
                    learning_completed,
                ],
            },
        }
    )
