# LS（Learning System）

企业内部学习系统，包含课程与考试、积分商城、活动广场、员工账户、通知与后台管理等模块。

## 版本

当前版本：**1.2.3**（见仓库根目录 `VERSION`）

### 1.2.3 更新摘要

| 类别 | 说明 |
|------|------|
| 视觉升级 | 重做后台与前台的统一视觉语言，优化导航、卡片、标题与按钮风格，提升整体体验一致性 |
| 后台工作台 | 优化后台首页、侧边导航、常用功能区与管理页样式，增强层次感与可用性 |
| 前台体验 | 首页、课程详情、课程目录、积分商城、活动中心等页面进行美化，保持功能与结构不变 |
| 品牌标识 | 更新站点品牌标识为更活泼的卡通雪花风格，并加入悬停动画效果 |
| 协同能力 | 新增飞书组织同步相关脚本与消息支持，便于企业组织数据维护 |

### 1.2.2 相对 1.2.1 的更新

| 类别 | 说明 |
|------|------|
| 密钥与仓库 | `config/env.sep` 恢复 OSS / MySQL 占位，真实值仅由部署平台 Secret 或环境变量注入；README 部署说明已同步 |

### 1.2.1 相对 1.2.0 的更新

| 类别 | 说明 |
|------|------|
| Sep / OSS 媒体 | `config/env.sep`：`USE_OSS_MEDIA=1`，与 Sep 数据库中的媒体路径一致；服务端可用内网 `OSS_ENDPOINT`，浏览器访问图片/视频需公网 `OSS_PUBLIC_ENDPOINT` |
| 代码（1.2.0 后已合入） | `OSS_PUBLIC_ENDPOINT_RESOLVED`：`MEDIA_URL`、`FileField.url`、视频签名 URL 均走公网可解析域名，避免仅配置内网 endpoint 时全站裂图、视频无法播放 |
| 保密 | Sep 模板中不写 OSS AK/SK、MySQL 密码；由部署环境注入（`python-dotenv` 默认不覆盖已存在的环境变量） |

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

数据库默认使用项目根目录 `db.sqlite3`。生产环境设置 `USE_MYSQL=1` 并配置 `MYSQL_*` 环境变量即可切换到 MySQL。

**首次部署或空库**：迁移会尝试创建预置管理员；若无法登录，执行：

```bash
python manage.py bootstrap_admin
```

登录后台时「用户名」为 **工号** `admin`，默认密码见命令输出；上线后请立即修改密码。

## 环境变量

复制 `env.example` 为 `.env`，按需填写。常用项：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_MYSQL` | _(空)_ | 设为 `1` 启用 MySQL，否则使用 SQLite |
| `MYSQL_DATABASE` | `learning_db` | MySQL 数据库名 |
| `MYSQL_HOST` | `127.0.0.1` | MySQL 主机地址 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_USER` | `root` | MySQL 用户名 |
| `MYSQL_PASSWORD` | _(空)_ | MySQL 密码 |
| `USE_OSS_MEDIA` | `0` | 本地预览保持 `0`；生产 / Sep 使用 OSS 时设为 `1` |
| `OSS_ENDPOINT` | 公网北京 OSS | 服务端 oss2 用；机房可设为内网 |
| `OSS_PUBLIC_ENDPOINT` | _(空)_ | 浏览器加载封面/头像/签名视频用；未设且 `OSS_ENDPOINT` 为内网时，代码会推导公网域名 |
| `OSS_BUCKET_NAME` 等 | 见 `env.example` | 与阿里云控制台 Bucket、AK/SK 一致 |

## 部署与密钥管理

为了更适合公司部署环境，推荐采用“配置模板 + 私密文件/环境变量”的方式管理密钥：

- `config/env.sep`：部署模板，仅保留可公开配置与占位符，不写真实密钥
- `config/env.secret.example`：私密文件模板，可复制为 `config/env.secret` 后在本机或部署机填写真实值
- `config/env.secret`：真实密钥文件，仅保留在本地开发机或部署机上，**不要提交到仓库**

建议使用方式：

```bash
cp config/env.secret.example config/env.secret
# 在 config/env.secret 中填写真实 OSS / MySQL 密钥
```

如果部署平台支持 Secret / 环境变量注入，也可以不落盘，直接由平台提供这些值。这样更适合公司内网、容器化或 CI/CD 部署，能避免把密钥写进 Git 历史。

## 仓库与分支

| 用途 | 地址 | 说明 |
|------|------|------|
| GitHub（同步） | <https://github.com/gillianmeng/LS> | 默认分支 `main` |
| GitLab | <http://git.snowballfinance.com/hr/e-learning> | `sep`：集成分支；`prod`：生产发布 |

## 许可

内部使用；如需对外分发请单独约定许可条款。
