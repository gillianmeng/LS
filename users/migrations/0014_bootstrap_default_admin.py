"""空库或首次部署时预置后台管理员：工号 admin（登录名），密码见 RunPython（哈希入库）。"""

from django.contrib.auth.hashers import make_password
from django.db import migrations


def create_default_admin(apps, schema_editor):
    Employee = apps.get_model("users", "Employee")
    if Employee.objects.filter(emp_id="admin").exists():
        return
    Employee.objects.create(
        emp_id="admin",
        real_name="系统管理员",
        password=make_password("qiuxuetang123"),
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def remove_default_admin(apps, schema_editor):
    Employee = apps.get_model("users", "Employee")
    Employee.objects.filter(emp_id="admin").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0013_banner_help_points_square_note"),
    ]

    operations = [
        migrations.RunPython(create_default_admin, remove_default_admin),
    ]
