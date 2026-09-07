"""Embedding/Qdrant 运维脚本：重建向量集合与全量重索引

场景：更换/升级 Embedding 模型后维度变化（如 M3 1024 → bge-small-zh 512），
Qdrant collection 维度不匹配时报错——本脚本按“当前配置”重建集合并（可选）全量重索引。

用法（容器内/宿主均可）：
    python scripts/rebuild_embeddings.py --reset              # 仅重建集合
    python scripts/rebuild_embeddings.py --reset --reindex    # 重建 + 重索引全部笔记

警告：--reset 会清空 kb_notes / user_profiles 集合（不删除笔记与文件数据），
重索引后向量按当前模型重新生成。
"""
import argparse
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

sys.path.insert(0, ".")
sys.path.insert(0, "/app")  # 容器内以 /app 为工作目录

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402
from sqlmodel import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.models.note import Note  # noqa: E402
from app.services import embedding, qdrant_service  # noqa: E402


def reset_collections(dim: int) -> None:
    client = qdrant_service.get_client()
    for name in (qdrant_service.KB_NOTES_COLLECTION, qdrant_service.USER_PROFILES_COLLECTION):
        if client.collection_exists(name):
            client.delete_collection(name)
            print(f"已删除 collection: {name}")
    qdrant_service.ensure_collections(vector_size=dim)
    print(f"已重建 collections（dim={dim}）")


async def reindex_all() -> int:
    from app.tasks.index import _index_note

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    count = 0
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            rows = await session.execute(select(Note.id))
            note_ids = list(rows.scalars().all())
        for note_id in note_ids:
            try:
                async with maker() as session:
                    await _index_note(note_id, session)
                count += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  索引失败 note={note_id}: {exc}")
    finally:
        await engine.dispose()
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="重建 Qdrant 集合并按需重索引")
    parser.add_argument("--reset", action="store_true", help="删除并重建 kb_notes/user_profiles")
    parser.add_argument("--reindex", action="store_true", help="重建后全量重索引所有笔记")
    args = parser.parse_args()

    if not args.reset and not args.reindex:
        parser.print_help()
        return 2
    if not embedding.is_configured():
        print("Embedding 未配置（EMBEDDING_MODEL / EMBEDDING_PRESET 为空），跳过")
        return 0

    dim = embedding.dimension()
    print(f"当前 Embedding 配置: provider={embedding.provider()} "
          f"model={embedding.model_name()} dim={dim}")
    if args.reset:
        reset_collections(dim)
    if args.reindex:
        if embedding.provider() != "local" and not embedding.is_configured():
            print("远程 Embedding 配置不完整，跳过重索引")
            return 0
        total = asyncio.run(reindex_all())
        print(f"重索引完成: {total} 篇笔记")
    print("完成。请重启 backend/worker 后验证 RAG/推荐。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
