from django import forms
from django.conf import settings
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group

from .models import Employee


class AdminEmployeeAuthenticationForm(AdminAuthenticationForm):
    """管理后台登录：首行字段名为 username，展示为工号；自动去除首尾空格。"""

    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "invalid_login": "工号或密码不正确；若账号已存在，需具备「职员权限」才可进入后台。",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "工号"
        self.fields["password"].label = "密码"

    def clean_username(self):
        username = self.cleaned_data["username"]
        if isinstance(username, str):
            return username.strip()
        return username


class EmployeeAuthenticationForm(AuthenticationForm):
    """前台登录：字段名仍为 username（Django 约定），展示为工号。"""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "工号或密码错误，请重试。",
        "inactive": "该账号已停用。",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "工号"
        self.fields["username"].widget.attrs.update(
            {
                "placeholder": "请输入工号",
                "autocomplete": "username",
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500",
            }
        )
        self.fields["password"].label = "密码"
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "请输入密码",
                "autocomplete": "current-password",
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500",
            }
        )


class _EmployeeFieldsMixin:
    """注册表单：工号、姓名 + 密码。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("emp_id", "real_name"):
            if name in self.fields:
                self.fields[name].widget.attrs.update(
                    {
                        "class": "w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500",
                    }
                )
        for name in ("password1", "password2"):
            if name in self.fields:
                self.fields[name].widget.attrs.update(
                    {
                        "class": "w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500",
                    }
                )


class EmployeeRegistrationForm(_EmployeeFieldsMixin, UserCreationForm):
    """普通员工注册（无后台权限）。"""

    class Meta:
        model = Employee
        fields = ("emp_id", "real_name")
        labels = {
            "emp_id": "工号",
            "real_name": "姓名",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "密码"
        self.fields["password2"].label = "确认密码"


class StaffRegistrationForm(EmployeeRegistrationForm):
    """管理员注册：需邀请码（环境变量 ADMIN_REGISTER_SECRET）。"""

    admin_secret = forms.CharField(
        label="管理员邀请码",
        widget=forms.PasswordInput(
            attrs={
                "class": "w-full rounded-lg border border-slate-200 px-3 py-2.5 text-slate-900 placeholder:text-slate-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500",
                "autocomplete": "off",
                "placeholder": "由运维配置的邀请码",
            }
        ),
    )

    def clean_admin_secret(self):
        secret = self.cleaned_data.get("admin_secret", "").strip()
        expected = getattr(settings, "ADMIN_REGISTER_SECRET", "") or ""
        if not expected:
            raise forms.ValidationError("当前未开放管理员自助注册。")
        if secret != expected:
            raise forms.ValidationError("邀请码不正确。")
        return secret

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_staff = True
        if commit:
            user.save()
            self.save_m2m()
        return user


class EmployeeAdminChangeForm(UserChangeForm):
    """员工编辑：附加积分调整（写入积分流水，不直接改余额字段）。"""

    points_adjust_delta = forms.IntegerField(
        label="积分调整",
        required=False,
        help_text="相对当前余额增减：正数为增加，负数为扣减；保存后写入「学习积分流水」并更新余额。留空表示不调整。",
    )
    points_adjust_note = forms.CharField(
        label="调整说明",
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "placeholder": "选填，将记入流水说明",
                "style": "min-width: 28rem;",
            }
        ),
    )

    class Meta(UserChangeForm.Meta):
        model = Employee

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields.pop("points_adjust_delta", None)
            self.fields.pop("points_adjust_note", None)

    def clean(self):
        cleaned_data = super().clean()
        delta = cleaned_data.get("points_adjust_delta")
        if delta is None or self.instance.pk is None:
            return cleaned_data
        if delta == 0:
            cleaned_data["points_adjust_delta"] = None
            return cleaned_data
        balance = int(self.instance.points_balance or 0)
        if balance + int(delta) < 0:
            raise forms.ValidationError(
                {"points_adjust_delta": "扣减后积分余额不能为负，请减小扣减数量。"}
            )
        return cleaned_data


class GroupAdminForm(forms.ModelForm):
    """组编辑：附带「组员」多选（Django 默认 Group 后台没有此项）。"""

    users = forms.ModelMultipleChoiceField(
        label="组员（员工）",
        queryset=get_user_model().objects.order_by("emp_id"),
        required=False,
        widget=FilteredSelectMultiple("员工", False),
        help_text="保存后，所选员工将属于本组；取消选择则移除关系。",
    )

    class Meta:
        model = Group
        fields = ("name", "permissions")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["users"].initial = self.instance.user_set.order_by("emp_id")

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            instance.save()
            self.save_m2m()
            instance.user_set.set(self.cleaned_data["users"])
        return instance
