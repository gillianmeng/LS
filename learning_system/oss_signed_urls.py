"""OSS 私有读：短时签名 URL（供课程页 <video> 等使用）。"""

from __future__ import annotations

import oss2
from django.conf import settings

from learning_system.oss_common import oss_object_key


def sign_oss_get_url(relative_name: str, expires: int | None = None) -> str:
    """
    生成 GET 签名 URL。relative_name 为 FileField.name（与 DB 中一致）。

    :param expires: 有效秒数，默认取 settings.OSS_SIGNED_URL_EXPIRES_SECONDS（如 8 小时）。
    """
    if not getattr(settings, "USE_OSS_MEDIA", False):
        raise RuntimeError("sign_oss_get_url 仅在 USE_OSS_MEDIA=1 时可用")
    exp = expires if expires is not None else int(getattr(settings, "OSS_SIGNED_URL_EXPIRES_SECONDS", 8 * 3600))
    auth = oss2.Auth(settings.OSS_ACCESS_KEY_ID, settings.OSS_ACCESS_KEY_SECRET)
    ep = settings.OSS_ENDPOINT.strip().rstrip("/")
    if not ep.startswith("http"):
        ep = "https://" + ep
    bucket = oss2.Bucket(auth, ep, settings.OSS_BUCKET_NAME)
    key = oss_object_key(relative_name, getattr(settings, "OSS_LOCATION", "") or "")
    return bucket.sign_url("GET", key, exp, slash_safe=True)
