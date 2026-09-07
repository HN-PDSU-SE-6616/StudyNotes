"""Celery 任务公共执行器

Celery 任务为同步入口；内部通过 asyncio.run 起独立事件循环，
并使用 NullPool 的独立引擎（避免 asyncpg 连接跨 loop 复用报错）。
"""
import asyncio
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings


def run_async(coro_factory: Callable[[AsyncSession], Awaitable]):
    """同步入口包裹：为每次任务创建独立引擎与会话"""

    async def _main() -> None:
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with maker() as session:
                await coro_factory(session)
        finally:
            await engine.dispose()

    asyncio.run(_main())
