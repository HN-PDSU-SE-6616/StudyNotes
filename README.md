# Taot 知识库（NoteLog）

多组织、支持 RAG 问答与个性化推荐的知识库系统。

**架构**：FastAPI + PostgreSQL(asyncpg) + Qdrant + Celery/Redis + sentence-transformers(BGE-M3) + OpenAI 兼容 LLM(DeepSeek) + Vue3 + TailwindCSS。

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
> 独立容器位于外部网络 `taot-net`，应用内主机名：`taot-postgres` / `taot-redis` / `qdrant` / `taot-mysql`。

启用本地 Embedding（镜像较大，需安装 torch）：

```bash
docker compose build --build-arg ENABLE_AI=1 backend worker
# 注：backend/worker/beat 共用镜像，一次 build-arg 即同时启用
```

> Docker 镜像内以 uv.lock 冻结安装；前端由多阶段构建自动产出。

## 本地开发

前置：uv（>=0.5）、Node 18+、Docker。Python 版本由 `.python-version` 锁定为 **3.12**。

一键部署（含环境、迁移与全部服务）：`start.bat` 或 `start.ps1`（两者同步更新）。

```bash
# 1. 独立基础服务（幂等，可重复执行）
powershell -ExecutionPolicy Bypass -File deploy/infra.ps1
# 2. 安装依赖（uv.lock 冻结；若容器运行应用则跳过，改为 docker compose up -d --build backend worker beat）
uv sync --frozen
# RAG/推荐需本地 Embedding（体积较大）：
uv sync --extra ai

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
| `DATABASE_URL` | PostgreSQL 异步 URL | `postgresql+asyncpg://taot:taot@localhost:5432/taot` |
| `QDRANT_URL` | 向量库 | `http://localhost:6333` |
| `REDIS_URL` | Celery/缓存 | `redis://localhost:6379/0` |
| `STORAGE_ROOT` | 对象存储根（LocalFS） | `storage` |
| `EMBEDDING_MODEL` | BGE 模型名/路径（空=关闭 RAG） | `BAAI/bge-m3` |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | OpenAI 兼容 LLM（DeepSeek） | 空 / `https://api.deepseek.com/v1` / `deepseek-chat` |
| `SECRET_KEY` | JWT 密钥（生产务必修改） | - |

## 数据流

```
前端 multipart 上传
   → /api/v1/files/upload：StorageProvider 落盘 + file_metadata(PENDING)
   → Celery parse_document：读文件 → 解析为 NoteBlock（PDF 保留页码、MD 保留标题层级）
   → file_metadata(COMPLETED) → Celery index_note：chunker 切片(带 heading_path/page/anchor)
   → Qdrant kb_notes（payload 含 org/project/owner/is_public 权限过滤字段）
提问 → /api/v1/rag/ask：检索(权限过滤) → 上下文 → DeepSeek → 答案 + sources(锚点)
推荐 → Celery beat 每日刷新兴趣向量(user_profiles) → Redis 缓存 → /api/v1/recommendations
```

引用跳转：前端按 `heading_path` / `page` 定位并滚动高亮笔记原文对应章节。

## 权限模型

- **RBAC（组织/项目级）**：`owner > admin > maintainer > reporter > guest`；
  项目成员角色可覆盖组织角色。
- **ABAC（笔记级）**：`is_public`、`owner_id`、`note_acl`（read/write/delete 显式授权）。
- 所有查询收敛于 `app/core/permissions.py`；不可见资源统一 404，避免信息泄露。

## 目录结构

```
app/
  core/           配置 · JWT · 权限中间层(RBAC/ABAC)
  models/         user/org/project/note/file（SQLModel + PG JSONB）
  routers/        auth · orgs · projects · notes · blocks · files · rag · recommendations
  services/       note_service · parser(文档解析) · chunker · embedding · qdrant_service · rag · storage
  tasks/          Celery：parse(解析) · index(向量) · recommend(推荐)
  worker.py       Celery 应用（队列 parse/index + beat 调度）
alembic/         数据库迁移（基线 + note_view_log）
db/partition/    表分区启用指引（预留）
frontend/        Vue3 + Pinia + Tailwind；组织/项目切换、移动端抽屉、AI 问答面板
docker-compose.yml  backend · worker · beat（基础服务由 deploy/infra.ps1 独立运行）
deploy/infra.ps1    独立基础容器编排：postgres/redis/qdrant/mysql → 外部网络 taot-net
wait_services.py    容器启动依赖等待（backend/worker/beat 入口）
```

## 测试

`uv run pytest -q`（独立测试库 `taot_test`，自动建库并迁移）。覆盖：
- 注册自动创建个人组织/项目；RBAC 隔离（跨用户访问统一 404 不泄露）；
- 组织邀请 reporter 后只读可访问、写操作 403；
- 笔记/Block CRUD、统计浏览计数；文件 asset 上传/读回一致；
- slug 解析与项目关系图接口。

（v3.1 起已移除引用旧 SQLite 模型的历史测试。）
