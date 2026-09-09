# Taot 知识库（NoteLog）

多组织、支持 RAG 问答与个性化推荐的知识库系统。

**架构**：FastAPI + PostgreSQL(asyncpg) + Qdrant + Celery/Redis + sentence-transformers(BGE) + OpenAI 兼容 LLM(DeepSeek) + Vue3 + TailwindCSS。

> v3.1 重构：废弃旧 SQLite/Workspace/Page 数据模型，全新建模 org/project/note/file + RBAC/ABAC 权限；
> 工程管理使用 uv（Python 3.12，依赖由 uv.lock 严格锁定）；旧内容（`data/`、`uploads/`）仅作归档，如需保留请用文件上传流水线重新导入。
>
> 仓库：`git@github.com:HN-PDSU-SE-6616/StudyNotes.git`（master）

## 快速开始（Docker 一键）

基础服务（PostgreSQL/Redis/Qdrant/MySQL）为**独立容器**，应用用 Docker Compose 编排，`compose down` 不影响基础服务与数据卷。

```bash
# 1. 确保独立基础服务（幂等；已存在则复用；端口被本机服务占用则跳过并提示）
powershell -ExecutionPolicy Bypass -File deploy/infra.ps1

# 2. 启动后端 + Celery worker + beat（自动等基础服务、执行 alembic 迁移）
docker compose up -d --build backend worker beat

# 3. 访问
# 后端 API:      http://localhost:8000/api/v1 （交互文档 http://localhost:8000/docs 仅本机）
# 前端 SPA:      http://localhost:8000
```

> 补建 MySQL（需先以管理员释放 3306：`Stop-Service MySQL84; Set-Service MySQL84 -StartupType Disabled`）：
> `powershell -ExecutionPolicy Bypass -File deploy/infra.ps1 -OnlyMysql`
>
> **环境感知**：若本机已有同端口服务，`deploy/infra.ps1` 会跳过该容器并提示；此时把连接地址改为本机服务即可（不重复创建）。
> 独立容器位于外部网络 `taot-net`，应用内主机名：`postgres` / `redis` / `qdrant` / `mysql`。

启用本地 Embedding（镜像较大，需安装 torch）：

```bash
docker compose build --build-arg ENABLE_AI=1 backend worker
# 注：backend/worker/beat 共用镜像，一次 build-arg 即同时启用
```

> Docker 镜像内以 uv.lock 冻结安装；前端由多阶段构建自动产出。
> 应用容器（backend/worker/beat）日志驱动统一 `json-file`：单文件 ≤20MB、保留 3 份。

## 本地开发（后端在本机，基础服务与 Embedding 在容器）

前置：uv（>=0.5）、Node 18+、Docker。Python 版本由 `.python-version` 锁定为 **3.12**。

一键部署（含环境、迁移与全部服务）：`start.bat` 或 `start.ps1`（两者同步更新）。

```bash
# 1. 独立基础服务（幂等，可重复执行；容器自带 json-file 日志轮换 20m×3）
powershell -ExecutionPolicy Bypass -File deploy/infra.ps1
# 2. 安装依赖（uv.lock 冻结）
uv sync --frozen
# 仅当在宿主机跑本地 Embedding（torch/sentence-transformers）才需要：uv sync --extra ai
# 推荐：Embedding 走容器内 bge-small-zh 服务（见“Embedding”小节），宿主机免 torch。

# 3. 数据库迁移
uv run alembic upgrade head

# 4. 后端 + Worker + Beat（各开一个终端）
uv run uvicorn app.main:app --reload --port 8000
uv run celery -A app.worker.celery_app worker -Q parse,index -l info -P solo   # Windows
uv run celery -A app.worker.celery_app beat -l info    # 每日 02:00 刷新推荐

# 5. 前端（Vite dev）
cd frontend && npm install && npm run dev   # http://localhost:5173

# 6. 测试
uv run pytest -q
```

### 配置（.env）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL 异步 URL | `postgresql+asyncpg://taot:taot@127.0.0.1:5432/taot` |
| `QDRANT_URL` | 向量库 | `http://127.0.0.1:6333` |
| `REDIS_URL` | Celery/缓存 | `redis://127.0.0.1:6379/0` |
| `STORAGE_ROOT` | 对象存储根（LocalFS） | `storage` |
| `EMBEDDING_MODEL` | 模型名（本地=sentence-transformers 名；远程=服务端注册名） | 空=关闭 RAG |
| `EMBEDDING_BASE_URL` / `EMBEDDING_API_KEY` | 远程 Embedding（OpenAI 兼容） | 空 |
| `EMBEDDING_PRESET` / `EMBEDDING_DIM` | 维度推断 / 显式对齐 | bge-small-zh=512 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI 兼容 LLM（DeepSeek） | 空 / `https://api.deepseek.com/v1` / `deepseek-chat` |
| `SECRET_KEY` | JWT 密钥（生产务必修改） | - |

## 数据流

```
前端 multipart 上传
   → /api/v1/files/upload：StorageProvider 落盘 + file_metadata(PENDING, category)
   → Celery parse_document：读文件 → 解析为 NoteBlock（PDF 保留页码、MD 保留标题层级）
   → file_metadata(COMPLETED) → Celery index_note：chunker 切片(带 heading_path/page/anchor)
   → Qdrant kb_notes（payload 含 org/project/owner/is_public 权限过滤字段）
提问 → /api/v1/rag/ask：检索(权限过滤) → 上下文 → DeepSeek → 答案 + sources(锚点)
推荐 → Celery beat 每日刷新：画像(职业+技术栈)与行为兴趣向量(user_profiles) → Redis 缓存 → /api/v1/recommendations
```

引用跳转：前端按 `heading_path` / `page` 定位并滚动高亮笔记原文对应章节。

## 导入与内容解析（v3.2 恢复 v2 语义）

- **单文件**：`POST /api/v1/files/upload`（purpose=document）→ Celery 解析为笔记；
  Markdown 支持有序/无序/任务列表连续项、表格转义、TOC 剥离、图片相对路径改写；
  HTML 支持 ul/ol 嵌套列表、table/blockquote/pre/img；标题默认取自首个 H1。
- **目录/多文件批量**：`POST /api/v1/projects/{id}/import`（multipart，filename 保留
  `webkitRelativePath`）→ 目录结构 = Note 树；`image/media/...` 资源目录自动上传为
  asset 并改写引用；跨文档 `[x](dir/a.md)` 链接修复为 `/notes/{slug}` 跳转；
  重复导入由 `note.source_path` 幂等判定（overwrite=false 跳过 / true 重建）。
  **导入到“当前选中页”时**：选中页直接改名为导入目录名并充当目录容器——与目录同名
  文档内容并入该页，其余文件/子目录按结构建为其子页面（`target_renamed/target_title`
  标志前端展示）；不再套“同名容器页”。
- **列表块协议**：相邻同型列表合并为一个 list 块的多行 `items`，有序编号在同一块内连号；
  前端 BlockRenderer 逐行渲染（含缩进层级 indent），无 `[object Object]` 与固定 `1.` 问题。

## 文件分类存储（用户 → 类型）

- `file_metadata` 新增 `category`（document/note_image/note_asset/user_avatar/assistant_icon/
  assistant_bg/assistant_media）与 `source_path`（导入时保留原始相对路径）；
- 新文件落盘目录：`storage_root/{owner_id}/{category}/{yyyy}/{mm}/{file_id}{ext}`；
  存量文件 storage_key 不变，可继续读取，不做物理迁移；
- 用户级媒体（头像/AI 小助手图标与背景等）：`POST /api/v1/files/mine` 上传（无需 project_id），
  `GET /api/v1/files/mine/{id}/content` 访问；
- 媒体 `<img>` 无法携带 Authorization 请求头：文件内容接口支持 `?access_token=`，
  前端统一由 `frontend/src/utils/media.ts` 的 `mediaUrl()` 附加。

## 推荐（冷启动 + 加权混合）

- 新用户注册进入 `/onboarding` 两步引导（职业 → 技术栈多选，均可自定义；可跳过）。
- 画像存 `user_profile`，即时/每日刷新为画像向量与行为兴趣向量。
- 排序分：`0.40×画像相似度 + 0.25×行为相似度 + 0.25×热度(浏览量归一) + 0.10×时效衰减`
  （权重在 `.env` 用 `REC_W_PROFILE/REC_W_READ/REC_W_POP/REC_W_FRESH` 调整；
  缺少行为时其权重并入画像，反之亦然；无画像无行为时以热门+时效兜底）。

## 批量清理（误导入修复）

- 侧栏「我的页面 → 批量删除」：多选页面（每项含其子树）批量删除；
- 对应接口：`POST /api/v1/notes/batch-delete`（保留 `DELETE /api/v1/projects/{id}/notes/` 供运维/脚本）。

## Embedding：本地 / 远程（OpenAI 兼容）

默认本地（sentence-transformers，需 `uv sync --extra ai`）。**推荐本机部署方式**：
后端跑在本机，Embedding 用独立容器里的 bge-small-zh 服务（映射 `6080:80`，OpenAI 兼容带 key）：

```dotenv
EMBEDDING_PROVIDER=api
EMBEDDING_BASE_URL=http://127.0.0.1:6080      # 若服务路由挂在 /v1 下报 404，改 6080/v1
EMBEDDING_API_KEY=your-embedding-service-key
EMBEDDING_MODEL=bge-small-zh                    # 必须为容器内注册的模型名（非 HF 名）
EMBEDDING_PRESET=bge-small-zh                   # 供维度推断 512
EMBEDDING_DIM=512
```

未配置或调用失败时 RAG/推荐/索引任务会给出可读错误并静默降级；Qdrant collection
已存在但维度不一致时会明确报错，提示对齐 `EMBEDDING_DIM` 或重建 collection
（本机直接 `uv run python scripts/rebuild_embeddings.py --reset --reindex`）。

## 悬浮 AI 助手（全局，Agent）

登录后所有页面右下角悬浮球（**桌宠式**：可拖拽定位并记忆位置；可隐藏/找回；默认开启漂浮特效）。
面板支持全屏/窗口切换（PC），移动端打开即全屏并适配底部安全区。功能：
- 对话方式：自由对话（Agent，`POST /api/v1/assistant/chat` 与 `/chat/stream` SSE）
  或知识库问答（RAG）；模型/密钥由后端 `.env`（`LLM_MODEL/LLM_API_KEY`）统一管理；
- **工具函数（可扩展）**：注册表 `app/services/tools.py`，对话自动 function calling：
  `search_knowledge_base`（RAG 检索当前/可访问项目的笔记片段，供自由对话直接回答
  “我的笔记/知识库内容”类问题）· `get_weather`（open-meteo 实时天气）·
  `get_ip`（公网/内网 IP）· `get_system_info`（服务端 + 浏览器客户端 CPU/GPU/内存，
  客户端参数由前端采集注入）· `fetch_web_page`（httpx + BeautifulSoup4 提取网页正文）·
  `web_search`（DuckDuckGo）· `web_research`（研究工作流：拆词→多源搜索→抓正文→要点汇总）；
  模型不支持 tools 时自动降级为普通对话；知识库工具走后端 RBAC（仅检索用户可访问项目）；
  同一轮多个工具并行执行，工具轮数上限 8；
- **计划层（深度规划）**：`mode=auto` 下启发式识别“同时/对比/结合”等多意图复杂问题，
  先经轻量 LLM 拆成 1~5 个子任务（知识库/联网/实时分组）逐项执行，再综合回答；
  流式接口先下发 `steps` 事件供前端展示“任务拆解执行中”进度；可在设置里关闭；
- **会话上下文**：`session_id` 记忆最近对话（Redis，每用户隔离），`POST /assistant/context/clear` 清空；
- **上下文感知热缓存**：同一用户重复/近似问题直接复用；**会话语境不同时不硬回放**——
  缓存仅作参考提示，由 LLM 结合当前语境重答（问题 + 最近会话指纹判定）；
- **外观配置**：浅色/深色（黑白）主题、面板背景（色板/渐变或上传图片）、图标（预设 emoji
  或上传图片，登录后上传至 `/api/v1/files/mine` 分类存储）、悬浮球尺寸/色板/整体透明度、
  创造性温度、问候语与角色 Prompt 预设；
- **Markdown 渲染**：助手回复以 HTML 渲染（粗体/列表/引用/代码块/表格，流式中未闭合
  代码围栏以纯文本保护），经 DOMPurify 消毒；
- DIY：自定义 CSS/JS（作用于 `.taot-assistant-*` 类名；默认特效 CSS 示例在输入框中可见可改写）。

### Embedding 模型预设（小/中/大自行选择）

.env 配置 `EMBEDDING_PRESET` 一键切换（未设置时用显式 `EMBEDDING_MODEL` + `EMBEDDING_DIM`）：

| preset | 模型 | 维度 | 说明 |
| --- | --- | --- | --- |
| bge-small-zh | BAAI/bge-small-zh-v1.5 | 512 | 中文轻量（CPU 推荐、最快） |
| bge-base-zh | BAAI/bge-base-zh-v1.5 | 768 | 中文中量（平衡） |
| bge-large-zh | BAAI/bge-large-zh-v1.5 | 1024 | 中文重量（精度高） |
| bge-m3 | BAAI/bge-m3 | 1024 | 多语言重量（需较高资源/30 系显卡更佳） |
| bge-small-en | BAAI/bge-small-en-v1.5 | 384 | 英文轻量 |
| bge-base-en | BAAI/bge-base-en-v1.5 | 768 | 英文中量 |
| openai-3-small | text-embedding-3-small | 1536 | 远程 API（需 PROVIDER=api） |
| openai-3-large | text-embedding-3-large | 3072 | 远程 API（需 PROVIDER=api） |

> 更换模型导致维度变化后，Qdrant 会提示维度不一致。执行重建并重索引：
> `docker compose exec backend python /app/scripts/rebuild_embeddings.py --reset --reindex`
> 本机运行：`uv run python scripts/rebuild_embeddings.py --reset --reindex`

## 本地快速迭代（改代码秒级生效，避免重复 build）

每次只改 `app/**/*.py` / `scripts` / 前端源码时，**不必重新 `docker compose build`**（镜像内 AI 依赖重装很慢）：

```bash
# 1) 一次性构建（依赖变更时才需要，如新增 Python 包）
docker compose build --build-arg ENABLE_AI=1 backend worker beat

# 2) 日常开发：叠加 dev 覆盖层（把宿主源码只读挂进容器）
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d backend worker

# 3) 改了 Python 代码 → 秒级重启即可生效
#    docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend worker

# 4) 改了前端源码 → 先构建产物再重启
#    cd frontend && npm run build
#    docker compose -f docker-compose.yml -f docker-compose.dev.yml restart backend
```

提速要点：
- `.dockerignore` 已排除 `.git/`（约 100MB+ 构建上下文）；
- Dockerfile 的 `uv sync` 使用 BuildKit cache mount（`/root/.cache/uv`），即便该层被重跑，
  torch/AI 依赖也只下载一次，之后从缓存秒装。

## Docker：安装本地 Embedding（torch + BGE）并防重复加载

```bash
# 构建包含 torch + sentence-transformers 的镜像（首次下载较大，一次性）
docker compose build --build-arg ENABLE_AI=1 backend worker beat
# 启动：backend/worker 入口会自动执行 preload_model.py 预热
# 模型缓存于命名卷 taot_hf_cache（HF_HOME），重启不重复下载；首次拉取较慢
```

未启用 AI 或模型未配置时，preload 会打印提示并正常跳过；远程 Embedding
（`EMBEDDING_PROVIDER=api`）同样无需本地模型。

## 容器日志与运维（轮换 / 清理）

- 所有项目容器（backend/worker/beat）与基础服务容器（infra.ps1 创建）统一使用
  `json-file` 日志驱动：单文件 ≤20MB、保留 3 份（每容器 ≤60MB），防日志无限累计吃满磁盘；
- Docker 原生不支持按“天数”轮换：时间维度保留（默认 3 天）用可选脚本近似实现——
  `scripts/cleanup_docker_logs.ps1`（解析各容器 `-json.log` 时间戳，截断超期条目；
  仅当日志确有超期且 ≥20MB 时才 stop→截断→start）。注册每日计划任务示例见脚本头注释；
- Docker Desktop 全局兜底：可在设置中配置 daemon 默认日志参数 `max-size=20m, max-file=3`。

## 监控与观测（APM：Prometheus + Grafana）

- 后端已内置 `/metrics`（prometheus-client）：HTTP 请求计数/耗时直方图/并发、
  Agent 工具调用计数；本地预览 `http://127.0.0.1:8000/metrics`；
- 一键编排：`docker compose -f deploy/monitoring/docker-compose.yml up -d`
  （Prometheus 9090 / Grafana 3000，admin/admin，预置“Taot 后端监控”面板）；
- 详细指标/抓取目标/Grafana 查询示例见 `docs/开发环境与工具汇总.md` 第 8 节。

## 权限模型

- **RBAC（组织/项目级）**：`owner > admin > maintainer > reporter > guest`；
  项目成员角色可覆盖组织角色。
- **ABAC（笔记级）**：`is_public`、`owner_id`、`note_acl`（read/write/delete 显式授权）。
- 所有查询收敛于 `app/core/permissions.py`；不可见资源统一 404，避免信息泄露。

## 目录结构

```
app/
  core/           配置 · JWT · 权限中间层(RBAC/ABAC)
  models/         user/org/project/note/file/profile（SQLModel + PG JSONB）
  routers/        auth · orgs · projects · notes · blocks · files · imports · profile · rag · recommendations
  services/       note_service · parser(文档解析) · importer(树导入) · careers(画像词典)
                  · chunker · embedding · qdrant_service · rag · storage · agent · agent_flow(计划层) · tools
  tasks/          Celery：parse(解析) · index(向量) · recommend(加权混合推荐)
  worker.py       Celery 应用（队列 parse/index + beat 调度）
alembic/         数据库迁移（基线 + note.source_path + user_profile + file.category/source_path）
db/partition/    表分区启用指引（预留）
frontend/        Vue3 + Pinia + Tailwind；组织/项目切换、移动端抽屉、AI 桌宠助手、笔记 TOC
docker-compose.yml  backend · worker · beat（基础服务由 deploy/infra.ps1 独立运行）
deploy/infra.ps1    独立基础容器编排：postgres/redis/qdrant/mysql → 外部网络 taot-net
scripts/         日志清理(cleanup_docker_logs.ps1) · Embedding 重建(rebuild_embeddings.py)
wait_services.py    容器启动依赖等待（backend/worker/beat 入口）
```

## 测试

`uv run pytest -q`（独立测试库 `taot_test`，自动建库并迁移）。覆盖：
- 注册自动创建个人组织/项目；RBAC 隔离（跨用户访问统一 404 不泄露）；
- 组织邀请 reporter 后只读可访问、写操作 403；
- 笔记/Block CRUD、统计浏览计数；文件 asset 上传/读回一致；
- slug 解析与项目关系图接口；
- 解析器协议（有序/无序/任务合并、表格转义、TOC、HTML 嵌套列表）；
- 目录导入成树 + 图片上链 + 链接修复 + overwrite 幂等；
- 画像 CRUD 与推荐权重归一。

（v3.1 起已移除引用旧 SQLite 模型的历史测试。）
