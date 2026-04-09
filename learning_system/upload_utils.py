"""上传文件：保存时删除被替换或清空后的旧文件，避免磁盘残留。"""


def delete_replaced_file_fields(old_instance, new_instance, *field_names: str) -> None:
    if not old_instance:
        return
    for name in field_names:
        old_f = getattr(old_instance, name, None)
        new_f = getattr(new_instance, name, None)
        old_name = (old_f.name if old_f else "") or ""
        new_name = ""
        if new_f is not None and getattr(new_f, "name", ""):
            new_name = new_f.name
        if old_name and old_name != new_name:
            old_f.delete(save=False)
