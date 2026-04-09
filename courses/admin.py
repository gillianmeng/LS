from django.contrib import admin

from learning_system.admin_mixins import OptionalFileFieldsAdminMixin

from .forms import ExamAdminForm
from .models import Course, CourseCategory, Exam, ExamRecord, Instructor, LearningRecord


@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "sort_order")
    list_filter = ("parent",)
    search_fields = ("name",)
    ordering = ("sort_order", "id")


@admin.register(Course)
class CourseAdmin(OptionalFileFieldsAdminMixin, admin.ModelAdmin):
    list_display = (
        "name",
        "content_kind",
        "course_type",
        "reward_points",
        "view_count",
        "duration_minutes",
        "is_recommended",
        "exclude_from_hot_ranking",
        "created_at",
    )
    list_filter = (
        "content_kind",
        "course_type",
        "catalog_category",
        "is_recommended",
        "exclude_from_hot_ranking",
    )
    search_fields = ("name", "description", "article_body")
    readonly_fields = ("created_at", "view_count")
    list_per_page = 50
    save_on_top = True
    fieldsets = (
        ("基本信息", {"fields": ("name", "course_type", "catalog_category", "description")}),
        (
            "内容形式",
            {
                "fields": ("content_kind", "article_url", "article_body"),
                "description": "文章课：优先使用「原文链接」在新窗口打开外部页面以保留版式；「文章正文」用于站内补充或纯文本摘要。视频课以下方视频为准。",
            },
        ),
        (
            "封面与视频资源",
            {
                "description": "文章课建议上传封面图；视频课请上传文件或填写链接（支持常见直链与 YouTube 等）。已上传的文件可勾选「清除」后保存以删除。",
                "fields": ("thumbnail", "cover_url", "video_file", "video_url"),
            },
        ),
        ("学时与积分", {"fields": ("duration_minutes", "reward_points")}),
        (
            "前台展示",
            {
                "fields": ("is_recommended", "exclude_from_hot_ranking"),
                "description": "「最热课程」按浏览量排序；若不希望某课参与最热排行，请勾选右侧开关。",
            },
        ),
        ("统计数据", {"fields": ("view_count", "created_at")}),
    )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "catalog_category":
            kwargs["queryset"] = CourseCategory.objects.filter(
                parent__isnull=False
            ).select_related("parent").order_by("parent__sort_order", "sort_order", "id")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Instructor)
class InstructorAdmin(OptionalFileFieldsAdminMixin, admin.ModelAdmin):
    list_display = ("name", "title", "employee", "sort_order", "is_published", "created_at")
    list_filter = ("is_published",)
    search_fields = ("name", "title", "employee__emp_id", "employee__real_name")
    autocomplete_fields = ("employee",)
    list_editable = ("sort_order", "is_published")
    ordering = ("sort_order", "id")
    fieldsets = (
        (None, {"fields": ("name", "title", "employee")}),
        (
            "头像",
            {
                "fields": ("photo", "photo_url"),
                "description": "上传或外链优先展示；二者皆空时，若已选「关联员工」且该员工有个人头像，则使用员工头像。",
            },
        ),
        ("展示", {"fields": ("sort_order", "is_published", "created_at")}),
    )
    readonly_fields = ("created_at",)


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    form = ExamAdminForm
    list_display = (
        "title",
        "kind",
        "starts_at",
        "ends_at",
        "duration_minutes",
        "pass_score",
        "is_published",
        "created_at",
    )
    list_filter = ("kind", "is_published")
    search_fields = ("title", "description")
    list_per_page = 50
    save_on_top = True
    fieldsets = (
        ("基本信息", {"fields": ("title", "kind", "description", "is_published")}),
        (
            "开放时间（可任意修改）",
            {
                "description": "按「日期」与「时刻」分别填写；留空表示不限制该端。时间均为后台配置的时区（上海）。",
                "fields": ("start_date", "start_time", "end_date", "end_time"),
            },
        ),
        (
            "答题限时",
            {
                "fields": ("duration_minutes",),
                "description": "与开放时间无关：例如开放三天，但每次进入后仅允许作答 90 分钟。",
            },
        ),
        ("成绩规则", {"fields": ("max_score", "pass_score")}),
        ("前台入口", {"fields": ("entry_url",), "description": "填写后，员工在「我的考试」列表可点击跳转（如问卷星、外部考试系统）。"}),
        ("创建", {"fields": ("created_at",)}),
        (
            "当前已保存的开放时段（只读核对）",
            {
                "classes": ("collapse",),
                "fields": ("starts_at", "ends_at"),
                "description": "保存后由上方「日期/时刻」自动写入数据库，展开可核对。",
            },
        ),
    )
    readonly_fields = ("created_at", "starts_at", "ends_at")


@admin.register(ExamRecord)
class ExamRecordAdmin(admin.ModelAdmin):
    list_display = ("exam", "employee", "score", "submitted_at")
    list_filter = ("exam__kind",)
    search_fields = ("exam__title", "employee__emp_id", "employee__real_name")
    raw_id_fields = ("exam", "employee")


@admin.register(LearningRecord)
class LearningRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "course", "progress_percentage", "is_completed", "updated_at")
    list_filter = ("is_completed",)
    search_fields = ("employee__emp_id", "employee__real_name", "course__name")
    readonly_fields = ("updated_at",)
