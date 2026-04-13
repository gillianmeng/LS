from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_users_employee_mysql_utf8mb4"),
    ]

    operations = [
        migrations.AddField(
            model_name="employee",
            name="admin_shortcuts",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="管理员工作台快捷按钮配置（按顺序存储）。",
                verbose_name="后台常用功能",
            ),
        ),
    ]
