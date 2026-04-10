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

**首次部署或空库**：迁移会尝试创建预置管理员；若无法登录，执行：

```bash
python manage.py bootstrap_admin
```

登录后台时「用户名」为 **工号** `admin`，默认密码见命令输出；**上线后请立即修改密码**。

## 环境变量

复制 `env.example` 为 `.env`。常用项：

- `USE_OSS_MEDIA`：本地预览建议 `0`，使用本机 `media/`；`1` 时走 OSS。

## 仓库与分支

| 用途 | 地址 | 说明 |
|------|------|------|
| GitHub（同步） | <https://github.com/gillianmeng/LS> | 默认分支 `main` |
| GitLab | <http://git.snowballfinance.com/hr/e-learning> | 生产常用分支 **`prod`**；集成/发布分支 **`sep`**（与本 README 版本对齐时请以 `sep` 上标签或提交为准） |

克隆 GitLab 示例：

```bash
# 生产
git clone -b prod http://git.snowballfinance.com/hr/e-learning.git

# 集成分支 sep（1.1.0 起）
git clone -b sep http://git.snowballfinance.com/hr/e-learning.git
```

## 许可

内部使用；如需对外分发请单独约定许可条款。
