"""
URL configuration for learning_system project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import admin_site  # noqa: F401  — 应用 AdminSite 文案（副作用导入）
from .views import global_search, index

urlpatterns = [
    path("", index, name="home"),
    path("search/", global_search, name="search"),
    path("admin/", admin.site.urls),
    path("accounts/", include("users.urls")),
    path("courses/", include("courses.urls")),
    path("shop/", include("shop.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
