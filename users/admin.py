from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import F

from learning_system.admin_mixins import OptionalFileFieldsAdminMixin

from .forms import EmployeeAdminChangeForm, GroupAdminForm
from .models import Employee, LeaderboardConfig, Notification, NotificationRead, Project, ProjectModule, SiteBannerConfig


class ProjectModuleInline(admin.TabularInline):
    model = ProjectModule
    extra = 0
    fields = ("module_type", "title", "enabled", "sort_order", "selected_object_ids", "config")
    readonly_fields = ()
    autocomplete_fields = ()

    class Media:
        js = ("js/project_module_admin.js",)


class ProjectModuleChoiceForm(forms.ModelForm):
    content_pool = forms.MultipleChoiceField(
        label="模块内容选择",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="根据模块类型选择要挂入项目的内容。保存后会写入已选内容 ID。",
    )

    class Meta:
        model = ProjectModule
        fields = ("project", "module_type", "title", "enabled", "sort_order", "config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        module_type = self.data.get(f"{self.prefix}-module_type") if self.data else None
        if not module_type and self.instance.pk:
            module_type = self.instance.module_type
        self.fields["content_pool"].choices = self._choices_for(module_type)
        if self.instance.pk:
            self.initial["content_pool"] = [str(x) for x in (self.instance.selected_object_ids or [])]

    def _choices_for(self, module_type):
        module_type = (module_type or "").strip()
        if module_type == ProjectModule.ModuleType.TRAINING:
            from shop.models import Training
            return [(str(x.pk), x.title) for x in Training.objects.order_by("-created_at")[:200]]
        if module_type == ProjectModule.ModuleType.COURSE:
            from courses.models import Course
            return [(str(x.pk), x.name) for x in Course.objects.order_by("-created_at")[:200]]
        if module_type == ProjectModule.ModuleType.EXAM:
            from courses.models import Exam
            return [(str(x.pk), x.title) for x in Exam.objects.order_by("-created_at")[:200]]
        if module_type == ProjectModule.ModuleType.ACTIVITY:
            from shop.models import Training
            qs = Training.objects.filter(applications_category=Training.ApplicationsCategory.ACTIVITY).order_by("-created_at")[:200]
            return [(str(x.pk), x.title) for x in qs]
        return []

    def clean(self):
        cleaned = super().clean()
        cleaned["selected_object_ids"] = [int(x) for x in self.cleaned_data.get("content_pool", [])]
        return cleaned

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.selected_object_ids = self.cleaned_data.get("selected_object_ids", [])
        if commit:
            obj.save()
            self.save_m2m()
        return obj


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "module_count", "is_active", "sort_order", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "code", "description")
    ordering = ("sort_order", "id")
    fieldsets = ((None, {"fields": ("name", "code", "description", "is_active", "sort_order")} ),)
    inlines = (ProjectModuleInline,)

    @admin.display(description="模块数")
    def module_count(self, obj):
        return obj.modules.count()


@admin.register(ProjectModule)
class ProjectModuleAdmin(admin.ModelAdmin):
    form = ProjectModuleChoiceForm
    list_display = ("project", "module_type", "enabled", "sort_order", "updated_at")
    list_filter = ("module_type", "enabled", "project")
    search_fields = ("project__name", "project__code", "title")
    ordering = ("project_id", "sort_order", "id")
    raw_id_fields = ("project",)
    fieldsets = (
        (None, {"fields": ("project", "module_type", "title", "enabled", "sort_order")} ),
        ("模块内容", {"fields": ("content_pool",), "description": "根据模块类型选择该项目下要启用的具体内容。"}),
        ("模块配置", {"fields": ("config",)}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if hasattr(form, "cleaned_data"):
            selected = form.cleaned_data.get("selected_object_ids")
            if selected is not None:
                obj.selected_object_ids = selected
                obj.save(update_fields=["selected_object_ids", "updated_at"])


@admin.register(SiteBannerConfig)
class SiteBannerConfigAdmin(OptionalFileFieldsAdminMixin, admin.ModelAdmin):
    """替换各页顶部 Banner；单条记录。"""

    fieldsets = (
        (
            "页面 Banner（留空则使用内置默认图）",
            {
                "fields": (
                    "banner_home",
                    "banner_my_learning",
                    "banner_points_mall",
                    "banner_activity_plaza",
                ),
                "description": (
                    "尺寸与前台版式对齐（宽×高，像素）："
                    "① 首页 1280×360，全宽通栏（主内容 max-w-7xl）。"
                    "② 我的学习 1200×300（约 4:1），桌面为半栏宽度，重要信息放中间以免裁切。"
                    "③ 积分商城 / 活动广场：左侧 Banner 固定比例 10:3（横图），推荐 1200×360 或 2400×720；"
                    "不可用正方形（如 1200×1200）。"
                    " 推荐 PNG 或 JPG。"
                ),
            },
        ),
    )

    def has_add_permission(self, request):
        return not SiteBannerConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeaderboardConfig)
class LeaderboardConfigAdmin(admin.ModelAdmin):
    """单条配置：仅允许一条记录（pk=1）。修改保存后刷新前台首页即可看到文案变化。"""

    list_display = ("__str__", "time_range_label", "home_rank_count", "sidebar_rank_count", "exclude_staff")
    fieldsets = (
        (
            "首页与「我的学习」积分榜文案",
            {
                "fields": ("time_range_label", "footnote", "exclude_staff"),
                "description": "时间范围标签、脚注为前台展示文案；取消「排除管理员」后，默认脚注「（不含系统管理员）」将自动隐藏，以免与榜单含义冲突。",
            },
        ),
        ("人数与范围", {"fields": ("home_rank_count", "sidebar_rank_count")} ),
    )

    def has_add_permission(self, request):
        return not LeaderboardConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


def _recipient_label(obj):
    return obj.employee.emp_id if obj.employee_id else "全体"


_recipient_label.short_description = "接收人"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", _recipient_label, "read_at", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "employee__emp_id", "employee__real_name")
    raw_id_fields = ("employee",)
    readonly_fields = ("created_at",)


@admin.register(NotificationRead)
class NotificationReadAdmin(admin.ModelAdmin):
    list_display = ("notification", "employee", "read_at")
    list_filter = ("read_at",)
    search_fields = ("notification__title", "employee__emp_id")
    raw_id_fields = ("notification", "employee")
    readonly_fields = ("read_at",)


@admin.register(Employee)
class EmployeeAdmin(OptionalFileFieldsAdminMixin, UserAdmin):
    form = EmployeeAdminChangeForm
    ordering = ("emp_id",)
    list_display = ("emp_id", "real_name", "email", "is_staff", "is_superuser", "points_balance")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("emp_id", "real_name", "email")
    fieldsets = (
        (None, {"fields": ("emp_id", "password")} ),
        ("个人信息", {"fields": ("real_name", "email", "avatar", "signature")} ),
        (
            "组织信息",
            {
                "fields": (
                    "dept_level_1",
                    "dept_level_2",
                    "dept_level_3",
                    "dept_level_4",
                    "job_level",
                    "hire_date",
                )
            },
        ),
        (
            "积分",
            {
                "fields": ("points_balance",),
                "description": "编辑已有员工时，请用下方「积分调整」增减余额；请勿依赖直接改余额（余额为只读）。",
            },
        ),
        ("飞书", {"fields": ("feishu_open_id", "feishu_union_id")} ),
        (
            "权限",
            {
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
                "description": (
                    "超级用户不受权限表限制。其他账号：须勾选「职员状态」才可登录管理后台；"
                    "将员工加入已在「组」里分配了「组内权限」的组时，系统会自动勾选职员状态。"
                    "能访问哪些模型由「组」与「用户权限」中的勾选项共同决定。"
                ),
            },
        ),
        ("重要日期", {"fields": ("last_login", "date_joined")} ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "emp_id",
                    "password1",
                    "password2",
                    "real_name",
                    "email",
                    "groups",
                ),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj is not None:
            for i, (title, data) in enumerate(fieldsets):
                if title == "积分":
                    fieldsets[i] = (
                        "积分",
                        {
                            "fields": (
                                "points_balance",
                                "points_adjust_delta",
                                "points_adjust_note",
                            ),
                            "description": (
                                "当前余额为只读。填写「积分调整」相对增减（正数加、负数减），"
                                "可选「调整说明」；保存后写入「学习积分流水」并更新余额。"
                            ),
                        },
                    )
                    break
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj is not None and "points_balance" not in ro:
            ro.append("points_balance")
        return ro

    def save_model(self, request, obj, form, change):
        from shop.models import PointsLedger

        if not change:
            super().save_model(request, obj, form, change)
            return
        delta = form.cleaned_data.get("points_adjust_delta")
        note = (form.cleaned_data.get("points_adjust_note") or "").strip()
        apply_adj = delta is not None and delta != 0
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            if apply_adj:
                u = request.user
                admin_label = getattr(u, "emp_id", None) or (
                    u.get_username() if getattr(u, "is_authenticated", False) else ""
                ) or str(getattr(u, "pk", ""))
                PointsLedger.objects.create(
                    employee_id=obj.pk,
                    amount=delta,
                    source=PointsLedger.Source.ADMIN_ADJUST,
                    note=(note or f"管理员调整（{admin_label}）")[:200],
                )
                Employee.objects.filter(pk=obj.pk).update(
                    points_balance=F("points_balance") + delta
                )
                obj.refresh_from_db(fields=["points_balance"])


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """组：在「组员」中勾选员工；默认 auth.Group 后台无法从组一侧维护成员。"""

    form = GroupAdminForm
    search_fields = ("name",)
    ordering = ("name",)
    filter_horizontal = ("permissions",)
    fieldsets = (
        (None, {"fields": ("name",)}),
        ("组内权限", {"fields": ("permissions",)}),
        (
            "组员",
            {
                "fields": ("users",),
                "description": (
                    "左右移动以加入或移出本组。保存后，若本组在「组内权限」中勾选了任意权限，"
                    "系统会自动为该员工开通「职员状态」，否则无法登录管理后台。"
                    "员工在后台能操作哪些菜单，由「组内权限」中的具体权限决定（非超级用户时生效）。"
                ),
            },
        ),
    )

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        if db_field.name == "permissions":
            qs = kwargs.get("queryset", db_field.remote_field.model.objects)
            kwargs["queryset"] = qs.select_related("content_type")
        return super().formfield_for_manytomany(db_field, request=request, **kwargs)
