"""
创建或重置本地开发用超级管理员（仅建议在 DEBUG 或明确设置环境变量时使用）。

用法:
  python manage.py ensure_dev_admin

默认工号 XQ1308；可用环境变量 DEV_ADMIN_EMP_ID 覆盖；密码由 DEV_ADMIN_PASSWORD 指定（不设则使用内置开发默认）。
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand

from users.models import Employee

# 与项目约定一致：本地默认后台账号工号（可通过 DEV_ADMIN_EMP_ID 覆盖）
DEFAULT_DEV_EMP_ID = "XQ1308"


class Command(BaseCommand):
    help = "创建/更新开发用超级管理员账号（默认工号 XQ1308）"

    def handle(self, *args, **options):
        emp_id = os.environ.get("DEV_ADMIN_EMP_ID", DEFAULT_DEV_EMP_ID).strip() or DEFAULT_DEV_EMP_ID
        password = os.environ.get("DEV_ADMIN_PASSWORD", "").strip()
        if not password:
            # 仅作本地演示；上线务必改密或使用强随机 DEV_ADMIN_PASSWORD
            password = "qiuxue123"

        if not settings.DEBUG and password == "qiuxue123":
            self.stderr.write(
                self.style.ERROR(
                    "生产环境请设置环境变量 DEV_ADMIN_PASSWORD，勿使用内置默认密码。"
                )
            )
            return

        user, created = Employee.objects.get_or_create(
            emp_id=emp_id,
            defaults={
                "real_name": "系统管理员",
                "email": "",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.real_name = user.real_name or "系统管理员"
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "已创建" if created else "已更新"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} 超级管理员：工号={emp_id} 姓名={user.real_name}\n"
                f"登录 /admin/：工号填 {emp_id}，密码为当前开发默认（见上）。若曾用该工号登录过前台，刷新或重新登录后即可进入后台。\n"
                f"生产环境请立即修改密码。"
            )
        )
