"""笔记向量索引任务：index_note / delete_note_index"""
import logging

from sqlalchemy import select
from sqlmodel import select as sm_select  # noqa: F401

from app.models.note import Note, NoteBlock
from app.models.project import Project
from app.services import chunker, embedding, qdrant_service
from app.tasks.common import run_async
from app.worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.index.index_note", bind=True, max_retries=1)
def index_note(self, note_id: str) -> None:
    """对单篇笔记全量重建向量索引（幂等：先删后写）"""
    try:
        run_async(lambda session: _index_note(note_id, session))
    except Exception as exc:  # noqa: BLE001
        logger.exception("索引笔记失败 note=%s", note_id)
        raise self.retry(exc=exc, countdown=20)


async def _index_note(note_id: str, session) -> None:
    note = await session.get(Note, note_id)
    if not note:
        return
    project = await session.get(Project, note.project_id)
    if not project:
        return
    if not embedding.is_configured():
        logger.warning("Embedding 未配置，跳过向量索引 note=%s", note_id)
        return

    result = await session.execute(
        select(NoteBlock).where(NoteBlock.note_id == note_id).order_by(NoteBlock.sort_order)
    )
    blocks = result.scalars().all()
    block_dicts = [{"type": b.type, "content": b.content or {}} for b in blocks]

    chunks = chunker.chunk_blocks_with_index(block_dicts, fallback_heading=note.title or "未命名")
    # 无论是否有内容都先清掉旧向量，保证幂等
    qdrant_service.delete_note_index(note_id)
    if not chunks:
        logger.info("笔记无可索引内容 note=%s", note_id)
        return

    qdrant_service.ensure_collections(vector_size=embedding.dimension())
    vectors = embedding.embed_texts([c["text"] for c in chunks])
    payload_note = {
        "id": note.id,
        "project_id": note.project_id,
        "org_id": project.organization_id,
        "owner_id": note.owner_id,
        "is_public": note.is_public,
        "title": note.title,
        "slug": note.slug,
    }
    count = qdrant_service.upsert_note_chunks(payload_note, chunks, vectors)
    logger.info("笔记已索引 note=%s chunks=%s", note_id, count)


@celery_app.task(name="app.tasks.index.delete_note_index")
def delete_note_index(note_id: str) -> None:
    """删除笔记的向量（级联删除时调用）"""
    try:
        qdrant_service.delete_note_index(note_id)
    except Exception:  # noqa: BLE001
        logger.exception("删除笔记向量失败 note=%s", note_id)


def queue_delete_note_index(note_id: str) -> None:
    """供 API 进程调用：入队删除（避免 API 直接依赖 Qdrant）"""
    try:
        delete_note_index.delay(note_id)
    except Exception:  # noqa: BLE001
        logger.warning("下发删除索引任务失败: %s", note_id)


def queue_index_note(note_id: str) -> None:
    """供 API 进程调用：笔记内容变更后触发重建索引"""
    try:
        index_note.delay(note_id)
    except Exception:  # noqa: BLE001
        logger.warning("下发索引任务失败: %s", note_id)
