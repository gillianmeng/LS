"""
Django 管理站点（/admin/）标题与首页文案。
修改文案请编辑 settings 中的 ADMIN_SITE_*，或在此文件调整默认值。
"""

from django.conf import settings
from django.contrib import admin

from users.forms import AdminEmployeeAuthenticationForm

admin.site.login_form = AdminEmployeeAuthenticationForm
admin.site.site_header = getattr(settings, "ADMIN_SITE_HEADER", "球学堂管理后台")
admin.site.site_title = getattr(settings, "ADMIN_SITE_TITLE", "球学堂")
admin.site.index_title = getattr(settings, "ADMIN_INDEX_TITLE", "数据与内容管理")
admin.site.empty_value_display = "—"
