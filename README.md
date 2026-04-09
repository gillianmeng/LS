# LS（Learning System）

企业内部学习系统：课程与考试、积分商城、活动广场（培训报名）、员工账户与通知等。

## 版本

**1.0.1**（见仓库根目录 `VERSION`）

## 技术栈

- Python 3.12、Django 4.2
- 数据库：SQLite（本地开发）/ MySQL 5.7+（生产，通过 PyMySQL 连接）
- 可选：阿里云 OSS 媒体存储

## 本地运行

```bash
conda create -n e-learning python=3.12
conda activate e-learning
pip install -r requirements.txt
cp env.example .env          # 按需编辑，勿将密钥提交仓库
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

数据库默认使用项目根目录 `db.sqlite3`（无需安装 MySQL）。生产环境设置 `USE_MYSQL=1` 并配置 `MYSQL_*` 环境变量即可切换到 MySQL。

## 环境变量

复制 `env.example` 为 `.env`。常用项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_MYSQL` | _(空)_ | 设为 `1` 启用 MySQL，否则使用 SQLite |
| `MYSQL_DATABASE` | `learning_db` | MySQL 数据库名 |
| `MYSQL_HOST` | `127.0.0.1` | MySQL 主机地址 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `root` | MySQL 用户名 |
| `MYSQL_PASSWORD` | _(空)_ | MySQL 密码 |
| `USE_OSS_MEDIA` | `0` | 本地预览保持 `0`（使用本机 `media/`）；`1` 走阿里云 OSS |

## 仓库

| 用途 | 地址 | 说明 |
|------|------|------|
| GitHub（同步） | <https://github.com/gillianmeng/LS> | 默认分支 `main` |
| GitLab（SEP） | <http://git.snowballfinance.com/hr/e-learning> | 开发分支 `sep`，生产分支 `prod` |

克隆 GitLab 生产分支示例：

```bash
git clone -b prod http://git.snowballfinance.com/hr/e-learning.git
```

## 许可

内部使用；如需对外分发请单独约定许可条款。
