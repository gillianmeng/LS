# LS（Learning System）

企业内部学习系统：课程与考试、积分商城、活动广场（培训报名）、员工账户与通知等。

## 版本

当前：**1.1.0**（见仓库根目录 `VERSION`）

### 与 1.0.1 的区别（1.1.0 更新摘要）

| 类别 | 说明 |
|------|------|
| 前台信息架构 | 主导航「知识殿堂」；原「我的课程」入口更名为「我的学习」；我的培训内展示必修在线课等 |
| 学习任务 | 知识殿堂首页「学习任务」：合并**指派必修**与**正式考试**（按期限/开考/截止与提醒窗口排序高亮）；UI 强化「须完成」提示 |
| 必修课程（后台） | 课程支持**必修完成期限**、**提醒窗口（天）**；前台培训页、课程详情与学习任务联动展示 |
| 考试提醒 | 正式考试按**开始/结束时间**与默认 7 天考前/截止前提醒窗口进入学习任务（已通过考试不占位） |
| 学习偏好 / 提醒 | 学习提醒与完课相关设置（含迁移）；可选站内提醒逻辑扩展（见 `courses/learning_reminders.py` 等） |
| 部署与账号 | 迁移预置超级管理员（工号 `admin`）；`python manage.py bootstrap_admin` 用于空库或忘密重置 |
| 其他 | 「我的报名」页去掉冗长说明文案；多处面包屑/返回链接与文案统一为「知识殿堂」 |

部署本版本请务必执行：`python manage.py migrate`。

## 技术栈

- Python 3.12、Django 4.2
- 数据库：SQLite（本地开发）/ MySQL 5.7+（生产，通过 PyMySQL 连接）
- 可选：阿里云 OSS 媒体存储

## 开发环境配置

本项目使用 Conda 管理 Python 环境。

```bash
# 创建环境（仅需一次）
conda create -n e-learning python=3.12 -y

# 激活环境（每次开发前执行）
conda activate e-learning

# 安装依赖
pip install -r requirements.txt
```

## 本地运行

```bash
conda activate e-learning
cp env.example .env          # 按需编辑，勿将密钥提交仓库
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

数据库默认使用项目根目录 `db.sqlite3`（无需安装 MySQL）。生产环境设置 `USE_MYSQL=1` 并配置 `MYSQL_*` 环境变量即可切换到 MySQL。

**首次部署或空库**：迁移会尝试创建预置管理员；若无法登录，执行：

```bash
python manage.py bootstrap_admin
```

登录后台时「用户名」为 **工号** `admin`，默认密码见命令输出；**上线后请立即修改密码**。

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

## 仓库与分支

| 用途 | 地址 | 说明 |
|------|------|------|
| GitHub（同步） | <https://github.com/gillianmeng/LS> | 默认分支 `main` |
| GitLab | <http://git.snowballfinance.com/hr/e-learning> | **`sep`**：集成分支（与当前 `VERSION` / README 版本一致）；**`prod`**：生产发布 |

克隆 GitLab 示例：

```bash
# 生产
git clone -b prod http://git.snowballfinance.com/hr/e-learning.git

# 集成分支 sep（1.1.0 起）
git clone -b sep http://git.snowballfinance.com/hr/e-learning.git
```

## 许可

内部使用；如需对外分发请单独约定许可条款。
