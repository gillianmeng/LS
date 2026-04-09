"""OSS 对象 key 与存储路径约定（与 AliyunOSSStorage 一致）。"""


def oss_object_key(name: str, location: str = "") -> str:
    """将 FileField.name（如 courses/videos/a.mp4）转为 Bucket 内完整 object key。"""
    name = name.replace("\\", "/").lstrip("/")
    loc = (location or "").strip("/")
    if loc:
        return f"{loc}/{name}"
    return name
