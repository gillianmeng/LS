"""
将当前库中所有表转换为 utf8mb4，以支持 emoji 等 4 字节 UTF-8 字符。

MySQL 的 utf8 实为 3 字节，写入 description/article_body 等含 emoji 时会报：
1366 Incorrect string value: '\\xF0\\x9F\\x91\\xA8...'
SQLite 下本迁移为空操作。
"""

from django.db import migrations


def _convert_tables_utf8mb4(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "mysql":
        return
    db_name = conn.settings_dict.get("NAME") or ""
    if not db_name:
        return
    qn = conn.ops.quote_name
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
            cursor.execute(
                f"ALTER TABLE {qn(tbl)} CONVERT TO CHARACTER SET utf8mb4 "
                "COLLATE utf8mb4_unicode_ci"
            )


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0013_course_required_deadline_reminder"),
    ]

    operations = [
        migrations.RunPython(_convert_tables_utf8mb4, _noop_reverse),
    ]
