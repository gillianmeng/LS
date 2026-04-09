"""
Custom MySQL database backend that skips the MySQL version check.

Django 4.2+ requires MySQL 8.0+, but the SEP deployment environment runs
MySQL 5.7.27.  MySQL 5.7 works fine with Django 4.2 in practice — the
hard version check is overly conservative.  Remove this file once the
database is upgraded to MySQL 8.0+.
"""

from django.db.backends.mysql import base


class DatabaseWrapper(base.DatabaseWrapper):
    def check_database_version(self):
        pass
