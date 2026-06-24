# app/main.py
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.database import init_db
from app.routers import notes, convert, auth, pages, blocks, hotspots, files


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="知识库：笔记管理 + 热点聚合",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = settings.api_prefix

# Auto-create directories that git doesn't track (for fresh clones)
for _dir in ("uploads", "static"):
    os.makedirs(_dir, exist_ok=True)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/note_assets", StaticFiles(directory="data"), name="note_assets")

app.include_router(auth.router, prefix=PREFIX)
app.include_router(pages.router, prefix=PREFIX)
app.include_router(blocks.router, prefix=PREFIX)
app.include_router(hotspots.router, prefix=PREFIX)
app.include_router(notes.router, prefix=PREFIX)
app.include_router(convert.router, prefix=PREFIX)
app.include_router(files.router, prefix=PREFIX)


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
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not built. Run: cd frontend && npm run build"}
