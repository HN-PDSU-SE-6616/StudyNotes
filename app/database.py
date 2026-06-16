# app/database.py
from sqlmodel import SQLModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    # 确保所有表模型被注册
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    # 为已有页面补充 slug（新增列兼容）
    await _backfill_slugs()
    # 页面统计相关列
    await _backfill_page_stats_columns()


async def _backfill_slugs():
    """为没有 slug 的已有页面生成唯一标识符"""
    import secrets
    async with async_session() as session:
        try:
            # 尝试添加列（如果已存在则忽略）
            await session.execute(text("ALTER TABLE page ADD COLUMN slug VARCHAR(16)"))
            await session.commit()
        except Exception:
            await session.rollback()
        # 填充空 slug
        result = await session.execute(text("SELECT id FROM page WHERE slug IS NULL OR slug = ''"))
        rows = result.fetchall()
        for (pid,) in rows:
            new_slug = secrets.token_urlsafe(12)[:16]
            await session.execute(text("UPDATE page SET slug = :s WHERE id = :i"), {"s": new_slug, "i": pid})
        if rows:
            await session.commit()
        # 创建唯一索引
        try:
            await session.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_page_slug ON page(slug)"))
            await session.commit()
        except Exception:
            await session.rollback()


async def _backfill_page_stats_columns():
    """添加页面统计相关列（creator_id, last_editor_id, view_count）"""
    columns = [
        "ALTER TABLE page ADD COLUMN creator_id INTEGER REFERENCES user(id)",
        "ALTER TABLE page ADD COLUMN last_editor_id INTEGER REFERENCES user(id)",
        "ALTER TABLE page ADD COLUMN view_count INTEGER DEFAULT 0",
    ]
    async with async_session() as session:
        for sql in columns:
            try:
                await session.execute(text(sql))
                await session.commit()
            except Exception:
                await session.rollback()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
