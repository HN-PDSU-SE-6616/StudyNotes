# Taot 知识库 v2.0

个人知识库系统重构版。后端 FastAPI 异步 + Vue3 前端，支持 JWT 用户认证、Block 式笔记编辑、首页热点聚合。

---

## 一、设计目标

| 模块 | 说明 |
|------|------|
| 用户系统 | JWT 认证（access + refresh token），多用户数据隔离 |
| 首页 | 聚合 GitHub 热门项目、B 站编程视频、编程社区最新帖子 |
| 我的笔记 | Block 块编辑器（类 Typora/Notion），侧边栏树形导航，页面关系图 |
| 兼容旧版 | 保留 v1 文件树笔记接口，便于数据迁移 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Vue3 前端 (frontend/)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  首页    │  │ 登录注册  │  │  我的笔记（侧边栏+编辑器）│ │
│  │ 热点聚合  │  │ Pinia    │  │  Block 渲染 / 关系图   │ │
│  └──────────┘  └──────────┘  └──────────────────────┘ │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / Bearer JWT
┌────────────────────────▼────────────────────────────────┐
│              FastAPI 异步后端 (app/)                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌──────────────────┐  │
│  │  auth  │ │ pages  │ │ blocks │ │ hotspots (聚合)  │  │
│  └────────┘ └────────┘ └────────┘ └──────────────────┘  │
│  ┌────────┐ ┌────────┐                                    │
│  │ notes  │ │convert │  ← 旧版兼容                         │
│  └────────┘ └────────┘                                    │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  SQLite (blog.db)   │
              └─────────────────────┘
```

**技术选型**

- 后端：FastAPI + SQLModel + aiosqlite（全异步）
- 认证：python-jose (JWT) + passlib (bcrypt)
- 前端：Vue3 + Vite + TypeScript + Pinia + Vue Router + Axios
- 热点：httpx 异步拉取第三方 API，内存缓存 10 分钟

---

## 三、数据模型设计

### 3.1 用户与工作区

```
User
├── id, username, email, hashed_password
├── display_name, avatar_url
└── is_active, created_at, updated_at

Workspace（每用户一个默认工作区，可扩展多工作区）
├── id, name, owner_id → User
└── created_at
```

### 3.2 页面与 Block（核心）

```
Page（替代旧版 Note）
├── id, workspace_id, title, icon
├── category: quick_start | doc | project | website | team | custom
├── parent_id（显式父子层级）
├── sort_order, is_pinned
└── created_at, updated_at

Block（页面内容块，JSON 存储灵活内容）
├── id, page_id, type, content (JSON), sort_order
└── created_at, updated_at

PageLink（页面间链接，自动从 Block 同步）
├── source_page_id → target_page_id
└── 用于侧边栏下拉子页面 + 关系图
```

### 3.3 Block 类型

| 类型 | 说明 | content 示例 |
|------|------|-------------|
| `paragraph` | 段落/富文本 | `{"text": "markdown 内容"}` |
| `heading` | 标题 | `{"level": 1, "text": "标题"}` |
| `code` | 代码块 | `{"language": "python", "code": "..."}` |
| `quote` | 引用 | `{"text": "..."}` |
| `list` | 列表 | `{"ordered": false, "items": [...]}` |
| `image` | 图片 | `{"url": "...", "alt": "..."}` |
| `chart` | 图表 | `{"chart_type": "mermaid", "source": "..."}` |
| `divider` | 分割线 | `{}` |
| `page_link` | 页面链接 | `{"page_id": 123, "title": "子页面"}` |
| `table` | 表格 | `{"rows": [[...]]}` |
| `callout` | 提示框 | `{"type": "info", "text": "..."}` |

### 3.4 侧边栏树逻辑

侧边栏由两层结构组成：

1. **层级子页面**（`parent_id`）：显式父子关系，如「项目管理 → 子项目 A」
2. **链接子页面**（`PageLink`）：页面内 `page_link` Block 引用的页面，以下拉形式展示

```
📄 快速开始
📄 写文档
   └─ 🔗 子页面 A（通过 page_link 引用）
   └─ 🔗 子页面 B
📁 项目管理
   ├─ 📄 子项目 A（parent_id）
   └─ 📄 子项目 B（parent_id）
```

---

## 四、API 设计

所有新接口前缀：`/Taot`

### 4.1 认证 `/Taot/auth`

| 方法 | 路径 | 说明 | 需登录 |
|------|------|------|--------|
| POST | `/register` | 注册并返回 token | 否 |
| POST | `/login` | 登录 | 否 |
| POST | `/refresh` | 刷新 access token | 否 |
| GET | `/me` | 获取当前用户 | 是 |
| PATCH | `/me` | 更新个人资料 | 是 |

请求头：`Authorization: Bearer <access_token>`

### 4.2 页面 `/Taot/pages`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tree` | 侧边栏页面树（含 linked_children） |
| GET | `/graph` | 页面关系图（nodes + edges） |
| GET | `/search?q=` | 全局搜索页面标题 |
| POST | `/` | 创建页面 |
| GET | `/{page_id}` | 页面详情（含 blocks 列表） |
| PATCH | `/{page_id}` | 更新页面元信息 |
| DELETE | `/{page_id}` | 删除页面及关联 blocks/links |

### 4.3 内容块 `/Taot/blocks`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/{page_id}` | 在页面下创建 Block |
| PATCH | `/{block_id}` | 更新 Block（自动同步 PageLink） |
| DELETE | `/{block_id}` | 删除 Block |
| PUT | `/{page_id}/reorder` | 批量重排 Block 顺序 |

### 4.4 首页热点 `/Taot/hotspots`

| 方法 | 路径 | 说明 | 需登录 |
|------|------|------|--------|
| GET | `/` | GitHub + B站 + 社区热点 | 否 |

### 4.5 旧版兼容

| 前缀 | 说明 |
|------|------|
| `/Taot/notes` | v1 文件树笔记（迁移期保留） |
| `/Taot/convert` | Markdown 转 HTML |

---

## 五、前端设计（已实现）

**UI 风格**：Tailwind CSS + Inter 字体，渐变背景、毛玻璃卡片、圆角设计，参考 Notion / Linear 现代风格。

### 5.1 路由

| 路径 | 页面 | 布局 |
|------|------|------|
| `/login` | 登录 | 全屏，左侧品牌区 + 右侧表单 |
| `/register` | 注册 | 同上 |
| `/` | 首页热点 | 左侧导航栏 + 右侧热点内容 |
| `/notes` | 我的笔记 | 左侧笔记侧边栏 + 右侧 Block 编辑器 |
| `/notes/:pageId` | 具体页面 | 同上 |
| `/graph` | 关系图谱 | 左侧导航栏 + 占位页（待开发） |

路由守卫：未登录自动跳转 `/login`；已登录访问登录页自动跳转首页。

### 5.2 登录 / 注册页

```
┌────────────────────────┬──────────────────────┐
│  渐变背景 + 光斑动效      │   毛玻璃表单卡片       │
│  品牌 Logo + Slogan     │   用户名 / 密码        │
│  功能亮点标签            │   登录按钮             │
│  (lg 以上显示)          │   注册链接             │
└────────────────────────┴──────────────────────┘
```

- 左侧：品牌展示区（`from-brand-600 via-purple-600 to-indigo-800` 渐变）
- 右侧：毛玻璃卡片表单，支持错误提示、加载状态
- 移动端：仅显示表单，顶部展示 Logo

### 5.3 首页布局

```
┌──────────────┬───────────────────────────────────────┐
│  功能导航栏    │  顶部欢迎横幅（渐变 + 用户名问候）        │
│  (256px)     ├───────────────────────────────────────┤
│              │  ⭐ GitHub 热门项目（卡片网格）           │
│  Logo        │  📺 B站编程教程（卡片网格）              │
│  首页热点 ●   │  💬 编程社区（卡片网格）                │
│  我的笔记     │                                       │
│  关系图谱     │                                       │
│              │                                       │
│  👤 用户头像  │                                       │
│  退出登录     │                                       │
└──────────────┴───────────────────────────────────────┘
```

组件：`AppSidebar`（导航）、`HotspotSection` + `HotspotCard`（热点卡片）

### 5.4 笔记页布局

```
┌──────────────────┬────────────────────────────────────┐
│  笔记侧边栏 (288px) │  页面编辑器                          │
│                  │  ┌──────────────────────────────┐  │
│  👤 头像 + 用户名  │  │ 📄 页面标题    [+ 添加 Block]  │  │
│  🔍 全局搜索      │  ├──────────────────────────────┤  │
│  🕸 关系图        │  │ Block 1: 段落（点击编辑）        │  │
│  📬 消息箱 (预留)  │  │ Block 2: 代码块                 │  │
│  ⋯  更多 (预留)   │  │ Block 3: 页面链接               │  │
│  ──────────────  │  │ ...                            │  │
│  我的页面  [+]    │  │ [+ 点击添加内容]                  │  │
│  📄 页面树...     │  └──────────────────────────────┘  │
│  返回首页         │                                    │
└──────────────────┴────────────────────────────────────┘
```

组件：
- `NotesSidebar`：用户区 + 工具栏 + 页面树
- `PageTreeNode`：递归树节点（支持 `children` + `linked_children` 下拉）
- `PageEditor`：页面标题编辑 + Block 管理
- `BlockRenderer`：按类型渲染/编辑 Block（paragraph、heading、code、quote、divider、page_link、callout）

### 5.5 状态管理（Pinia）

| Store | 职责 |
|-------|------|
| `authStore` | token 持久化、登录/注册/登出、用户信息 |
| `pageStore` | 页面树、当前页面详情、Block CRUD、全局搜索 |
| `hotspotStore` | 首页三类热点数据加载 |

### 5.6 前端目录

```
frontend/
├── src/
│   ├── api/              # axios 封装 + auth/pages/hotspots 接口
│   ├── components/
│   │   ├── common/       # UserAvatar
│   │   ├── layout/       # AppSidebar（首页导航）
│   │   ├── hotspot/      # HotspotCard, HotspotSection
│   │   └── notes/        # NotesSidebar, PageTreeNode, BlockRenderer, PageEditor
│   ├── stores/           # auth, page, hotspot
│   ├── router/           # 路由 + 守卫
│   ├── types/            # TypeScript 类型定义
│   ├── views/            # Login, Register, Home, Notes, Graph
│   ├── App.vue
│   ├── main.ts
│   └── style.css         # Tailwind + 全局样式
├── tailwind.config.js
├── vite.config.ts        # 代理 /Taot → 后端 8000
└── package.json
```

---

## 六、目录结构

```
项目根目录/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── database.py             # 异步数据库连接
│   ├── models.py               # 旧模型兼容导出
│   ├── core/
│   │   ├── config.py           # 配置（JWT、数据库、CORS）
│   │   ├── security.py         # 密码哈希、JWT 签发/校验
│   │   └── deps.py             # get_current_user 依赖
│   ├── models/
│   │   ├── user.py             # User 模型
│   │   ├── page.py             # Page / Block / PageLink / Workspace
│   │   └── legacy.py           # 旧版 Note 模型
│   ├── routers/
│   │   ├── auth.py             # 认证接口
│   │   ├── pages.py            # 页面 CRUD
│   │   ├── blocks.py           # Block CRUD
│   │   ├── hotspots.py         # 首页热点
│   │   ├── notes.py            # 旧版笔记（兼容）
│   │   ├── files.py            # 文件上传管理
│   │   └── convert.py          # MD 转换
│   ├── services/
│   │   ├── page_service.py     # 页面树、关系图、链接同步
│   │   └── hotspot_service.py  # 热点聚合 + 缓存
│   └── utils/
│       └── markdown.py         # Markdown 转换 + 路径修复
├── frontend/                   # Vue3 前端
│   ├── src/
│   │   ├── api/                # API 请求层
│   │   ├── components/         # UI 组件
│   │   ├── stores/             # Pinia 状态
│   │   ├── views/              # 页面视图
│   │   └── router/             # 路由配置
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── index.html
├── static/                     # 静态资源（上传文件存储）
├── uploads/                    # 上传的 MD 文件
├── data/                       # 旧版笔记 HTML 资源（可选）
├── .env.example                # 环境变量模板（会被 Git 跟踪）
├── .env                        # 本地环境变量（自动生成，不提交 Git）
├── requirements.txt            # Python 依赖
├── import_notes.py             # 旧版笔记导入工具
├── start.bat                   # 一键启动（CMD）
├── start.ps1                   # 一键启动（PowerShell）
├── blog.db                     # SQLite 数据库（运行时生成）
└── README.md
```

---

## 七、快速开始

### 7.1 环境要求

- **Python** 3.9+
- **Node.js** 18+（推荐 18.x LTS，兼容至 22.x）

### 7.2 一键启动（推荐 ⭐）

项目根目录提供了两种启动脚本，自动完成**环境检测 → 创建配置文件 → 虚拟环境 → 依赖安装 → 服务启动**：

| 脚本 | 适用场景 | 运行方式 |
|------|---------|---------|
| `start.bat` | 双击运行（CMD） | 直接双击 |
| `start.ps1` | PowerShell（推荐） | `powershell -ExecutionPolicy Bypass -File start.ps1` |

**脚本自动执行流程（6 步）：**

```
[1/6] 检测运行环境     → 检查 Python / Node.js 是否安装，显示路径和版本
[2/6] 检查必备文件     → 自动创建 .env 配置文件（首次）
                      → 自动创建 uploads/、static/ 目录
[3/6] 配置虚拟环境     → 无 venv/ 则自动创建 python -m venv venv
[4/6] 检查后端依赖     → 未安装时自动 pip install -r requirements.txt
[5/6] 检查前端依赖     → frontend/node_modules/vite 不存在时自动 npm install
[6/6] 启动服务        → 分别在独立窗口中启动后端 (:8000) 和前端 (:5173)
```

> **开箱即用**：首次运行脚本会自动创建 `.env`（从 `.env.example` 复制默认配置），无需手动配置即可启动。

### 7.3 环境变量配置（可选）

项目启动脚本会自动创建 `.env` 文件。如需自定义配置，编辑 `.env`：

```env
# JWT 认证密钥（生产环境务必修改为随机字符串！）
# 可使用 python -c "import secrets; print(secrets.token_hex(32))" 生成
SECRET_KEY=change-me-in-production-use-env-var

# JWT 签名算法
ALGORITHM=HS256

# Access Token 过期时间（分钟），默认 1440 = 24 小时
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Refresh Token 过期时间（天）
REFRESH_TOKEN_EXPIRE_DAYS=7

# 数据库文件路径（SQLite）
DATABASE_URL=sqlite+aiosqlite:///./blog.db

# 旧版笔记数据目录（仅导入 Wolai 导出笔记时需要，新项目可忽略）
NOTES_DATA_PATH=data
```

> 详细注释见 `.env.example` 模板文件。`.env` 已在 `.gitignore` 中排除，不会被提交到 Git。

### 7.4 导入旧版笔记（可选）

如果你有从 Wolai（我来）导出的 HTML 格式笔记，可以使用导入工具：

```powershell
# 激活虚拟环境后执行

# 使用默认路径 (data/)
python import_notes.py

# 指定自定义路径（支持任意目录，灵活适配分散的笔记）
python import_notes.py ./my_notes
python import_notes.py D:/exports/wolai_backup

# 或通过环境变量设置
$env:NOTES_IMPORT_PATH = "D:/my_exports"
python import_notes.py
```

导入工具会递归扫描指定目录，自动构建层级笔记树并存入数据库。

> **注意**：`data/` 目录不再必需。如果没有旧版笔记数据，系统正常运行所有新功能（Block 编辑器、热点聚合等）。

### 7.5 后端（手动启动）

```powershell
# 在项目根目录下执行

# 激活虚拟环境（Windows）
.\venv\Scripts\Activate.ps1

# 安装依赖（首次）
pip install -r requirements.txt

# 启动后端（开发模式，热重载）
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- API 文档：http://127.0.0.1:8000/docs
- 旧版页面：http://127.0.0.1:8000/Taot

### 7.6 前端（手动启动）

```powershell
# 进入前端目录
cd .\frontend

# 安装依赖（首次）
npm install

# 启动开发服务器（代理 /Taot 到后端 8000 端口）
npm run dev
```

启动后访问：http://localhost:5173

> 需同时启动后端（8000 端口），前端通过 Vite 代理转发 `/Taot` 请求。

### 7.7 快速验证 API

```powershell
# 注册用户
curl -X POST http://127.0.0.1:8000/Taot/auth/register `
  -H "Content-Type: application/json" `
  -d '{"username":"test","email":"test@example.com","password":"123456"}'

# 获取首页热点（无需登录）
curl http://127.0.0.1:8000/Taot/hotspots/

# 创建页面（需替换 TOKEN）
curl -X POST http://127.0.0.1:8000/Taot/pages/ `
  -H "Authorization: Bearer <TOKEN>" `
  -H "Content-Type: application/json" `
  -d '{"title":"我的第一篇笔记","icon":"📝"}'
```

---

## 八、分步实施计划

| 阶段 | 内容 | 状态 |
|------|------|------|
| Phase 1 | 后端 core + JWT 认证 + 用户模型 | ✅ 已完成 |
| Phase 2 | Page / Block / PageLink 模型与 API | ✅ 已完成 |
| Phase 3 | 首页热点聚合服务 | ✅ 已完成 |
| Phase 4 | Vue3 前端：登录页 + 首页 + 笔记页 UI | ✅ 已完成 |
| Phase 5 | Block 编辑器增强（图表、代码高亮） | 🚧 进行中 |
| Phase 6 | 页面关系图可视化 + 全局搜索 UI | ⏳ 待开发 |
| Phase 7 | 旧版笔记数据迁移工具 | ⏳ 待开发 |
| Phase 8 | 消息箱、团队协作等扩展功能 | ⏳ 预留接口 |

---

## 九、核心设计原则

1. **Block 优先**：页面内容由 Block 数组组成，而非单一大段 HTML/Markdown，便于按类型渲染和扩展
2. **链接即导航**：`page_link` Block 自动同步到 `PageLink` 表，驱动侧边栏下拉和关系图，无需手动维护导航
3. **用户隔离**：所有页面操作通过 `Workspace → owner_id` 校验，保证多用户数据安全
4. **渐进迁移**：旧版 `/notes` 接口保留，新 Block 模型并行运行，降低迁移风险
5. **热点解耦**：首页热点通过独立 service 聚合 + 缓存，不侵入核心业务逻辑

---

## 十、常见问题

### Q: 启动脚本闪退怎么办？
A: 请使用 PowerShell 运行 `start.ps1`（`powershell -ExecutionPolicy Bypass -File start.ps1`）。如果 `.bat` 脚本中文乱码，将终端编码设置为 UTF-8（`chcp 65001`）。

### Q: 前端报错 "'vite' 不是内部或外部命令"？
A: 说明 `npm install` 未完成依赖安装。删除 `frontend/node_modules` 目录后重新运行启动脚本，脚本会自动检测并重新安装。

### Q: 后端报错 "Directory 'uploads' does not exist"？
A: 启动脚本会自动创建 `uploads/` 和 `static/` 目录。如果手动启动，请先运行 `mkdir uploads static`。

### Q: Node.js 版本太低怎么办？
A: 项目要求 Node.js 18+。启动脚本会自动检测版本并给出警告。推荐安装 Node.js 18 LTS 版本（下载地址：https://nodejs.org/）。

### Q: 如何重置数据库？
A: 删除 `blog.db` 文件，重启后端即可自动重建。注意这会清除所有用户和笔记数据。

### Q: 如何导入分散在不同目录的笔记？
A: 使用 `python import_notes.py <目录路径>` 指定任意路径导入，或设置环境变量 `NOTES_IMPORT_PATH`。多次运行可导入多个目录。
