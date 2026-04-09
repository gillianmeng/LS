from django.db.models import Q

from .models import Notification, SiteBannerConfig


def site_banner_config(request):
    """各页顶通栏 Banner（单条配置，未上传则用默认静态图）。"""
    return {"banner_config": SiteBannerConfig.get_solo()}


def nav_notifications(request):
    """顶栏通知列表与未读数量（含全体通知）。"""
    if not request.user.is_authenticated:
        return {
            "nav_notification_items": [],
            "nav_notification_unread_count": 0,
        }
    user = request.user
    applicable = Notification.objects.filter(
        Q(employee__isnull=True) | Q(employee=user)
    ).order_by("-created_at")
    unread = sum(1 for n in applicable if not n.is_read_by(user))
    items = [
        {"notification": n, "unread": not n.is_read_by(user)}
        for n in applicable[:12]
    ]
    return {
        "nav_notification_items": items,
        "nav_notification_unread_count": unread,
    }
