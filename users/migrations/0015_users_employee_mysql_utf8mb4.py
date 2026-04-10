"""
显式将 users_employee 转为 utf8mb4，保证 signature / real_name 等可存 emoji 与数学字母符号等 4 字节字符。

若仅依赖 courses 中全库迁移，在部分环境可能未覆盖到本表；本迁移作为兜底。
SQLite 下跳过。
"""

from django.db import migrations


def _convert_employee_table(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "mysql":
        return
    qn = conn.ops.quote_name
    with conn.cursor() as cursor:
        cursor.execute(
            f"ALTER TABLE {qn('users_employee')} CONVERT TO CHARACTER SET utf8mb4 "
            "COLLATE utf8mb4_unicode_ci"
        )


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0014_bootstrap_default_admin"),
    ]

    operations = [
        migrations.RunPython(_convert_employee_table, _noop),
    ]
