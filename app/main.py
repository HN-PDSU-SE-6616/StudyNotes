# app/main.py
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.database import init_db
from app.routers import (
    auth,
    orgs,
    projects,
    notes,
    blocks,
    files,
    rag,
    assistant,
    recommendations,
    profile,
    imports,
    hotspots,
    convert,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
    except Exception:  # noqa: BLE001
        logger.exception("数据库初始化失败（请确认 PostgreSQL 已启动并执行过迁移）")
        raise
    # 启动期确保 Qdrant collection 存在（不依赖 AI 模型时的默认维度）
    try:
        from app.services import qdrant_service

        qdrant_service.ensure_collections(vector_size=1024)
    except Exception:  # noqa: BLE001
        logger.warning("Qdrant 不可用，向量检索功能暂不可用")
    yield


app = FastAPI(
    title=settings.app_name,
    description="知识库：多组织笔记 + 文件流水线 + 向量问答 + 推荐",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = settings.api_prefix

# 静态资源（头像/旧资产等；文件实体统一走 /api/v1/files）
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ========== 新版本化 API ==========
app.include_router(auth.router, prefix=PREFIX)
app.include_router(orgs.router, prefix=PREFIX)
app.include_router(projects.collection, prefix=PREFIX)
app.include_router(projects.items, prefix=PREFIX)
app.include_router(notes.collection, prefix=PREFIX)
app.include_router(notes.items, prefix=PREFIX)
app.include_router(blocks.router, prefix=PREFIX)
app.include_router(files.router, prefix=PREFIX)
app.include_router(rag.router, prefix=PREFIX)
app.include_router(assistant.router, prefix=PREFIX)
app.include_router(profile.router, prefix=PREFIX)
app.include_router(recommendations.router, prefix=PREFIX)
app.include_router(imports.router, prefix=PREFIX)
app.include_router(hotspots.router, prefix=PREFIX)
app.include_router(convert.router, prefix=PREFIX)


# ========== /docs 保护：仅允许 localhost 访问 ==========

@app.middleware("http")
async def protect_docs(request: Request, call_next):
    """禁止外部访问 /docs、/redoc、/openapi.json"""
    if request.url.path in ("/docs", "/redoc", "/openapi.json"):
        host = request.headers.get("host", "")
        if "localhost" not in host and "127.0.0.1" not in host:
            return Response(status_code=404)
    return await call_next(request)


# ========== 生产环境：前端 SPA 静态文件服务 ==========

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(FRONTEND_DIST):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")),
        name="frontend_assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """所有非 API/静态文件路径返回前端 index.html（SPA 模式）"""
        # API 未命中一律 JSON 404，避免返回 HTML 干扰前端错误处理
        prefix = PREFIX.strip("/")
        if full_path.startswith(prefix + "/") or full_path in (prefix,):
            return Response(status_code=404, content='{"detail":"Not Found"}', media_type="application/json")
        if full_path.startswith("static/"):
            return Response(status_code=404)
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not built. Run: cd frontend && npm run build"}
