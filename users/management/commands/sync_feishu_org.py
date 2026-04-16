"""从飞书拉取组织结构并按工号同步 Employee 账号基础信息。"""

from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.feishu_client import FeishuClient
from users.models import Employee


class Command(BaseCommand):
    help = "同步飞书组织结构（按工号 employee_no -> Employee.emp_id）"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="仅演练，不落库")
        parser.add_argument("--root-department-id", default="0", help="根部门 ID，默认 0（租户根）")

    def handle(self, *args, **options):
        app_id = os.environ.get("FEISHU_APP_ID", "").strip()
        app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
        if not app_id or not app_secret:
            raise CommandError("缺少 FEISHU_APP_ID / FEISHU_APP_SECRET 环境变量")

        dry_run = bool(options.get("dry_run"))
        root_department_id = str(options.get("root_department_id") or "0")

        client = FeishuClient(app_id=app_id, app_secret=app_secret)
        departments = client.list_departments(root_department_id=root_department_id)
        dept_name_by_id = {d.department_id: d.name for d in departments}

        seen_emp_ids: set[str] = set()
        pulled_users = []
        for dep in departments:
            for u in client.list_users_by_department(dep.department_id):
                emp_id = u.employee_no.strip()
                if not emp_id or emp_id in seen_emp_ids:
                    continue
                seen_emp_ids.add(emp_id)
                pulled_users.append(u)

        updated = 0
        created = 0
        skipped = 0

        with transaction.atomic():
            for u in pulled_users:
                emp_id = u.employee_no.strip()
                dept_names = [dept_name_by_id.get(did, "") for did in u.department_ids]
                dept_names = [n for n in dept_names if n]

                defaults = {
                    "real_name": u.name or emp_id,
                    "feishu_open_id": u.open_id,
                    "feishu_union_id": u.union_id or "",
                    "dept_level_1": dept_names[0] if len(dept_names) > 0 else "",
                    "dept_level_2": dept_names[1] if len(dept_names) > 1 else "",
                    "dept_level_3": dept_names[2] if len(dept_names) > 2 else "",
                    "dept_level_4": dept_names[3] if len(dept_names) > 3 else "",
                }

                obj, is_created = Employee.objects.get_or_create(emp_id=emp_id, defaults=defaults)
                if is_created:
                    created += 1
                    continue

                changed = False
                for field, value in defaults.items():
                    if getattr(obj, field) != value:
                        setattr(obj, field, value)
                        changed = True
                if changed:
                    obj.save(update_fields=list(defaults.keys()))
                    updated += 1
                else:
                    skipped += 1

            if dry_run:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if dry_run else "APPLY"
        self.stdout.write(
            self.style.SUCCESS(
                f"[{mode}] departments={len(departments)} users={len(pulled_users)} created={created} updated={updated} skipped={skipped}"
            )
        )
