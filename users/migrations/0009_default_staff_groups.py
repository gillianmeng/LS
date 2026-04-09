from django.db import migrations


def seed_groups_and_staff(apps, schema_editor):
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

    for emp in Employee.objects.iterator():
        if emp.is_staff:
            continue
        # 历史数据：已在带权限组中的员工开通职员身份
        joined = False
        for g in emp.groups.all():
            if g.permissions.exists():
                joined = True
                break
        if joined:
            emp.is_staff = True
            emp.save(update_fields=["is_staff"])


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_sitebannerconfig_seed_row"),
    ]

    operations = [
        migrations.RunPython(seed_groups_and_staff, migrations.RunPython.noop),
    ]
