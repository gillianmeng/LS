"""
Django 管理站点（/admin/）标题与首页文案。
修改文案请编辑 settings 中的 ADMIN_SITE_*，或在此文件调整默认值。
"""

import types

from django.conf import settings
from django.contrib import admin

from learning_system.dashboard_stats import get_admin_dashboard_stats
from users.forms import AdminEmployeeAuthenticationForm

admin.site.login_form = AdminEmployeeAuthenticationForm
admin.site.site_header = getattr(settings, "ADMIN_SITE_HEADER", "球学堂管理后台")
admin.site.site_title = getattr(settings, "ADMIN_SITE_TITLE", "球学堂")
admin.site.index_title = getattr(settings, "ADMIN_INDEX_TITLE", "数据与内容管理")
admin.site.empty_value_display = "—"

# 工作台首页模板需要 dash 上下文；不依赖 templatetags 注册（避免部分环境未加载 users.templatetags）
_original_admin_index = admin.site.index


def _admin_index_with_dashboard(self, request, extra_context=None):
    extra_context = extra_context or {}
    extra_context.setdefault("dash", get_admin_dashboard_stats())
    return _original_admin_index(request, extra_context)


admin.site.index = types.MethodType(_admin_index_with_dashboard, admin.site)
