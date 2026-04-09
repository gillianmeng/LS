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
