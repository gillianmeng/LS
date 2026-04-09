"""课程/考试相关表单（主要用于管理后台）。"""

import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Exam


def _combine_local_date_time(d: datetime.date | None, t: datetime.time | None) -> datetime.datetime | None:
    if d is None:
        return None
    if t is None:
        t = datetime.time.min
    naive = datetime.datetime.combine(d, t)
    return timezone.make_aware(naive, timezone.get_current_timezone())


class ExamAdminForm(forms.ModelForm):
    """将开始/结束时间拆成日期 + 时刻，便于在后台自由调节（仍存为 DateTimeField）。"""

    start_date = forms.DateField(
        required=False,
        label="开始日期",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    start_time = forms.TimeField(
        required=False,
        label="开始时刻",
        widget=forms.TimeInput(attrs={"type": "time", "step": "1"}),
        help_text="可与日期分开改；不填时刻则视为当天 0:00。",
    )
    end_date = forms.DateField(
        required=False,
        label="结束日期",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_time = forms.TimeField(
        required=False,
        label="结束时刻",
        widget=forms.TimeInput(attrs={"type": "time", "step": "1"}),
        help_text="不填时刻则视为当天 0:00；仅填结束日期也可表示截止日。",
    )

    class Meta:
        model = Exam
        fields = (
            "title",
            "kind",
            "description",
            "is_published",
            "duration_minutes",
            "max_score",
            "pass_score",
            "entry_url",
            "created_at",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        if inst.pk:
            if inst.starts_at:
                lt = timezone.localtime(inst.starts_at)
                self.initial.setdefault("start_date", lt.date())
                self.initial.setdefault("start_time", lt.time().replace(microsecond=0))
            if inst.ends_at:
                lt = timezone.localtime(inst.ends_at)
                self.initial.setdefault("end_date", lt.date())
                self.initial.setdefault("end_time", lt.time().replace(microsecond=0))

    def clean(self):
        data = super().clean()
        sd, st = data.get("start_date"), data.get("start_time")
        ed, et = data.get("end_date"), data.get("end_time")

        if st and not sd:
            raise ValidationError({"start_time": "已填写开始时刻时，请先选择开始日期。"})
        if et and not ed:
            raise ValidationError({"end_time": "已填写结束时刻时，请先选择结束日期。"})

        starts_at = _combine_local_date_time(sd, st)
        ends_at = _combine_local_date_time(ed, et)

        if starts_at and ends_at and starts_at >= ends_at:
            raise ValidationError("结束时间必须晚于开始时间。")

        self.instance.starts_at = starts_at
        self.instance.ends_at = ends_at
        return data
