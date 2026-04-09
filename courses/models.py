from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from learning_system.upload_utils import delete_replaced_file_fields


class CourseCategory(models.Model):
    """前台课程目录（两级：一级栏目 → 二级子类），与「在线课堂」左侧分类一致。"""

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        verbose_name="上级栏目",
    )
    name = models.CharField(max_length=100, verbose_name="名称")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="排序")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "课程目录"
        verbose_name_plural = "课程目录"

    def __str__(self) -> str:
        if self.parent_id:
            return f"{self.parent.name} / {self.name}"
        return self.name


class Course(models.Model):
    """培训课程。"""

    class CourseType(models.TextChoices):
        REQUIRED = "required", "必修"
        ELECTIVE = "elective", "选修"

    class ContentKind(models.TextChoices):
        VIDEO = "video", "视频"
        ARTICLE = "article", "文章"

    name = models.CharField(max_length=200, verbose_name="课程名称")
    description = models.TextField(blank=True, verbose_name="简介")
    content_kind = models.CharField(
        max_length=10,
        choices=ContentKind.choices,
        default=ContentKind.VIDEO,
        verbose_name="内容形式",
        help_text="视频课上传/填写视频；图文课可使用下方「原文链接」或「文章正文」。",
    )
    article_url = models.URLField(
        blank=True,
        verbose_name="文章原文链接",
        help_text="选填。填写后学员点击在新窗口打开该地址，可保留飞书/语雀/官网等原有排版；不必把全文粘贴进正文。可与简介、站内正文搭配使用。",
    )
    article_body = models.TextField(
        blank=True,
        verbose_name="文章正文",
        help_text="站内直接展示的纯文本；从外部粘贴可能丢格式，可改用上方「原文链接」。",
    )
    video_file = models.FileField(
        upload_to="courses/videos/",
        blank=True,
        null=True,
        verbose_name="视频文件",
    )
    video_url = models.URLField(blank=True, verbose_name="视频链接")
    reward_points = models.PositiveIntegerField(default=0, verbose_name="学习完成后可获积分")
    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        verbose_name="课程类型",
    )
    thumbnail = models.ImageField(
        upload_to="courses/covers/",
        blank=True,
        null=True,
        verbose_name="封面图",
    )
    cover_url = models.URLField(blank=True, verbose_name="封面图链接")
    view_count = models.PositiveIntegerField(default=0, verbose_name="浏览次数")
    duration_minutes = models.PositiveIntegerField(default=0, verbose_name="课程时长（分钟）")
    is_recommended = models.BooleanField(default=False, verbose_name="是否推荐")
    exclude_from_hot_ranking = models.BooleanField(
        default=False,
        verbose_name="不参与「最热课程」排行",
        help_text="勾选后：仍可在首页「推荐」「最新」等展示，但不会出现于「最热课程」排序中（适合仅作展示、不需拼浏览量的课程）。",
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    catalog_category = models.ForeignKey(
        CourseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses",
        verbose_name="课程目录",
        help_text="选至二级子类，用于首页与全部课程左侧分类筛选。",
    )

    class Meta:
        verbose_name = "课程"
        verbose_name_plural = "课程"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk:
            prev = Course.objects.filter(pk=self.pk).only("video_file", "thumbnail").first()
            if prev:
                delete_replaced_file_fields(prev, self, "video_file", "thumbnail")
        super().save(*args, **kwargs)

    @property
    def duration_display(self) -> str:
        m = self.duration_minutes
        if m >= 60:
            h, rem = divmod(m, 60)
            return f"{h} 小时 {rem} 分钟" if rem else f"{h} 小时"
        return f"{m} 分钟"


class Instructor(models.Model):
    """首页「专业讲师」展示用，后台 Courses 应用下维护。"""

    name = models.CharField(max_length=50, verbose_name="姓名")
    title = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="职称/标签",
        help_text="如：高级讲师、认证讲师",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="instructor_entries",
        verbose_name="关联员工",
        help_text="选填。未上传下方「头像」且未填外链时，使用该股员工的个人头像。",
    )
    photo = models.ImageField(
        upload_to="courses/instructors/",
        blank=True,
        null=True,
        verbose_name="头像",
        help_text="管理员上传则优先用于首页展示；留空时可回退到关联员工的个人头像。",
    )
    photo_url = models.URLField(blank=True, verbose_name="头像链接", help_text="不上传文件时可填外链")
    sort_order = models.PositiveSmallIntegerField(default=0, verbose_name="排序", help_text="数字越小越靠前")
    is_published = models.BooleanField(default=True, verbose_name="在首页展示")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "讲师"
        verbose_name_plural = "讲师"
        ordering = ["sort_order", "id"]

    def __str__(self):
        return self.name

    @property
    def display_avatar_url(self) -> str | None:
        """首页展示：后台头像 / 外链 > 关联员工个人头像。"""
        if self.photo:
            return self.photo.url
        pu = (self.photo_url or "").strip()
        if pu:
            return pu
        if self.employee_id:
            emp = self.employee
            if emp.avatar:
                return emp.avatar.url
        return None

    def save(self, *args, **kwargs):
        if self.pk:
            prev = Instructor.objects.filter(pk=self.pk).only("photo").first()
            if prev:
                delete_replaced_file_fields(prev, self, "photo")
        super().save(*args, **kwargs)


class Exam(models.Model):
    """考试或练习，对应前台「测练中心 — 我的考试」。"""

    class Kind(models.TextChoices):
        EXAM = "exam", "考试"
        PRACTICE = "practice", "练习"

    title = models.CharField(max_length=200, verbose_name="名称")
    description = models.TextField(blank=True, verbose_name="说明")
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.EXAM,
        verbose_name="类型",
    )
    starts_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="开始时间",
        help_text="不填表示发布后即可参与",
    )
    ends_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="结束时间",
        help_text="不填表示不限制截止时间",
    )
    duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="答题限时（分钟）",
        help_text="进入考试后的作答时长上限；不填表示不限。与开放时间段相互独立，可随时在后台修改。",
    )
    pass_score = models.PositiveSmallIntegerField(
        default=60,
        verbose_name="及格分",
        help_text="用于判定「通过/未通过」；练习也可沿用。",
    )
    max_score = models.PositiveSmallIntegerField(default=100, verbose_name="满分")
    entry_url = models.URLField(
        blank=True,
        verbose_name="答题入口链接",
        help_text="可选，跳转外部考试或问卷",
    )
    is_published = models.BooleanField(default=True, verbose_name="发布")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="创建时间")

    class Meta:
        verbose_name = "考试/练习"
        verbose_name_plural = "考试与练习"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def schedule_status(self) -> str:
        """相对当前时间：待开始 pending / 进行中 ongoing / 已结束 done。"""
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return "pending"
        if self.ends_at and now > self.ends_at:
            return "done"
        return "ongoing"


class ExamRecord(models.Model):
    """员工在某场考试中的成绩（可后台录入，后续可接在线答题）。"""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exam_records",
        verbose_name="员工",
    )
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name="考试",
    )
    score = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="得分")
    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="交卷时间",
        help_text="可后台手动填写",
    )

    class Meta:
        verbose_name = "考试成绩"
        verbose_name_plural = "考试成绩"
        ordering = ["-submitted_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["employee", "exam"], name="unique_employee_exam_record"),
        ]

    def __str__(self):
        return f"{self.employee} — {self.exam}"

    def passed(self) -> bool | None:
        """是否通过：无分返回 None。"""
        if self.score is None:
            return None
        return self.score >= self.exam.pass_score


class LearningRecord(models.Model):
    """员工课程学习记录。"""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_records",
        verbose_name="员工",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="learning_records",
        verbose_name="课程",
    )
    progress_percentage = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="学习进度百分比",
    )
    is_completed = models.BooleanField(default=False, verbose_name="是否已完成")
    updated_at = models.DateTimeField(default=timezone.now, verbose_name="最近学习时间")

    class Meta:
        verbose_name = "学习记录"
        verbose_name_plural = "学习记录"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "course"],
                name="unique_employee_course_learning",
            ),
        ]

    def save(self, *args, **kwargs):
        old_completed: bool | None = None
        if self.pk:
            prev = LearningRecord.objects.filter(pk=self.pk).only("is_completed").first()
            if prev:
                old_completed = prev.is_completed
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
        self._points_granted_on_complete = 0
        self._points_grant_reason = ""
        if self.is_completed and old_completed is not True:
            try:
                from shop.points_awards import try_award_course_completion

                granted, reason = try_award_course_completion(self.employee, self.course)
                self._points_granted_on_complete = granted
                self._points_grant_reason = reason
            except Exception:
                import logging

                logging.getLogger(__name__).exception("课程学完积分发放失败")

    def __str__(self):
        return f"{self.employee} - {self.course}"
