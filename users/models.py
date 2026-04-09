from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from learning_system.upload_utils import delete_replaced_file_fields


class LeaderboardConfig(models.Model):
    """首页「榜单排名」与「我的学习」侧栏积分榜（固定单条，在后台「积分榜显示设置」中编辑）。"""

    time_range_label = models.CharField(
        max_length=50,
        default="全部时间",
        verbose_name="时间范围标签",
        help_text="展示在积分榜旁，如：全部时间、本月、本季度（当前仍按员工累计积分余额排序）。",
    )
    home_rank_count = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
        verbose_name="首页上榜人数",
        help_text="首页双列平分展示，例如 10 即左 1–5、右 6–10 名。",
    )
    sidebar_rank_count = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        verbose_name="「我的学习」侧栏人数",
        help_text="侧栏排行榜展示前若干名，不超过首页上榜人数。",
    )
    exclude_staff = models.BooleanField(
        default=True,
        verbose_name="排除管理员账号",
        help_text="勾选后不计入 is_staff 与超级用户。",
    )
    footnote = models.CharField(
        max_length=120,
        blank=True,
        default="（不含系统管理员）",
        verbose_name="说明脚注",
        help_text="显示在标签旁；留空则不显示。",
    )

    class Meta:
        verbose_name = "积分榜显示设置"
        verbose_name_plural = "积分榜显示设置"

    def __str__(self):
        return "积分榜显示设置"

    @property
    def display_footnote(self) -> str:
        """前台展示用脚注：已包含管理员时不再显示默认的「不含系统管理员」。"""
        t = (self.footnote or "").strip()
        if not t:
            return ""
        if not self.exclude_staff and t == "（不含系统管理员）":
            return ""
        return t

    @classmethod
    def get_solo(cls):
        cls.objects.get_or_create(
            pk=1,
            defaults={
                "time_range_label": "全部时间",
                "home_rank_count": 10,
                "sidebar_rank_count": 6,
                "exclude_staff": True,
                "footnote": "（不含系统管理员）",
            },
        )
        return cls.objects.get(pk=1)


class SiteBannerConfig(models.Model):
    """各页顶通栏 Banner，后台单条配置；未上传时使用默认静态图。"""

    banner_home = models.ImageField(
        upload_to="site_banners/home/",
        blank=True,
        null=True,
        verbose_name="首页 Banner",
        help_text="建议 1280×360 px（宽×高），PNG/JPG。对应前台主内容区全宽（max-w-7xl），比例约 3.56:1。",
    )
    banner_my_learning = models.ImageField(
        upload_to="site_banners/my_learning/",
        blank=True,
        null=True,
        verbose_name="我的学习 Banner",
        help_text="建议 1200×300 px（约 4:1）。该页为三栏布局，桌面端 Banner 在中栏（约半宽），图为 object-cover，重要内容请居中，避免左右被裁。",
    )
    banner_points_mall = models.ImageField(
        upload_to="site_banners/points_mall/",
        blank=True,
        null=True,
        verbose_name="积分商城 Banner",
        help_text="【比例固定为 宽:高 = 10:3，横图】推荐导出尺寸 1200×360 px（或 2400×720 @2x）。"
        "勿用正方形（如 1200×1200），否则左右或上下会被大幅裁切。"
        "前台左侧通栏为 10:3 + object-cover，重要视觉请放在中间安全区。",
    )
    banner_activity_plaza = models.ImageField(
        upload_to="site_banners/activity_plaza/",
        blank=True,
        null=True,
        verbose_name="活动广场 Banner",
        help_text="与积分商城相同：比例 10:3，推荐 1200×360 px（或 2400×720 @2x），勿用正方形；主体居中。",
    )

    class Meta:
        verbose_name = "页面 Banner 图"
        verbose_name_plural = "页面 Banner 图"

    def __str__(self):
        return "页面 Banner 图"

    @classmethod
    def get_solo(cls):
        cls.objects.get_or_create(pk=1)
        return cls.objects.get(pk=1)

    def save(self, *args, **kwargs):
        if self.pk:
            prev = SiteBannerConfig.objects.filter(pk=self.pk).only(
                "banner_home",
                "banner_my_learning",
                "banner_points_mall",
                "banner_activity_plaza",
            ).first()
            if prev:
                delete_replaced_file_fields(
                    prev,
                    self,
                    "banner_home",
                    "banner_my_learning",
                    "banner_points_mall",
                    "banner_activity_plaza",
                )
        super().save(*args, **kwargs)


class Employee(AbstractUser):
    """企业内部员工用户，以工号登录。"""

    username = None
    emp_id = models.CharField(max_length=50, unique=True, verbose_name="工号")
    real_name = models.CharField(max_length=50, verbose_name="真实姓名")
    dept_level_1 = models.CharField(max_length=100, blank=True, verbose_name="一级部门")
    dept_level_2 = models.CharField(max_length=100, blank=True, verbose_name="二级部门")
    dept_level_3 = models.CharField(max_length=100, blank=True, verbose_name="三级部门")
    dept_level_4 = models.CharField(max_length=100, blank=True, verbose_name="四级部门")
    job_level = models.CharField(max_length=50, blank=True, verbose_name="职级")
    hire_date = models.DateField(null=True, blank=True, verbose_name="入职时间")
    points_balance = models.PositiveIntegerField(default=0, verbose_name="当前积分余额")
    feishu_open_id = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        verbose_name="飞书 open_id",
        help_text="与飞书账号绑定，用于飞书登录",
    )
    feishu_union_id = models.CharField(
        max_length=128, blank=True, default="", verbose_name="飞书 union_id"
    )
    avatar = models.ImageField(
        upload_to="profiles/avatars/",
        blank=True,
        null=True,
        verbose_name="头像",
        help_text="「我的学习」个人卡片展示；建议正方形图片。",
    )
    signature = models.TextField(
        blank=True,
        max_length=500,
        verbose_name="签名档",
        help_text="一句个性签名，显示在个人卡片。",
    )

    USERNAME_FIELD = "emp_id"
    REQUIRED_FIELDS = ["real_name"]

    class Meta:
        verbose_name = "员工"
        verbose_name_plural = "员工"

    def __str__(self):
        return f"{self.real_name} ({self.emp_id})"

    def save(self, *args, **kwargs):
        if self.pk:
            prev = Employee.objects.filter(pk=self.pk).only("avatar").first()
            if prev:
                delete_replaced_file_fields(prev, self, "avatar")
        super().save(*args, **kwargs)


class Notification(models.Model):
    """站内通知（顶栏铃铛）。接收人留空表示全体用户。"""

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收人",
        null=True,
        blank=True,
        help_text="留空表示全体用户；指定则仅该员工可见。",
    )
    title = models.CharField(max_length=200, verbose_name="标题")
    body = models.CharField(max_length=500, blank=True, verbose_name="摘要")
    link = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="链接",
        help_text="站内路径，如 /shop/mall/ 或 /courses/my/",
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="已读时间",
        help_text="仅单人通知使用；全体通知的已读见「通知已读记录」。",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "站内通知"
        verbose_name_plural = "站内通知"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def is_read_by(self, user) -> bool:
        """当前用户是否已读（单人看 read_at/已读表，全体只看已读表）。"""
        if not user.is_authenticated:
            return True
        if self.employee_id and self.employee_id != user.id:
            return True
        if self.employee_id == user.id and self.read_at:
            return True
        return NotificationRead.objects.filter(notification=self, employee=user).exists()


class NotificationRead(models.Model):
    """用户对某条通知的已读记录（全体通知每人一行）。"""

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="read_records",
        verbose_name="通知",
    )
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="notification_reads",
        verbose_name="员工",
    )
    read_at = models.DateTimeField(auto_now_add=True, verbose_name="已读时间")

    class Meta:
        verbose_name = "通知已读记录"
        verbose_name_plural = "通知已读记录"
        constraints = [
            models.UniqueConstraint(
                fields=["notification", "employee"],
                name="unique_notification_employee_read",
            )
        ]

    def __str__(self):
        return f"{self.employee_id} ← {self.notification_id}"
