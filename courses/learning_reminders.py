"""每日学习提醒：在仍有未完课时写入站内通知（受 LearningPreference 控制）。"""

from __future__ import annotations

import logging

from django.urls import reverse

logger = logging.getLogger(__name__)


def process_daily_study_reminder(user) -> None:
    """每个请求最多为当日写一条提醒逻辑（按偏好与业务日去重）。"""
    if not getattr(user, "is_authenticated", False):
        return

    from shop.points_awards import shanghai_today

    from .models import LearningPreference, LearningRecord

    try:
        pref, _ = LearningPreference.objects.get_or_create(employee=user)
    except Exception:
        logger.exception("读取 LearningPreference 失败")
        return

    if not pref.daily_reminder_enabled:
        return

    today = shanghai_today()
    if pref.last_daily_reminder_date == today:
        return

    try:
        incomplete = LearningRecord.objects.filter(employee=user, is_completed=False).count()
    except Exception:
        logger.exception("统计未完课数量失败")
        return

    if incomplete > 0:
        try:
            from users.models import Notification

            Notification.objects.create(
                employee=user,
                title="今日学习提醒",
                body=f"您还有 {incomplete} 门课程待学完，可在「自学计划」中继续学习。",
                link=reverse("courses:my_courses"),
            )
        except Exception:
            logger.exception("写入每日学习提醒通知失败")

    pref.last_daily_reminder_date = today
    try:
        pref.save(update_fields=["last_daily_reminder_date"])
    except Exception:
        logger.exception("更新 last_daily_reminder_date 失败")
