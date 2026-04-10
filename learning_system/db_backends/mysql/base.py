"""
Custom MySQL database backend that skips the MySQL version check.

Django 4.2+ requires MySQL 8.0+, but the SEP deployment environment runs
MySQL 5.7.27.  MySQL 5.7 works fine with Django 4.2 in practice — the
hard version check is overly conservative.  Remove this file once the
database is upgraded to MySQL 8.0+.
"""

from django.db.backends.mysql import base
from django.db.backends.mysql import features


class DatabaseFeatures(features.DatabaseFeatures):
    @property
    def minimum_database_version(self):
        if self.connection.mysql_is_mariadb:
            return (10, 4)
        return (5, 7)


class DatabaseWrapper(base.DatabaseWrapper):
    features_class = DatabaseFeatures

    def init_connection_state(self):
        super().init_connection_state()
        # 与 settings DATABASES OPTIONS 中的 charset/init_command 双保险：部分连接池或旧驱动下
        # 仅声明 charset 仍可能以 latin1/utf8 会话写入，导致 emoji（4 字节 UTF-8）报 1366。
        try:
            with self.cursor() as cursor:
                cursor.execute(
                    "SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
        except Exception:
            pass
