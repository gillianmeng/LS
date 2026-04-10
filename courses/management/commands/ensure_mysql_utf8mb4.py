"""
在 MySQL 上将当前库所有表转为 utf8mb4（与迁移 0014/0015 逻辑一致），用于迁移已执行
但仍有 1366 emoji 报错时手工补救。

用法:
  USE_MYSQL=1 python manage.py ensure_mysql_utf8mb4
"""

import logging

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "将 MySQL 当前库全部表转为 utf8mb4_unicode_ci（支持 emoji）"

    def handle(self, *args, **options):
        if connection.vendor != "mysql":
            self.stdout.write(self.style.WARNING("当前非 MySQL，跳过。"))
            return
        db_name = connection.settings_dict.get("NAME") or ""
        qn = connection.ops.quote_name
        log = logging.getLogger(__name__)
        ok, fail = 0, 0
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT TABLE_NAME FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
                ORDER BY TABLE_NAME
                """,
                [db_name],
            )
            tables = [r[0] for r in cursor.fetchall()]
        for tbl in tables:
            t = tbl.replace("`", "")
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"ALTER TABLE {qn(t)} CONVERT TO CHARACTER SET utf8mb4 "
                        "COLLATE utf8mb4_unicode_ci"
                    )
                ok += 1
            except Exception as exc:
                log.warning("ALTER failed for %s: %s", t, exc)
                fail += 1
                self.stderr.write(self.style.ERROR(f"失败 {t}: {exc}"))
        self.stdout.write(
            self.style.SUCCESS(f"完成：成功 {ok} 张表，失败 {fail} 张。若仍有 1366，请检查数据库账号是否有 ALTER 权限。")
        )
