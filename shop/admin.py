from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from learning_system.admin_mixins import OptionalFileFieldsAdminMixin

from .forms import ShopMallSettingsForm, TrainingAdminForm
from users.feishu_message import FeishuMessenger

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
    # 不使用 date_hierarchy：MySQL 未加载时区表时，USE_TZ 下会触发 CONVERT_TZ 报错（见 Django 文档 MySQL time zone definitions）

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
        "order_overview",
        "fulfillment_overview",
        "ops_links",
        "created_at",
    )
    list_display_links = ("order_overview",)
    list_filter = ("status", "delivery_type", "created_at")
    search_fields = ("order_no", "product_name", "employee__emp_id", "recipient_phone", "tracking_number")
    raw_id_fields = ("employee", "product")
    readonly_fields = ("created_at", "updated_at", "pickup_notice_sent_at", "completed_at")
    actions = ("send_pickup_notice", "mark_orders_completed")
    fieldsets = (
        ("订单", {"fields": ("order_no", "status", "employee", "product", "product_name", "points_spent", "created_at", "updated_at")}),
        ("领取", {"fields": ("delivery_type", "recipient_name", "recipient_phone", "address_detail", "pickup_location_note", "pickup_notice_sent_at", "completed_at")}),
        ("备注", {"fields": ("buyer_remark",)}),
        ("物流（邮寄）", {"fields": ("logistics_company", "tracking_number")}),
    )

    @admin.display(description="订单概览")
    def order_overview(self, obj):
        muted = bool(obj.completed_at or obj.status == MallOrder.OrderStatus.COMPLETED)
        title_color = "#9ca3af" if muted else "#111827"
        sub_color = "#cbd5e1" if muted else "#6b7280"
        status_chip = self._status_badge("已结单" if muted else "处理中", "neutral" if muted else "warning")
        return format_html(
            '<div style="display:flex; flex-direction:column; gap:6px; line-height:1.25;{}">'
            '<div style="display:flex; align-items:center; gap:8px;">'
            '<strong style="font-size:14px; color:{};">{}</strong>'
            '{}'
            '</div>'
            '<span style="color:{}; font-size:12px;">{} · {}</span>'
            '</div>',
            " opacity:0.78;" if muted else "",
            title_color,
            obj.product_name,
            status_chip,
            sub_color,
            obj.order_no,
            obj.employee.real_name,
        )

    @admin.display(description="处理信息")
    def fulfillment_overview(self, obj):
        notice = self._status_badge(
            "已通知" if obj.pickup_notice_sent_at else "待通知",
            "success" if obj.pickup_notice_sent_at else "muted",
        )
        delivery = self._status_badge(
            "现场领取" if obj.delivery_type == MallOrder.DeliveryType.PICKUP else "快递邮寄",
            "info",
        )

        if obj.delivery_type == MallOrder.DeliveryType.PICKUP:
            delivered_text = "已领取" if (obj.completed_at or obj.status == MallOrder.OrderStatus.COMPLETED) else "待领取"
            delivered_tone = "success" if delivered_text == "已领取" else "warning"
        else:
            shipped_done = (
                obj.status in (MallOrder.OrderStatus.SHIPPED, MallOrder.OrderStatus.COMPLETED)
                or bool((obj.logistics_company or "").strip())
                or bool((obj.tracking_number or "").strip())
            )
            delivered_text = "已邮寄" if shipped_done else "待邮寄"
            delivered_tone = "success" if shipped_done else "warning"

        delivered = self._status_badge(delivered_text, delivered_tone)

        return format_html(
            '<div style="display:flex; flex-wrap:wrap; gap:6px; align-items:center; max-width:360px;">{}{}{} </div>',
            notice,
            delivery,
            delivered,
        )

    def _status_badge(self, text, tone):
        palette = {
            "success": "background:#ecfdf5;color:#047857;border-color:#a7f3d0;",
            "warning": "background:#fffbeb;color:#b45309;border-color:#fde68a;",
            "info": "background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe;",
            "neutral": "background:#f8fafc;color:#475569;border-color:#e2e8f0;",
            "muted": "background:#f9fafb;color:#6b7280;border-color:#e5e7eb;",
        }
        style = palette.get(tone, palette["neutral"])
        return format_html(
            '<span style="display:inline-flex; align-items:center; padding:3px 9px; border:1px solid; border-radius:999px; font-size:12px; line-height:1; white-space:nowrap; {}">{}</span>',
            style,
            text,
        )

    def ops_links(self, obj):
        if not obj.pk:
            return "—"
        if obj.completed_at or obj.status == MallOrder.OrderStatus.COMPLETED:
            return mark_safe(
                '<div style="display:flex; flex-direction:column; gap:6px; width:74px;">'
                '<span class="button" style="display:block; width:100%; box-sizing:border-box; text-align:center; padding:3px 4px; line-height:1.1; font-size:12px; white-space:nowrap; background:#e5e7eb; color:#6b7280; border-color:#d1d5db; cursor:default;">已结单</span>'
                '</div>'
            )
        return format_html(
            '<div style="display:flex; flex-direction:column; gap:6px; width:74px;">'
            '<a class="button" style="display:block; width:100%; box-sizing:border-box; text-align:center; padding:3px 4px; line-height:1.1; font-size:12px; white-space:nowrap; background:#2563eb; color:#ffffff; border-color:#1d4ed8; box-shadow:none;" href="{}">通知领取</a>'
            '<a class="button" style="display:block; width:100%; box-sizing:border-box; text-align:center; padding:3px 4px; line-height:1.1; font-size:12px; white-space:nowrap; background:#dc2626; color:#ffffff; border-color:#b91c1c; box-shadow:none;" href="{}">结单</a>'
            '</div>',
            reverse("admin:shop_mallorder_send_pickup_notice", args=[obj.pk]),
            reverse("admin:shop_mallorder_mark_completed", args=[obj.pk]),
        )

    ops_links.short_description = "操作"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/send-pickup-notice/",
                self.admin_site.admin_view(self.send_pickup_notice_view),
                name="shop_mallorder_send_pickup_notice",
            ),
            path(
                "<path:object_id>/mark-completed/",
                self.admin_site.admin_view(self.mark_completed_view),
                name="shop_mallorder_mark_completed",
            ),
        ]
        return custom + urls

    def send_pickup_notice_view(self, request, object_id):
        order = self.get_object(request, object_id)
        if not order:
            self.message_user(request, "订单不存在。", level=messages.ERROR)
            return redirect("admin:shop_mallorder_changelist")

        messenger = FeishuMessenger()
        receiver = getattr(order.employee, "feishu_open_id", "") or ""
        text = (
            f"【积分商城】你有一笔订单需要领取\n"
            f"订单号：{order.order_no}\n"
            f"商品：{order.product_name}\n"
            f"领取方式：{order.get_delivery_type_display()}\n"
            f"状态：{order.get_status_display()}\n"
        )
        try:
            if receiver:
                messenger.send_text_to_user(receiver, text)
            if not order.pickup_notice_sent_at:
                order.pickup_notice_sent_at = timezone.now()
                order.save(update_fields=["pickup_notice_sent_at", "updated_at"])
            self.message_user(request, "已发送飞书通知领取消息。", level=messages.SUCCESS)
        except Exception as exc:
            self.message_user(request, f"飞书消息发送失败：{exc}", level=messages.ERROR)
        return redirect(request.META.get("HTTP_REFERER") or reverse("admin:shop_mallorder_change", args=[order.pk]))

    def mark_completed_view(self, request, object_id):
        order = self.get_object(request, object_id)
        if not order:
            self.message_user(request, "订单不存在。", level=messages.ERROR)
            return redirect("admin:shop_mallorder_changelist")
        if order.status != MallOrder.OrderStatus.COMPLETED or not order.completed_at:
            order.status = MallOrder.OrderStatus.COMPLETED
            order.completed_at = timezone.now()
            order.save(update_fields=["status", "completed_at", "updated_at"])
        self.message_user(request, "订单已完成。", level=messages.SUCCESS)
        return redirect(request.META.get("HTTP_REFERER") or reverse("admin:shop_mallorder_change", args=[order.pk]))

    @admin.action(description="通知领取（占位：后续接飞书）")
    def send_pickup_notice(self, request, queryset):
        updated = queryset.filter(pickup_notice_sent_at__isnull=True).update(pickup_notice_sent_at=timezone.now())
        self.message_user(request, f"已标记 {updated} 个订单为已通知领取；飞书通知后续接入。", level=messages.INFO)

    @admin.action(description="标记已完成")
    def mark_orders_completed(self, request, queryset):
        updated = queryset.exclude(completed_at__isnull=False).update(completed_at=timezone.now(), status=MallOrder.OrderStatus.COMPLETED)
        self.message_user(request, f"已完成 {updated} 个订单。", level=messages.SUCCESS)


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
    # 不使用 date_hierarchy：同上，且 start_at 可空；可按列表「开始时间」列排序筛选
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
