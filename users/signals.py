"""员工与组：加入「带后台权限的组」时自动开通职员身份（is_staff），否则无法登录 /admin/。"""

from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

from .models import Employee


def _group_has_admin_permissions(group: Group) -> bool:
    return group.permissions.exists()


def _ensure_staff_for(user: Employee) -> None:
    if user.is_superuser or user.is_staff:
        return
    if not user.groups.filter(permissions__isnull=False).distinct().exists():
        return
    Employee.objects.filter(pk=user.pk).update(is_staff=True)


@receiver(m2m_changed, sender=Employee.groups.through)
def grant_staff_when_user_joins_permitted_group(
    sender, instance, action, pk_set, **kwargs
):
    """从员工侧改组，或从组侧改成员：只要进入任一带权限的组，即开通 is_staff。"""
    if action != "post_add" or not pk_set:
        return

    if isinstance(instance, Employee):
        user = instance
        groups = Group.objects.filter(pk__in=pk_set)
        if not any(_group_has_admin_permissions(g) for g in groups):
            return
        _ensure_staff_for(user)
        return

    if isinstance(instance, Group):
        group = instance
        if not _group_has_admin_permissions(group):
            return
        for emp in Employee.objects.filter(pk__in=pk_set):
            _ensure_staff_for(emp)
