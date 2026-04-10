from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from learning_system.upload_utils import delete_replaced_file_fields

# 考试在学习任务中的默认「距开考/距截止」提醒天数（与必修课程默认一致）
EXAM_LEARNING_TASK_REMINDER_DAYS = 7


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
    required_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="必修完成期限",
        help_text="仅当课程类型为「必修」时生效：学员须在此时间前学完；留空表示不设具体期限（前台仍显示为指派必修）。",
    )
    required_reminder_days = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="提醒窗口（天）",
        help_text="仅必修有效：距「完成期限」前若干天起，知识殿堂「学习任务」等处以醒目样式提醒。留空则按 7 天。",
        validators=[MinValueValidator(1), MaxValueValidator(366)],
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

    def get_required_deadline_state(self, *, is_completed: bool) -> dict | None:
        """必修课程期限与提醒窗口状态；非必修返回 None。"""
        if self.course_type != self.CourseType.REQUIRED:
            return None
        dl = self.required_deadline
        if is_completed:
            if dl:
                local_dl = timezone.localtime(dl)
                sub = f"已在期限（{local_dl.strftime('%Y-%m-%d %H:%M')}）前完成"
            else:
                sub = "指派必修已学完"
            return {
                "kind": "completed",
                "label": "已完成",
                "subline": sub,
                "tone": "success",
                "sort_priority": 9,
                "deadline": dl,
                "in_reminder_window": False,
            }
        window_days = self.required_reminder_days or 7
        now = timezone.now()
        if not dl:
            return {
                "kind": "nodl",
                "label": "须完成",
                "subline": "指派必修 · 请尽快学完",
                "tone": "mandatory",
                "sort_priority": 3,
                "deadline": None,
                "in_reminder_window": True,
                "sort_ts": self.created_at,
            }
        local_dl = timezone.localtime(dl)
        dl_str = local_dl.strftime("%Y-%m-%d %H:%M")
        window_start = dl - timedelta(days=window_days)
        in_window = now >= window_start
        if now > dl:
            return {
                "kind": "overdue",
                "label": "已逾期",
                "subline": f"须在 {dl_str} 前完成",
                "tone": "danger",
                "sort_priority": 0,
                "deadline": dl,
                "in_reminder_window": True,
                "days_left": None,
                "sort_ts": dl,
            }
        delta = dl - now
        days_left = max(0, delta.days)
        if in_window:
            return {
                "kind": "urgent",
                "label": "临期须完成",
                "subline": f"截止 {dl_str}" + (f" · 剩余 {days_left} 天" if days_left else " · 今日截止"),
                "tone": "warning",
                "sort_priority": 1,
                "deadline": dl,
                "in_reminder_window": True,
                "days_left": days_left,
                "sort_ts": dl,
            }
        days_until_reminder = max(0, int((window_start - now).total_seconds() // 86400))
        rem_hint = (
            f"约 {days_until_reminder} 天后进入 {window_days} 天提醒窗口"
            if days_until_reminder
            else f"即将进入 {window_days} 天提醒窗口"
        )
        return {
            "kind": "scheduled",
            "label": "须完成",
            "subline": f"请于 {dl_str} 前完成 · {rem_hint}",
            "tone": "info",
            "sort_priority": 2,
            "deadline": dl,
            "in_reminder_window": False,
            "days_left": days_left,
            "sort_ts": dl,
        }


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

    def get_learning_task_state(self, employee) -> dict | None:
        """正式考试进入「学习任务」：按开放时间与截止前提醒窗口；已通过者不返回。"""
        if self.kind != self.Kind.EXAM or not self.is_published:
            return None

        rec = ExamRecord.objects.filter(employee=employee, exam=self).first()
        if rec and rec.score is not None and rec.score >= self.pass_score:
            return None

        now = timezone.now()
        rtd = timedelta(days=EXAM_LEARNING_TASK_REMINDER_DAYS)
        sched = self.schedule_status()

        if sched == "done":
            ends = self.ends_at
            ends_s = timezone.localtime(ends).strftime("%Y-%m-%d %H:%M") if ends else "—"
            if rec and rec.score is not None:
                sub_tail = f"得分 {rec.score}，未达及格线 {self.pass_score}"
            else:
                sub_tail = "未参加或未录入成绩"
            return {
                "kind": "exam_ended",
                "label": "考试已结束",
                "subline": f"已于 {ends_s} 结束 · {sub_tail}",
                "tone": "danger",
                "sort_priority": 0,
                "in_reminder_window": True,
                "sort_ts": ends or now,
            }

        if sched == "pending" and self.starts_at:
            start = self.starts_at
            win_start = start - rtd
            in_w = now >= win_start
            loc_s = timezone.localtime(start).strftime("%Y-%m-%d %H:%M")
            days = max(0, (start - now).days)
            sub = f"将于 {loc_s} 开始"
            if days:
                sub += f" · 还有 {days} 天"
            else:
                sub += " · 今日开考"
            return {
                "kind": "exam_pending",
                "label": "待开考提醒" if in_w else "待开考",
                "subline": sub + f" · 考前 {EXAM_LEARNING_TASK_REMINDER_DAYS} 天起提醒",
                "tone": "warning" if in_w else "info",
                "sort_priority": 1 if in_w else 4,
                "in_reminder_window": in_w,
                "sort_ts": start,
            }

        if self.ends_at:
            loc_e = timezone.localtime(self.ends_at).strftime("%Y-%m-%d %H:%M")
            win_end = self.ends_at - rtd
            in_w = now >= win_end
            days_left = max(0, (self.ends_at - now).days)
            sub = f"开放至 {loc_e}"
            if days_left:
                sub += f" · 剩余 {days_left} 天"
            else:
                sub += " · 今日截止"
            sub += f" · 截止前 {EXAM_LEARNING_TASK_REMINDER_DAYS} 天起提醒"
            return {
                "kind": "exam_ongoing",
                "label": "临期须参考" if in_w else "须参加考试",
                "subline": sub,
                "tone": "warning" if in_w else "info",
                "sort_priority": 1 if in_w else 3,
                "in_reminder_window": in_w,
                "sort_ts": self.ends_at,
            }

        return {
            "kind": "exam_ongoing_open",
            "label": "须参加考试",
            "subline": "考试进行中 · 不限定截止时间，请尽快完成",
            "tone": "mandatory",
            "sort_priority": 3,
            "in_reminder_window": True,
            "sort_ts": self.created_at,
        }


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


class LearningPreference(models.Model):
    """学员学习提醒与完课反馈等偏好（一对一）。"""

    employee = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_preference",
        verbose_name="员工",
    )
    daily_reminder_enabled = models.BooleanField(
        default=True,
        verbose_name="每日学习提醒",
        help_text="开启后，当您仍有未学完课程时，系统每日最多通过站内通知提醒一次（上海自然日）。",
    )
    last_daily_reminder_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="上次每日提醒业务日",
        help_text="防重复；由系统自动维护。",
    )
    points_notification_enabled = models.BooleanField(
        default=True,
        verbose_name="学习类积分站内通知",
        help_text="关闭后，获得每日登录、完课积分时不再写入顶栏「通知」，积分仍正常到账。",
    )
    verbose_completion_message = models.BooleanField(
        default=True,
        verbose_name="完课详细提示",
        help_text="关闭后，标记学完时仅显示简短提示，不再展示积分细则与原因说明。",
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "学习提醒与完课设置"
        verbose_name_plural = "学习提醒与完课设置"

    def __str__(self) -> str:
        return f"{self.employee_id} 的学习偏好"
