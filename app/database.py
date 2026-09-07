# app/database.py
"""数据库引擎与会话（PostgreSQL asyncpg；兼容 SQLite 用于测试）"""
import logging
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _ensure_storage_dirs() -> None:
    """确保 git 不追踪的目录存在（上传/静态/对象存储根）"""
    for _dir in (settings.storage_root, "static", "uploads"):
        os.makedirs(_dir, exist_ok=True)


def run_migrations() -> None:
    """以子进程执行 alembic upgrade head（保证工作目录正确加载 .env）"""
    project_root = Path(__file__).resolve().parent.parent
    ini = project_root / "alembic.ini"
    if not ini.exists():
        raise FileNotFoundError("缺少 alembic.ini，请先完成 Alembic 初始化")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"数据库迁移失败:\n{result.stdout}\n{result.stderr}")
    logger.info("Alembic 迁移完成")


async def init_db() -> None:
    """应用启动初始化：
    1) 优先执行 Alembic 迁移；
    2) 若 alembic 不可用（例如仅测试环境），退回 create_all 兜底。
    """
    _ensure_storage_dirs()
    try:
        run_migrations()
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("Alembic 迁移不可用，退回 create_all：%s", exc)

    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
