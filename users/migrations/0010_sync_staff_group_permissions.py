"""在 courses / shop 等应用迁移完成后，确保预置组绑定的模型权限完整（0009 可能早于业务应用执行）。"""

from django.db import migrations


def sync_groups_and_staff(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    Employee = apps.get_model("users", "Employee")

    configs = (
        ("学习内容管理", ("courses",)),
        ("商城运营", ("shop",)),
        ("用户与通知", ("users",)),
    )
    for name, app_labels in configs:
        g, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label__in=app_labels)
        g.permissions.set(perms)

    for emp in Employee.objects.filter(is_staff=False).iterator():
        if emp.groups.filter(permissions__isnull=False).exists():
            Employee.objects.filter(pk=emp.pk).update(is_staff=True)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0009_default_staff_groups"),
        ("courses", "0010_coursecategory"),
        ("shop", "0006_seed_shop_mall_settings"),
    ]

    operations = [
        migrations.RunPython(sync_groups_and_staff, migrations.RunPython.noop),
    ]
