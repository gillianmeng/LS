"""阿里云 OSS 存储后端（课程视频、封面、站点图片等 FileField / ImageField）。"""

from __future__ import annotations

import mimetypes
import os
from urllib.parse import quote

import oss2
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible

from learning_system.oss_common import oss_object_key


@deconstructible
class AliyunOSSStorage(Storage):
    """使用 oss2 上传；按资源类型自动设置 ACL（图片 public-read、VOD private）。"""

    def __init__(
        self,
        *,
        access_key_id: str,
        access_key_secret: str,
        bucket_name: str,
        endpoint: str,
        base_url: str | None = None,
        location: str = "",
        default_object_acl: str = "public-read",
    ):
        if not access_key_id or not access_key_secret or not bucket_name or not endpoint:
            raise ImproperlyConfigured("阿里云 OSS 缺少 access_key_id / access_key_secret / bucket_name / endpoint。")
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.bucket_name = bucket_name
        ep = endpoint.strip().rstrip("/")
        if not ep.startswith("http"):
            ep = "https://" + ep
        self.endpoint = ep
        self.location = (location or "").strip("/")
        acl = (default_object_acl or "public-read").strip().lower()
        if acl not in ("private", "public-read"):
            acl = "public-read"
        self._default_object_acl = acl
        auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(auth, self.endpoint, bucket_name)
        if base_url:
            self._base_url = base_url.rstrip("/") + "/"
        else:
            host = self.endpoint.replace("https://", "").replace("http://", "")
            self._base_url = f"https://{bucket_name}.{host}/"

    def _key(self, name: str) -> str:
        return oss_object_key(name, self.location)

    def _open(self, name, mode="rb"):
        if "w" in mode or "a" in mode or "+" in mode:
            raise ValueError("OSS 存储不支持写入模式打开已有文件。")
        key = self._key(name)
        result = self._bucket.get_object(key)
        return ContentFile(result.read())

    @staticmethod
    def _is_vod_key(key: str, content_type: str | None = None) -> bool:
        normalized = key.lower().replace("\\", "/")
        ext = os.path.splitext(normalized)[1]
        vod_exts = {
            ".mp4",
            ".m3u8",
            ".ts",
            ".mov",
            ".m4v",
            ".avi",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".mp3",
            ".wav",
            ".aac",
            ".flac",
            ".ogg",
            ".m4a",
        }
        if normalized.startswith("courses/videos/"):
            return True
        if ext in vod_exts:
            return True
        ct = (content_type or "").lower()
        return ct.startswith("video/") or ct.startswith("audio/")

    def _pick_object_acl(self, key: str, content_type: str | None = None) -> str:
        # 安全策略：VOD 私有；图片与其余静态资源默认 public-read。
        if self._is_vod_key(key, content_type=content_type):
            return oss2.OBJECT_ACL_PRIVATE
        return oss2.OBJECT_ACL_PUBLIC_READ

    def _save(self, name, content):
        key = self._key(name)
        data = content.read()
        ct = getattr(content, "content_type", None) or mimetypes.guess_type(name)[0]
        headers: dict[str, str] = {"x-oss-object-acl": self._pick_object_acl(key, content_type=ct)}
        if ct:
            headers["Content-Type"] = ct
        self._bucket.put_object(key, data, headers=headers)
        return name

    def delete(self, name):
        self._bucket.delete_object(self._key(name))

    def exists(self, name):
        return self._bucket.object_exists(self._key(name))

    def url(self, name):
        key = self._key(name).replace("\\", "/")
        return self._base_url.rstrip("/") + "/" + quote(key, safe="/")

    def get_available_name(self, name, max_length=None):
        return super().get_available_name(name, max_length=max_length)
