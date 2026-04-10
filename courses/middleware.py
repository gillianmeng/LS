"""课程应用中间件：每日学习提醒（站内通知）。"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class DailyStudyReminderMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = getattr(request, "path", "") or ""
        if path.startswith("/admin"):
            return self.get_response(request)
        if getattr(request, "user", None) and request.user.is_authenticated:
            try:
                from .learning_reminders import process_daily_study_reminder

                process_daily_study_reminder(request.user)
            except Exception:
                logger.exception("每日学习提醒处理失败")
        return self.get_response(request)
