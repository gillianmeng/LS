# LS（Learning System）

企业内部学习系统：课程与考试、积分商城、活动广场（培训报名）、员工账户与通知等。

## 版本

**1.0.1**（见仓库根目录 `VERSION`）

## 技术栈

- Python 3.x、Django 6.x
- 可选：阿里云 OSS 媒体存储、PyMySQL / MySQL

## 本地运行

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env          # 按需编辑，勿将密钥提交仓库
python manage.py migrate
python manage.py runserver
```

数据库默认可使用项目根目录 `db.sqlite3`（开发）；生产请配置 MySQL 等并调整 `learning_system/settings.py` / 环境变量。

## 环境变量

复制 `env.example` 为 `.env`。常用项：

- `USE_OSS_MEDIA`：本地预览建议 `0`，使用本机 `media/`；`1` 时走 OSS。

## 仓库

| 用途 | 地址 | 说明 |
|------|------|------|
| GitHub（同步） | <https://github.com/gillianmeng/LS> | 默认分支 `main` |
| GitLab（生产发布） | <http://git.snowballfinance.com/hr/e-learning> | 生产代码在分支 **`prod`** |

克隆 GitLab 生产分支示例：

```bash
git clone -b prod http://git.snowballfinance.com/hr/e-learning.git
```

## 许可

内部使用；如需对外分发请单独约定许可条款。
