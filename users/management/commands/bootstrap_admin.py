"""
创建或重置预置后台管理员（工号 admin，用于空库/忘密恢复）。

用法:
  python manage.py bootstrap_admin

与迁移 0014_bootstrap_default_admin 一致：工号 admin，密码 qiuxuetang123。
上线后请尽快在后台修改密码。
"""

from django.core.management.base import BaseCommand

from users.models import Employee

BOOTSTRAP_EMP_ID = "admin"
BOOTSTRAP_REAL_NAME = "系统管理员"
BOOTSTRAP_PASSWORD = "qiuxuetang123"


class Command(BaseCommand):
    help = "创建或更新预置超级管理员（工号 admin）"

    def handle(self, *args, **options):
        user, created = Employee.objects.get_or_create(
            emp_id=BOOTSTRAP_EMP_ID,
            defaults={
                "real_name": BOOTSTRAP_REAL_NAME,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )
        user.real_name = user.real_name or BOOTSTRAP_REAL_NAME
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(BOOTSTRAP_PASSWORD)
        user.save()

        action = "已创建" if created else "已重置密码并更新"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}：工号 {BOOTSTRAP_EMP_ID}，姓名 {user.real_name}\n"
                "登录 /admin/ 时在「工号」处填写 admin，密码为 qiuxuetang123。\n"
                "请登录后立即在后台修改密码。"
            )
        )
