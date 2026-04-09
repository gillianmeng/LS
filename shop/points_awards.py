"""学习相关积分发放：每日登录、课程学完；受「学习类积分每日上限」约束。"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

if TYPE_CHECKING:
    from users.models import Employee

logger = logging.getLogger(__name__)


def shanghai_today() -> datetime.date:
    """Asia/Shanghai 当前自然日。"""
    return timezone.now().astimezone(ZoneInfo("Asia/Shanghai")).date()


def shanghai_day_bounds(d: datetime.date) -> tuple[datetime.datetime, datetime.datetime]:
    sh = ZoneInfo("Asia/Shanghai")
    start = datetime.datetime.combine(d, datetime.time.min).replace(tzinfo=sh)
    end = start + datetime.timedelta(days=1)
    return start, end


def _get_mall_points_settings() -> dict:
    from .models import ShopMallSettings

    defaults = {
        "daily_login": 2,
        "course_complete_default": 5,
        "learning_daily_cap": 20,
    }
    try:
        s = ShopMallSettings.objects.first()
        if s:
            return {
                "daily_login": int(s.points_daily_login),
                "course_complete_default": int(s.points_course_complete_default),
                "learning_daily_cap": int(s.points_learning_daily_cap),
            }
    except Exception:
        logger.exception("读取积分数值配置失败，使用内置默认值")
    return defaults


def _learning_points_earned_today(employee: Employee) -> int:
    from .models import PointsLedger

    d = shanghai_today()
    start, end = shanghai_day_bounds(d)
    total = (
        PointsLedger.objects.filter(
            employee=employee,
            source__in=(
                PointsLedger.Source.DAILY_LOGIN,
                PointsLedger.Source.COURSE_COMPLETE,
            ),
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(s=Sum("amount"))["s"]
        or 0
    )
    return int(total)


def grant_learning_points(
    employee: Employee,
    amount: int,
    source: str,
    *,
    course=None,
    local_date: datetime.date | None = None,
    note: str = "",
) -> tuple[int, str]:
    """
    在当日「学习类」上限内发放积分；返回 (实际发放数, 原因码 ok|zero|daily_cap)。
    """
    from users.models import Employee as EmployeeModel

    from .models import PointsLedger

    if amount <= 0:
        return 0, "zero"
    cfg = _get_mall_points_settings()
    cap = cfg["learning_daily_cap"]
    earned = _learning_points_earned_today(employee)
    room = max(0, cap - earned)
    actual = min(int(amount), room)
    if actual <= 0:
        return 0, "daily_cap"
    note = (note or "")[:200]
    with transaction.atomic():
        EmployeeModel.objects.select_for_update().only("id").get(pk=employee.pk)
        PointsLedger.objects.create(
            employee=employee,
            amount=actual,
            source=source,
            course=course,
            local_date=local_date,
            note=note,
        )
        EmployeeModel.objects.filter(pk=employee.pk).update(points_balance=F("points_balance") + actual)
    employee.refresh_from_db(fields=["points_balance"])
    return actual, "ok"


def try_award_daily_login(employee: Employee) -> tuple[int, str]:
    """每个自然日（上海）首次登录发放；已发过则 (0, already)。"""
    from .models import PointsLedger

    today = shanghai_today()
    if PointsLedger.objects.filter(
        employee=employee,
        source=PointsLedger.Source.DAILY_LOGIN,
        local_date=today,
    ).exists():
        return 0, "already"
    cfg = _get_mall_points_settings()
    return grant_learning_points(
        employee,
        cfg["daily_login"],
        PointsLedger.Source.DAILY_LOGIN,
        local_date=today,
        note="每日登录",
    )


def try_award_course_completion(employee: Employee, course) -> tuple[int, str]:
    """课程首次标记学完时发放；同一课只发一次。金额 = 课程 reward_points，为 0 时用后台默认完课分。"""
    from .models import PointsLedger

    if PointsLedger.objects.filter(
        employee=employee,
        source=PointsLedger.Source.COURSE_COMPLETE,
        course=course,
    ).exists():
        return 0, "already"
    cfg = _get_mall_points_settings()
    base = int(course.reward_points) if int(course.reward_points or 0) > 0 else cfg["course_complete_default"]
    return grant_learning_points(
        employee,
        base,
        PointsLedger.Source.COURSE_COMPLETE,
        course=course,
        note=f"学完《{course.name}》",
    )
