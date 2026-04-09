"""
Django settings for learning_system project.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# 项目根目录的 .env（已在 .gitignore）；生产环境也可不设文件而只用系统环境变量。
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = "django-insecure-p)#^_cfo#7=gnvv88-yjijfn*2_+0l_cb^8@gapzpqi@add9lk"

DEBUG = True

ALLOWED_HOSTS: list[str] = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "users.apps.UsersConfig",
    "courses.apps.CoursesConfig",
    "shop.apps.ShopConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "learning_system.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "learning_system.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "users.context_processors.nav_notifications",
                "users.context_processors.site_banner_config",
            ],
        },
    },
]

WSGI_APPLICATION = "learning_system.wsgi.application"

# 数据库：默认 SQLite（无需安装 MySQL/Docker，本地直接预览）。
# 使用 MySQL / Docker 时设置环境变量：USE_MYSQL=1，并配置 MYSQL_*。
_USE_MYSQL = os.environ.get("USE_MYSQL", "").lower() in ("1", "true", "yes")

if not _USE_MYSQL:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.environ.get("MYSQL_DATABASE", "learning_db"),
            "USER": os.environ.get("MYSQL_USER", "root"),
            "PASSWORD": os.environ.get("MYSQL_PASSWORD", ""),
            "HOST": os.environ.get("MYSQL_HOST", "127.0.0.1"),
            "PORT": os.environ.get("MYSQL_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "zh-hans"

TIME_ZONE = "Asia/Shanghai"

USE_I18N = True

USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_ROOT = BASE_DIR / "media"

# —— 阿里云 OSS（课程视频、封面、站点上传图等）：仅通过环境变量配置密钥，勿写入仓库。
# 启用：USE_OSS_MEDIA=1，并设置 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET。
# 可选：OSS_MEDIA_CUSTOM_DOMAIN=cdn.example.com（绑定 CDN 时）
# 课程详情页内嵌视频：使用短时签名 URL（见 OSS_SIGNED_URL_EXPIRES_SECONDS）。
# OSS_DEFAULT_OBJECT_ACL：public-read（默认，封面等可直接 URL 访问）或 private（需配合后续图片签名，否则封面可能 403）。
USE_OSS_MEDIA = os.environ.get("USE_OSS_MEDIA", "").lower() in ("1", "true", "yes")
OSS_ACCESS_KEY_ID = os.environ.get("OSS_ACCESS_KEY_ID", "").strip()
OSS_ACCESS_KEY_SECRET = os.environ.get("OSS_ACCESS_KEY_SECRET", "").strip()
OSS_BUCKET_NAME = os.environ.get("OSS_BUCKET_NAME", "e-learning-vods").strip()
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "https://oss-cn-beijing.aliyuncs.com").strip()
OSS_MEDIA_CUSTOM_DOMAIN = os.environ.get("OSS_MEDIA_CUSTOM_DOMAIN", "").strip()
OSS_LOCATION = os.environ.get("OSS_LOCATION", "").strip()
OSS_SIGNED_URL_EXPIRES_SECONDS = int(os.environ.get("OSS_SIGNED_URL_EXPIRES", str(8 * 3600)))
_OSS_ACL_RAW = os.environ.get("OSS_DEFAULT_OBJECT_ACL", "public-read").strip().lower()
OSS_DEFAULT_OBJECT_ACL = _OSS_ACL_RAW if _OSS_ACL_RAW in ("private", "public-read") else "public-read"


def _oss_media_base_url() -> str:
    """Bucket 外网访问基址（与 AliyunOSSStorage 默认规则一致）。"""
    if OSS_MEDIA_CUSTOM_DOMAIN:
        d = OSS_MEDIA_CUSTOM_DOMAIN.rstrip("/")
        if d.startswith("http://") or d.startswith("https://"):
            return d + "/"
        return f"https://{d}/"
    host = OSS_ENDPOINT.replace("https://", "").replace("http://", "").strip("/")
    return f"https://{OSS_BUCKET_NAME}.{host}/"


if USE_OSS_MEDIA:
    if not OSS_ACCESS_KEY_ID or not OSS_ACCESS_KEY_SECRET:
        raise ImproperlyConfigured(
            "已设置 USE_OSS_MEDIA=1，但未配置 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET。"
            "请在部署环境中设置环境变量（勿提交到代码库）。"
        )
    MEDIA_URL = _oss_media_base_url()
    STORAGES = {
        "default": {
            "BACKEND": "learning_system.storage.AliyunOSSStorage",
            "OPTIONS": {
                "access_key_id": OSS_ACCESS_KEY_ID,
                "access_key_secret": OSS_ACCESS_KEY_SECRET,
                "bucket_name": OSS_BUCKET_NAME,
                "endpoint": OSS_ENDPOINT,
                "base_url": (_oss_media_base_url() if OSS_MEDIA_CUSTOM_DOMAIN else None),
                "location": OSS_LOCATION,
                "default_object_acl": OSS_DEFAULT_OBJECT_ACL,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    # 必须以 / 开头，否则在 /courses/ 等子路径下相对地址会变成 /courses/media/...，本地预览图片/视频会 404。
    MEDIA_URL = "/media/"
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {
                "location": str(MEDIA_ROOT),
                "base_url": MEDIA_URL,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "users.Employee"

# 前台员工登录（users 应用 /accounts/login/）
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# 管理员自助注册邀请码（设为非空后，/accounts/register/staff/ 可用；生产务必使用强随机串）
ADMIN_REGISTER_SECRET = os.environ.get("ADMIN_REGISTER_SECRET", "").strip()

# Django 管理后台（/admin/）页面标题与首页提示（可通过环境变量覆盖）
ADMIN_SITE_HEADER = os.environ.get("ADMIN_SITE_HEADER", "球学堂管理后台")
ADMIN_SITE_TITLE = os.environ.get("ADMIN_SITE_TITLE", "球学堂")
ADMIN_INDEX_TITLE = os.environ.get("ADMIN_INDEX_TITLE", "数据与内容管理")

# 允许的跨域 Origin
CSRF_TRUSTED_ORIGINS = [
    "https://sep-e-learning.snowballfinance.com",
    "https://e-learning.snowballfinance.com",
]
