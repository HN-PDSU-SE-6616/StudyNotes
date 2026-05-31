# import_notes.py
import os
import asyncio
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, async_session
from app.models import Note


NOTES_ROOT = os.path.abspath("data")
RESERVED_DIRS = {"media", "css", "fonts"}


async def import_directory(session: AsyncSession, current_dir: str, parent_id: int = None):
    dir_name = os.path.basename(current_dir)

    # 1. 寻找当前笔记目录下的 HTML 文件
    # 注意：这里假设一个笔记目录下会有一个 main.html 或 index.html
    html_file = None
    for file in os.listdir(current_dir):
        if file.endswith(".html"):
            html_file = file
            break

    # 如果没找到HTML，且该目录不是根目录，可能这只是一个纯分类目录
    # 但只要是有内容的目录，我们就创建一个数据库条目
    relative_path = os.path.relpath(current_dir, start=NOTES_ROOT) if html_file else None

    note = Note(
        title=dir_name,
        parent_id=parent_id,
        content_type="file" if html_file else "db",
        content_path=relative_path,  # 记录目录路径，而不是单个文件路径
        is_published=True
    )
    session.add(note)
    await session.flush()

    # 2. 递归处理子目录
    for item in os.listdir(current_dir):
        sub_path = os.path.join(current_dir, item)
        if os.path.isdir(sub_path):
            # 跳过系统保留目录
            if item.lower() in RESERVED_DIRS:
                continue

            # 继续递归
            await import_directory(session, sub_path, parent_id=note.id)


async def main():
    # 确保数据库表已创建
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    print(f"开始扫描目录: {NOTES_ROOT}")
    if not os.path.exists(NOTES_ROOT):
        print(f"错误: 目录 {NOTES_ROOT} 不存在，请先解压你的 zip 包到该路径下！")
        return

    async with async_session() as session:
        try:
            # 遍历根目录下的第一级目录和文件
            for item in os.listdir(NOTES_ROOT):
                item_path = os.path.join(NOTES_ROOT, item)
                if os.path.isdir(item_path):
                    await import_directory(session, item_path, parent_id=None)

            # 一起提交
            await session.commit()
            print("🎉 导入完成！所有目录已转为层级数据结构。")
        except Exception as e:
            await session.rollback()
            print(f"❌ 导入失败，已回滚更改。错误: {e}")


if __name__ == "__main__":
    asyncio.run(main())
