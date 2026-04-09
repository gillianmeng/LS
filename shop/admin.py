from django.contrib import admin

from learning_system.admin_mixins import OptionalFileFieldsAdminMixin

from .forms import ShopMallSettingsForm, TrainingAdminForm
from .models import (
    ExchangeRecord,
    MallOrder,
    MallShippingAddress,
    PointsLedger,
    Product,
    ShopMallSettings,
    Training,
    TrainingRegistration,
)


@admin.register(ShopMallSettings)
class ShopMallSettingsAdmin(admin.ModelAdmin):
    """全站仅一条记录：积分商城前台规则与领取默认说明。"""

    form = ShopMallSettingsForm
    save_on_top = True

    list_display = ("__str__", "preview_points_rules", "preview_instruction")

    @admin.display(description="积分规则（摘要）")
    def preview_points_rules(self, obj):
        text = (obj.points_earn_rules or "").strip()
        return (text[:60] + "…") if len(text) > 60 else (text or "（使用系统内置默认）")

    @admin.display(description="现场领取说明（摘要）")
    def preview_instruction(self, obj):
        text = (obj.default_pickup_instruction or "").strip()
        return (text[:80] + "…") if len(text) > 80 else (text or "—")

    fieldsets = (
        (
            "① 积分获取规则（前台「积分规则」区块）",
            {
                "fields": ("points_earn_rules",),
                "description": "此处修改即对应员工端积分商城页的「积分规则」展示。留空则使用内置默认；填写后整段替换前台文案。排版：每条单独一行，前 3 行显示为三列卡片。下方 ③ 的数值与程序实际发放一致，请与文案描述对齐。",
            },
        ),
        (
            "③ 学习积分（程序按此处数值发放）",
            {
                "fields": (
                    "points_daily_login",
                    "points_course_complete_default",
                    "points_learning_daily_cap",
                ),
                "description": "每日登录在员工首次登录成功时自动发放；完课积分在学员点击「标记已学完」或后台将学习记录设为已完成后发放。单门课优先使用课程设置中的「学习完成后可获积分」，为 0 时使用「默认完课奖励」。",
            },
        ),
        (
            "② 默认现场领取说明（结算页 / 新订单）",
            {
                "fields": ("default_pickup_instruction",),
                "description": "员工选择「现场领取」且未填写自定义说明时，订单中写入的默认文案；仅影响保存后的新订单。",
            },
        ),
    )

    def has_add_permission(self, request):
        return not ShopMallSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PointsLedger)
class PointsLedgerAdmin(admin.ModelAdmin):
    list_display = ("created_at", "employee", "amount", "source", "course", "note")
    list_filter = ("source",)
    search_fields = ("employee__emp_id", "employee__real_name", "note")
    readonly_fields = ("employee", "amount", "source", "note", "course", "local_date", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Product)
class ProductAdmin(OptionalFileFieldsAdminMixin, admin.ModelAdmin):
    list_display = ("name", "points_cost", "stock", "image")
    search_fields = ("name",)


@admin.register(MallShippingAddress)
class MallShippingAddressAdmin(admin.ModelAdmin):
    list_display = ("employee", "label", "recipient_name", "recipient_phone", "is_default", "updated_at")
    list_filter = ("is_default",)
    search_fields = ("employee__emp_id", "employee__real_name", "recipient_name", "recipient_phone", "address_detail")
    raw_id_fields = ("employee",)


@admin.register(MallOrder)
class MallOrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_no",
        "employee",
        "product_name",
        "points_spent",
        "delivery_type",
        "status",
        "created_at",
    )
    list_filter = ("status", "delivery_type", "created_at")
    search_fields = ("order_no", "product_name", "employee__emp_id", "recipient_phone", "tracking_number")
    raw_id_fields = ("employee", "product")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("订单", {"fields": ("order_no", "status", "employee", "product", "product_name", "points_spent", "created_at", "updated_at")}),
        ("领取", {"fields": ("delivery_type", "recipient_name", "recipient_phone", "address_detail", "pickup_location_note")}),
        ("备注", {"fields": ("buyer_remark",)}),
        ("物流（邮寄）", {"fields": ("logistics_company", "tracking_number")}),
    )


@admin.register(ExchangeRecord)
class ExchangeRecordAdmin(admin.ModelAdmin):
    list_display = ("employee", "product", "points_spent", "exchanged_at")
    list_filter = ("exchanged_at",)
    search_fields = ("employee__emp_id", "product__name")


class TrainingRegistrationInline(admin.TabularInline):
    model = TrainingRegistration
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("employee",)
    fields = ("employee", "status", "message", "admin_note", "created_at", "updated_at")


@admin.register(Training)
class TrainingAdmin(OptionalFileFieldsAdminMixin, admin.ModelAdmin):
    form = TrainingAdminForm
    list_display = (
        "title",
        "applications_category_label",
        "start_at",
        "end_at",
        "is_published",
        "is_home_featured",
        "sort_order",
        "registration_count",
    )
    list_filter = ("is_published", "is_home_featured", "applications_category")
    search_fields = ("title", "summary", "location", "instructor_name", "schedule_note")
    date_hierarchy = "start_at"
    ordering = ("sort_order", "-start_at")
    inlines = [TrainingRegistrationInline]
    fieldsets = (
        (
            "内容",
            {
                "fields": (
                    "title",
                    "summary",
                    "description",
                    "cover",
                    "instructor_name",
                    "promotional_url",
                    "promotional_link_label",
                ),
                "description": "「宣传/资料链接」用于飞书文档、活动介绍页等；「外链报名」用于报名表单类地址。",
            },
        ),
        (
            "时间与地点",
            {
                "fields": (
                    "start_at",
                    "end_at",
                    "schedule_note",
                    "registration_deadline",
                    "location",
                    "online_meeting_url",
                ),
                "description": "排期可只填「时间安排说明」；若填写起止时间，请保证结束不早于开始。",
            },
        ),
        (
            "报名",
            {
                "fields": ("registration_external_url", "max_participants"),
                "description": "外链报名：飞书表单 / 外部系统等 URL。未填则仅站内报名。",
            },
        ),
        (
            "我的报名 · 分类标签",
            {
                "fields": ("applications_category",),
                "description": "从下列标签中选一项，与员工前台「我的报名」顶部七个选项一致：培训、活动、评选、讲师级别认证、课程授权认证、外训、独立报名。",
            },
        ),
        (
            "发布范围",
            {
                "fields": ("is_published", "is_home_featured", "sort_order"),
                "description": "「在活动广场展示」控制活动广场与首页展示。",
            },
        ),
    )

    @admin.display(description="我的报名标签")
    def applications_category_label(self, obj):
        return obj.get_applications_category_display()

    @admin.display(description="报名人数")
    def registration_count(self, obj):
        return obj.registrations.count()


@admin.register(TrainingRegistration)
class TrainingRegistrationAdmin(admin.ModelAdmin):
    list_display = ("training", "employee", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("training__title", "employee__emp_id", "employee__real_name", "message")
    raw_id_fields = ("training", "employee")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("training", "employee", "status")}),
        ("留言与备注", {"fields": ("message", "admin_note")}),
        ("时间", {"fields": ("created_at", "updated_at")}),
    )
