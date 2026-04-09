"""
创建虚拟员工账号及积分商城示例商品（本地/测试用）。

用法:
  python manage.py ensure_demo_shop_data

虚拟账号：MCZ001–MCZ010（丘八…郭十、张三～赵六）；积分见 DEMO_ACCOUNTS。
首页「专业讲师」：MCZ007–MCZ010（张三～赵六）与 DEMO_INSTRUCTORS 同步；头像文件需在
MEDIA_ROOT 下对应路径存在（见各条 photo 相对路径）。

密码默认 qiuxue123（可用环境变量 DEMO_EMPLOYEE_PASSWORD 覆盖）。
每次执行会重置上述账号的密码与积分。示例商品若已存在同名则跳过创建。
"""

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from courses.models import Instructor
from shop.models import Product
from users.models import Employee

DEFAULT_PASSWORD = "qiuxue123"

# 工号、姓名、积分
DEMO_ACCOUNTS = (
    ("MCZ001", "丘八", 300),
    ("MCZ002", "宴九", 400),
    ("MCZ003", "漆七", 500),
    ("MCZ004", "刑大", 50),
    ("MCZ005", "姚二", 200),
    ("MCZ006", "郭十", 600),
    ("MCZ007", "张三", 100),
    ("MCZ008", "李四", 200),
    ("MCZ009", "王五", 300),
    ("MCZ010", "赵六", 400),
)

# 已从演示列表移除的工号：执行命令时会删除库中对应账号（若存在）
RETIRED_DEMO_EMP_IDS = ("MCZ011", "MCZ012", "MCZ013", "MCZ014")

SAMPLE_PRODUCTS = (
    ("笔记本礼盒", 80, 50),
    ("运动水壶", 150, 30),
    ("蓝牙耳机（演示）", 280, 20),
)

# 姓名、职称、对应演示工号、头像相对 MEDIA_ROOT 的路径（与后台已上传文件一致）
DEMO_INSTRUCTORS = (
    ("张三", "高级讲师", "MCZ007", "courses/instructors/d5c70a8f17e9f72d22c99d0d544752f4.jpg", 0),
    ("李四", "高级讲师", "MCZ008", "courses/instructors/龙.jpg", 1),
    ("王五", "高级讲师", "MCZ009", "courses/instructors/生成特定风格图片.png", 2),
    ("赵六", "认证讲师", "MCZ010", "courses/instructors/a0468aa89c50b668e5630a3806add782.jpg", 3),
)


class Command(BaseCommand):
    help = "创建虚拟员工 MCZ001–MCZ010、同步首页讲师（张三～赵六）及商城示例商品"

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_EMPLOYEE_PASSWORD", "").strip() or DEFAULT_PASSWORD

        n_retired, _ = Employee.objects.filter(emp_id__in=RETIRED_DEMO_EMP_IDS).delete()
        if n_retired:
            self.stdout.write(
                self.style.WARNING(
                    f"已移除演示账号 MCZ011–MCZ014（本次删除 {n_retired} 条相关记录）。\n"
                )
            )

        lines = []
        for emp_id, real_name, points in DEMO_ACCOUNTS:
            user, _created = Employee.objects.update_or_create(
                emp_id=emp_id,
                defaults={
                    "real_name": real_name,
                    "email": "",
                    "is_staff": False,
                    "is_superuser": False,
                    "points_balance": points,
                },
            )
            user.set_password(password)
            user.points_balance = points
            user.save()
            lines.append(f"  {emp_id}  {real_name}  {points} 分")

        instructor_lines = []
        media_root = Path(settings.MEDIA_ROOT)
        for name, title, link_emp_id, photo_rel, sort_order in DEMO_INSTRUCTORS:
            link_emp = Employee.objects.filter(emp_id=link_emp_id).first()
            ins, _ = Instructor.objects.update_or_create(
                name=name,
                defaults={
                    "title": title,
                    "employee": link_emp,
                    "sort_order": sort_order,
                    "is_published": True,
                    "photo_url": "",
                },
            )
            abs_photo = media_root / photo_rel
            if abs_photo.is_file():
                if ins.photo.name != photo_rel:
                    ins.photo.name = photo_rel
                    ins.save(update_fields=["photo"])
                instructor_lines.append(f"  {name}  {title}  头像 OK")
            else:
                instructor_lines.append(
                    f"  {name}  {title}  头像文件缺失: {photo_rel}（已保留职称与排序）"
                )

        added = 0
        for name, cost, stock in SAMPLE_PRODUCTS:
            _obj, c = Product.objects.get_or_create(
                name=name,
                defaults={"points_cost": cost, "stock": stock},
            )
            if c:
                added += 1

        self.stdout.write(
            self.style.SUCCESS(
                "虚拟账号（密码默认 "
                + DEFAULT_PASSWORD
                + "，可用 DEMO_EMPLOYEE_PASSWORD 覆盖）：\n"
                + "\n".join(lines)
                + "\n\n首页讲师（张三～赵六）：\n"
                + "\n".join(instructor_lines)
                + f"\n\n示例商品：本次新建 {added} 条（同名已存在则保留原数据）。"
            )
        )
