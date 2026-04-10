"""
若 0014 在部分表上因锁表/权限失败，本迁移按表重试 CONVERT（容错，不阻断其它表）。
新环境上 0014 已成功时，本迁移多为幂等快速跳过（单表 ALTER 仍可执行）。
"""

import logging

from django.db import migrations


def _retry_utf8mb4_tables(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "mysql":
        return
    db_name = conn.settings_dict.get("NAME") or ""
    if not db_name:
        return
    qn = conn.ops.quote_name
    log = logging.getLogger(__name__)
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT TABLE_NAME FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """,
            [db_name],
        )
        for (table_name,) in cursor.fetchall():
            tbl = table_name.replace("`", "")
            try:
                cursor.execute(
                    f"ALTER TABLE {qn(tbl)} CONVERT TO CHARACTER SET utf8mb4 "
                    "COLLATE utf8mb4_unicode_ci"
                )
            except Exception as exc:
                log.warning("utf8mb4 CONVERT failed for `%s`: %s", tbl, exc)


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0014_mysql_convert_to_utf8mb4"),
    ]

    operations = [
        migrations.RunPython(_retry_utf8mb4_tables, _noop),
    ]
