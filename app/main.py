# app/main.py
from contextlib import asynccontextmanager

import aiofiles
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import HTMLResponse

from app.database import init_db
from app.routers import notes, convert


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    await init_db()
    yield


app = FastAPI(
    title="个人博客 API",
    description="笔记管理 + Markdown 转换工具",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS（方便前端本地调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 根路由后缀
PREFIX = "/Taot"

# 挂载静态文件
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/note_assets", StaticFiles(directory="data"), name="note_assets")

# 注册路由
app.include_router(notes.router, prefix=PREFIX)
app.include_router(convert.router, prefix=PREFIX)


@app.get(PREFIX, response_class=HTMLResponse)
async def root():
    async with aiofiles.open("templates/index.html", mode='r', encoding='utf-8') as f:
        html = await f.read()
    return html
