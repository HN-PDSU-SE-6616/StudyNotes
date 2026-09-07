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
> 独立容器位于外部网络 `taot-net`，应用内主机名：`postgres` / `redis` / `qdrant` / `mysql`。

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
- **列表块协议**：相邻同型列表合并为一个 list 块的多行 `items`，有序编号在同一块内连号；
  前端 BlockRenderer 逐行渲染（含缩进层级 indent），无 `[object Object]` 与固定 `1.` 问题。

## 推荐（冷启动 + 加权混合）

- 新用户注册进入 `/onboarding` 两步引导（职业 → 技术栈多选，均可自定义；可跳过）。
- 画像存 `user_profile`，即时/每日刷新为画像向量与行为兴趣向量。
- 排序分：`0.40×画像相似度 + 0.25×行为相似度 + 0.25×热度(浏览量归一) + 0.10×时效衰减`
  （权重在 `.env` 用 `REC_W_PROFILE/REC_W_READ/REC_W_POP/REC_W_FRESH` 调整；
  缺少行为时其权重并入画像，反之亦然；无画像无行为时以热门+时效兜底）。

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
                  · chunker · embedding · qdrant_service · rag · storage
  tasks/          Celery：parse(解析) · index(向量) · recommend(加权混合推荐)
  worker.py       Celery 应用（队列 parse/index + beat 调度）
alembic/         数据库迁移（基线 + note.source_path + user_profile）
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
- slug 解析与项目关系图接口；
- 解析器协议（有序/无序/任务合并、表格转义、TOC、HTML 嵌套列表）；
- 目录导入成树 + 图片上链 + 链接修复 + overwrite 幂等；
- 画像 CRUD 与推荐权重归一。

（v3.1 起已移除引用旧 SQLite 模型的历史测试。）
