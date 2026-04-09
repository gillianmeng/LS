import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from learning_system.upload_utils import delete_replaced_file_fields


def generate_mall_order_no() -> str:
    return f"PO{timezone.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(2).upper()}"


FALLBACK_PICKUP_INSTRUCTION = (
    "总部行政部前台领取 · 工作日 9:00–18:00 · 请携带订单号与工牌"
)

DEFAULT_POINTS_EARN_RULES = """每日登录：+2 分（每个自然日首次登录计 1 次）

每学完一门课程：+5 分（在「我的学习」中标记完成）

学习相关积分每日上限：20 分（含登录与完课奖励；超出部分当日不再发放）

兑换：本页商品以标价扣减积分；已提交订单一般不退积分。更多活动奖励以公司公告为准。"""


class ShopMallSettings(models.Model):
    """单例配置：积分商城前台展示的默认文案（仅一条记录）。"""

    points_earn_rules = models.TextField(
        blank=True,
        verbose_name="积分获取规则",
        help_text="前台路径：积分商城页 →「积分规则」区块。留空则使用系统内置默认文案。建议每条规则单独一行；前 3 行会以三张卡片展示。保存后立即生效。",
    )
    points_daily_login = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="每日登录奖励（分）",
        help_text="员工每个自然日（上海时区）首次前台登录自动发放，受下方「学习类积分每日上限」约束。",
    )
    points_course_complete_default = models.PositiveSmallIntegerField(
        default=5,
        verbose_name="默认完课奖励（分）",
        help_text="当课程设置「学习完成后可获积分」为 0 时，学完该课按此默认分发放；若课程单独填写了积分则优先生效。",
    )
    points_learning_daily_cap = models.PositiveSmallIntegerField(
        default=20,
        verbose_name="学习类积分每日上限（分）",
        help_text="每日登录 + 学完课程 等学习行为合计最多发放至此分数，超出部分当日不再发放（次日清零重新计算）。",
    )

    default_pickup_instruction = models.TextField(
        default=FALLBACK_PICKUP_INSTRUCTION,
        verbose_name="默认现场领取说明",
        help_text="在结算页「现场领取」向员工展示；提交订单时会写入该笔订单。修改后仅影响新订单。",
    )

    class Meta:
        verbose_name = "积分商城：规则与说明"
        verbose_name_plural = "积分商城：规则与说明"

    def __str__(self):
        return "积分商城：规则与说明"


def get_default_pickup_instruction() -> str:
    """后台「积分商城：规则与说明」中的默认现场领取说明；未配置时使用内置兜底文案。"""
    try:
        s = ShopMallSettings.objects.first()
        if s and (s.default_pickup_instruction or "").strip():
            return s.default_pickup_instruction.strip()
    except Exception:
        pass
    return FALLBACK_PICKUP_INSTRUCTION


def get_points_earn_rules_display() -> str:
    """积分商城展示的积分获取说明；后台未填写时使用 DEFAULT_POINTS_EARN_RULES。"""
    try:
        s = ShopMallSettings.objects.first()
        if s and (s.points_earn_rules or "").strip():
            return s.points_earn_rules.strip()
    except Exception:
        pass
    return DEFAULT_POINTS_EARN_RULES


class PointsLedger(models.Model):
    """学习类积分流水（每日登录、完课）；用于防重与审计。"""

    class Source(models.TextChoices):
        DAILY_LOGIN = "daily_login", "每日登录"
        COURSE_COMPLETE = "course_complete", "课程学完"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="points_ledger_entries",
        verbose_name="员工",
    )
    amount = models.PositiveIntegerField(verbose_name="变动积分", help_text="发放为正数。")
    source = models.CharField(max_length=32, choices=Source.choices, verbose_name="来源")
    note = models.CharField(max_length=200, blank=True, verbose_name="说明")
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="points_ledger_entries",
        verbose_name="关联课程",
    )
    local_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="业务日",
        help_text="每日登录奖励对应的上海自然日，防重复发放。",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="时间")

    class Meta:
        verbose_name = "学习积分流水"
        verbose_name_plural = "学习积分流水"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "source", "local_date"],
                condition=models.Q(source="daily_login"),
                name="uniq_points_daily_login_per_employee_day",
            ),
            models.UniqueConstraint(
                fields=["employee", "source", "course"],
                condition=models.Q(source="course_complete"),
                name="uniq_points_course_complete_once",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} +{self.amount} {self.get_source_display()}"


class Product(models.Model):
    """积分商城商品。"""

    name = models.CharField(max_length=200, verbose_name="商品名称")
    image = models.ImageField(
        upload_to="shop/products/",
        blank=True,
        null=True,
        verbose_name="商品图片",
    )
    points_cost = models.PositiveIntegerField(verbose_name="所需积分")
    stock = models.PositiveIntegerField(default=0, verbose_name="库存数量")

    class Meta:
        verbose_name = "商品"
        verbose_name_plural = "商品"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk:
            prev = Product.objects.filter(pk=self.pk).only("image").first()
            if prev:
                delete_replaced_file_fields(prev, self, "image")
        super().save(*args, **kwargs)


class MallOrder(models.Model):
    """积分商城兑换订单（提交后扣积分与库存）。"""

    class DeliveryType(models.TextChoices):
        MAIL = "mail", "快递邮寄"
        PICKUP = "pickup", "现场领取"

    class OrderStatus(models.TextChoices):
        SUBMITTED = "submitted", "待处理"
        PROCESSING = "processing", "备货中"
        SHIPPED = "shipped", "配送中"
        PICKUP_READY = "pickup_ready", "待现场领取"
        COMPLETED = "completed", "已完成"
        CANCELLED = "cancelled", "已取消"

    order_no = models.CharField(max_length=40, unique=True, db_index=True, verbose_name="订单号")
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mall_orders",
        verbose_name="下单员工",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="mall_orders",
        verbose_name="商品",
    )
    product_name = models.CharField(max_length=200, verbose_name="商品名称快照")
    points_spent = models.PositiveIntegerField(verbose_name="消耗积分")

    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.SUBMITTED,
        verbose_name="订单状态",
    )
    delivery_type = models.CharField(
        max_length=10,
        choices=DeliveryType.choices,
        verbose_name="领取方式",
    )

    recipient_name = models.CharField(max_length=50, blank=True, verbose_name="收件人")
    recipient_phone = models.CharField(max_length=20, blank=True, verbose_name="联系电话")
    address_detail = models.TextField(blank=True, verbose_name="邮寄地址", help_text="省 / 市 / 区及详细地址")

    pickup_location_note = models.TextField(
        blank=True,
        verbose_name="现场领取说明",
        help_text="下单时写入的完整说明（含后台默认文案或员工自定义）。",
    )

    buyer_remark = models.CharField(max_length=500, blank=True, verbose_name="买家备注")

    logistics_company = models.CharField(max_length=100, blank=True, verbose_name="物流公司")
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name="运单号")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="下单时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "商城订单"
        verbose_name_plural = "商城订单"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = generate_mall_order_no()
            clash = MallOrder.objects.filter(order_no=self.order_no)
            if self.pk:
                clash = clash.exclude(pk=self.pk)
            while clash.exists():
                self.order_no = generate_mall_order_no()
                clash = MallOrder.objects.filter(order_no=self.order_no)
                if self.pk:
                    clash = clash.exclude(pk=self.pk)
        if self.product_id and not self.product_name:
            self.product_name = self.product.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_no} · {self.product_name}"


class MallShippingAddress(models.Model):
    """员工在积分商城保存的收货地址（用于结算预填与「我的地址」管理）。"""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mall_shipping_addresses",
        verbose_name="员工",
    )
    label = models.CharField(max_length=40, blank=True, verbose_name="标签", help_text="如：家、公司")
    recipient_name = models.CharField(max_length=50, verbose_name="收件人")
    recipient_phone = models.CharField(max_length=20, verbose_name="联系电话")
    address_detail = models.TextField(verbose_name="详细地址")
    is_default = models.BooleanField(default=False, verbose_name="默认地址")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "积分商城收货地址"
        verbose_name_plural = "积分商城收货地址"
        ordering = ["-is_default", "-updated_at"]

    def __str__(self) -> str:
        return f"{self.recipient_name} · {(self.label or '地址')[:20]}"

    def save(self, *args, **kwargs):
        if self.is_default:
            MallShippingAddress.objects.filter(employee=self.employee).exclude(pk=self.pk).update(
                is_default=False
            )
        super().save(*args, **kwargs)


class Training(models.Model):
    """线下/线上培训活动：后台发布后可出现在活动广场「培训」与首页推荐。"""

    class ApplicationsCategory(models.TextChoices):
        """与前台「我的报名」顶部标签一致，后台单选其一。"""

        TRAINING = "training", "培训"
        ACTIVITY = "activity", "活动"
        SELECTION = "selection", "评选"
        LECTURER_CERT = "lecturer_cert", "讲师级别认证"
        COURSE_AUTH = "course_auth", "课程授权认证"
        EXTERNAL = "external", "外训"
        INDEPENDENT = "independent", "独立报名"

    title = models.CharField(max_length=200, verbose_name="标题")
    summary = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="摘要",
        help_text="用于列表与首页卡片；可不填则截取正文前若干字。",
    )
    description = models.TextField(blank=True, verbose_name="详情说明")
    promotional_url = models.URLField(
        blank=True,
        verbose_name="宣传/资料链接",
        help_text="选填。可填飞书文档、活动介绍页、海报网页等；员工在列表与详情页可点击跳转。与下方「外链报名」用途不同。",
    )
    promotional_link_label = models.CharField(
        max_length=40,
        blank=True,
        verbose_name="资料链接按钮文字",
        help_text="选填。不填则前台显示「查看活动资料」。",
    )
    cover = models.ImageField(
        upload_to="shop/trainings/",
        blank=True,
        null=True,
        verbose_name="封面图",
    )

    start_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="开始时间",
        help_text="选填。若不填具体时间，请务必填写下方「时间安排说明」（如：多场次、待定）。",
    )
    end_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="结束时间",
        help_text="选填；仅填开始时间时表示单次活动开始时刻，结束以说明或后台为准。",
    )
    schedule_note = models.TextField(
        blank=True,
        verbose_name="时间安排说明",
        help_text="灵活排期时在此说明：例「每周三 14:00 共四次」「时间另行通知」。可与上方起止时间同时填写（前台会一并展示）。",
    )
    registration_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="报名截止时间",
        help_text="留空表示不单独限制；若未填结束时间，报名是否开放主要受本字段与「发布」控制。",
    )

    location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="地点 / 形式说明",
        help_text="例：总部 3 楼会议室、或「线上」并可在下方填写链接。",
    )
    online_meeting_url = models.URLField(blank=True, verbose_name="线上会议链接")

    instructor_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="讲师",
        help_text="可填姓名或「某某团队」；前台详情与列表展示。",
    )
    registration_external_url = models.URLField(
        blank=True,
        verbose_name="外链报名地址",
        help_text="选填。若填写，前台将展示「外链报名」入口（可与站内报名并存，由您自行约定使用方式）。",
    )

    max_participants = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="人数上限",
        help_text="留空表示不限制；统计待审核+已通过占用名额。",
    )

    is_published = models.BooleanField(
        default=False,
        verbose_name="在活动广场展示",
        help_text="勾选后：对员工可见并出现在活动广场「培训」分类（仍受时间筛选影响）。",
    )
    is_home_featured = models.BooleanField(
        default=False,
        verbose_name="首页推荐",
        help_text="勾选后：出现在网站首页「培训推荐」区块（须同时勾选上方展示）。",
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="排序",
        help_text="数字越小越靠前。",
    )
    applications_category = models.CharField(
        max_length=32,
        choices=ApplicationsCategory.choices,
        default=ApplicationsCategory.TRAINING,
        verbose_name="「我的报名」分类标签",
        help_text="必选其一，与员工前台「我的报名」七个筛选标签一致：培训、活动、评选、讲师级别认证、课程授权认证、外训、独立报名。决定本条出现在哪一个标签下（已加入/未加入均按此筛选）。是否出现在活动广场由下方「在活动广场展示」控制。",
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "培训活动"
        verbose_name_plural = "培训活动"
        ordering = ["sort_order", "-start_at", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def clean(self):
        super().clean()
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise ValidationError({"end_at": "结束时间不能早于开始时间。"})
        note = (self.schedule_note or "").strip()
        if self.end_at and not self.start_at:
            raise ValidationError({"start_at": "若填写结束时间，请先填写开始时间。"})
        if self.start_at is None and self.end_at is None and not note:
            raise ValidationError(
                "请至少填写「时间安排说明」，或填写「开始时间」（可与结束时间一起填写）。"
            )

    def schedule_status(self, now=None) -> str:
        """not_started / ongoing / ended / flexible（无固定起止时间）。"""
        now = now or timezone.now()
        if self.start_at is None:
            return "flexible"
        if now < self.start_at:
            return "not_started"
        if self.end_at is not None and now > self.end_at:
            return "ended"
        return "ongoing"

    def registration_is_open(self, now=None) -> bool:
        now = now or timezone.now()
        if not self.is_published:
            return False
        if self.end_at is not None and now > self.end_at:
            return False
        if self.registration_deadline and now > self.registration_deadline:
            return False
        return True

    def occupied_slots(self) -> int:
        return self.registrations.filter(
            status__in=(
                TrainingRegistration.Status.PENDING,
                TrainingRegistration.Status.APPROVED,
            )
        ).count()

    def has_capacity(self) -> bool:
        if not self.max_participants:
            return True
        return self.occupied_slots() < self.max_participants

    def save(self, *args, **kwargs):
        if self.pk:
            prev = Training.objects.filter(pk=self.pk).only("cover").first()
            if prev:
                delete_replaced_file_fields(prev, self, "cover")
        super().save(*args, **kwargs)


class TrainingRegistration(models.Model):
    """员工培训报名记录；后台可审核。"""

    class Status(models.TextChoices):
        PENDING = "pending", "待审核"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已拒绝"
        CANCELLED = "cancelled", "已取消"

    training = models.ForeignKey(
        Training,
        on_delete=models.CASCADE,
        related_name="registrations",
        verbose_name="培训活动",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="training_registrations",
        verbose_name="报名人",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="状态",
    )
    message = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="报名留言",
        help_text="员工选填：部门、备注需求等。",
    )
    admin_note = models.TextField(blank=True, verbose_name="管理员备注")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="报名时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "培训报名"
        verbose_name_plural = "培训报名"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["training", "employee"],
                name="uniq_training_registration_per_employee",
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.training.title} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        old_status = None
        if self.pk:
            row = TrainingRegistration.objects.filter(pk=self.pk).only("status").first()
            if row:
                old_status = row.status
        super().save(*args, **kwargs)
        if self.status in (self.Status.APPROVED, self.Status.REJECTED) and old_status != self.status:
            _notify_training_registration_review(self)


def _notify_training_registration_review(registration: "TrainingRegistration") -> None:
    """审核为通过或拒绝时，向报名人写入站内通知（顶栏铃铛）。"""
    from django.urls import reverse

    from users.models import Notification

    training = registration.training
    if registration.status == TrainingRegistration.Status.APPROVED:
        title = f"培训报名已通过：{training.title}"
        body = "管理员已通过你的报名，请前往活动详情查看时间与安排。"
    elif registration.status == TrainingRegistration.Status.REJECTED:
        title = f"培训报名未通过：{training.title}"
        body = "你的报名未通过审核。"
        note = (registration.admin_note or "").strip()
        if note:
            body = f"{body} 备注：{note}"[:500]
    else:
        return

    Notification.objects.create(
        employee=registration.employee,
        title=title[:200],
        body=body[:500],
        link=reverse("shop:training_detail", args=[training.pk]),
    )


class ExchangeRecord(models.Model):
    """积分兑换记录。"""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exchange_records",
        verbose_name="员工",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="exchange_records",
        verbose_name="商品",
    )
    exchanged_at = models.DateTimeField(auto_now_add=True, verbose_name="兑换时间")
    points_spent = models.PositiveIntegerField(verbose_name="消耗积分")

    class Meta:
        verbose_name = "兑换记录"
        verbose_name_plural = "兑换记录"
        ordering = ["-exchanged_at"]

    def __str__(self):
        return f"{self.employee} 兑换 {self.product} ({self.points_spent} 分)"
