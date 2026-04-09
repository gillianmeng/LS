from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import EmployeeAuthenticationForm, EmployeeRegistrationForm, StaffRegistrationForm
from .models import Notification, NotificationRead


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
