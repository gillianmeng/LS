"""
使用 PyMySQL 作为 MySQLdb 的替代驱动。
Django 6 会校验 mysqlclient 版本；PyMySQL 伪装版本较低，需声明兼容版本号。
生产环境若已安装 mysqlclient>=2.2.1，可删除本文件中的 pymysql 相关代码。
"""
import pymysql

pymysql.install_as_MySQLdb()

# Django 6: backends/mysql/base.py 要求 mysqlclient >= 2.2.1
import MySQLdb  # noqa: E402

MySQLdb.version_info = (2, 2, 1, "final", 0)
