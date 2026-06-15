# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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
