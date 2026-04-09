"""全站登录门禁：未登录仅可访问首页预览、账号相关、静态/媒体与后台入口。"""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlencode


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            return self.get_response(request)

        path = request.path_info or "/"

        if self._anonymous_allowed(request, path):
            return self.get_response(request)

        login = settings.LOGIN_URL
        q = urlencode({"next": request.get_full_path()})
        sep = "&" if "?" in login else "?"
        return redirect(f"{login}{sep}{q}")

    def _anonymous_allowed(self, request, path: str) -> bool:
        # 首页（仅横幅 + 课程预览，内容由视图区分）
        if path == "/" or path == "":
            return True

        # 登录 / 登出 / 注册（含员工注册）
        if path.startswith("/accounts/login"):
            return True
        if path.startswith("/accounts/logout"):
            return True
        if path.startswith("/accounts/register"):
            return True

        # Django Admin 自带登录页
        if path.startswith("/admin"):
            return True

        # 开发环境静态与上传媒体
        if path.startswith("/static/"):
            return True
        if path.startswith("/media/"):
            return True

        if path == "/favicon.ico":
            return True

        return False
