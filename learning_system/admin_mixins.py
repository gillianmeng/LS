"""Django Admin 通用行为。"""

from django.db import models


class OptionalFileFieldsAdminMixin:
    """
    可选文件/图片字段在后台必须为非必填，否则无法勾选「清除」后保存。
    见 Django FileField 与 ClearableFileInput 的 required 语义。
    """

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field is not None and isinstance(
            db_field, (models.FileField, models.ImageField)
        ) and getattr(db_field, "blank", False):
            field.required = False
        return field
