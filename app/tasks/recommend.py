"""推荐任务：每日刷新用户兴趣向量与个性化推荐（Celery beat）"""
import json
import logging

from sqlalchemy import select
from sqlmodel import select as sm_select  # noqa: F401

from app.models.note import Note, NoteBlock, NoteViewLog
from app.models.org import OrganizationMember
from app.models.project import Project
from app.services import chunker, embedding, qdrant_service
from app.tasks.common import run_async
from app.worker import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)

RECENT_DAYS = 7
TOP_READ_NOTES = 10
CANDIDATE_COUNT = 30
REDIS_TTL = 60 * 60 * 24  # 24h


def _redis_client():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def cache_recommendations(user_id: int, items: list[dict]) -> None:
    try:
        client = _redis_client()
        client.set(f"recommend:{user_id}", json.dumps(items, ensure_ascii=False), ex=REDIS_TTL)
    except Exception:  # noqa: BLE001
        logger.warning("写入推荐缓存失败 user=%s", user_id)


def get_cached_recommendations(user_id: int) -> list[dict]:
    try:
        client = _redis_client()
        raw = client.get(f"recommend:{user_id}")
        if raw:
            return json.loads(raw)
    except Exception:  # noqa: BLE001
        logger.warning("读取推荐缓存失败 user=%s", user_id)
    return []


@celery_app.task(name="app.tasks.recommend.refresh_recommendations")
def refresh_recommendations() -> None:
    """每日刷新所有活跃用户的推荐结果（兴趣向量 → Qdrant 检索 → Redis 缓存）"""
    if not embedding.is_configured():
        logger.warning("Embedding 未配置，跳过推荐刷新")
        return
    try:
        run_async(_refresh_all)
    except Exception:  # noqa: BLE001
        logger.exception("推荐刷新失败")


async def _refresh_all(session) -> None:
    from datetime import datetime, timedelta

    try:
        qdrant_service.ensure_collections(vector_size=embedding.dimension())
    except RuntimeError as exc:
        logger.warning("Embedding 不可用，跳过推荐刷新: %s", exc)
        return
    cutoff = datetime.utcnow() - timedelta(days=RECENT_DAYS)

    # 活跃用户
    user_result = await session.execute(
        select(NoteViewLog.user_id).where(NoteViewLog.viewed_at >= cutoff).distinct()
    )
    user_ids = list(user_result.scalars().all())
    if not user_ids:
        logger.info("无活跃用户，跳过推荐刷新")
        return

    for user_id in user_ids:
        try:
            await _refresh_one(session, user_id, cutoff)
        except Exception:  # noqa: BLE001
            logger.exception("用户推荐刷新失败 user=%s", user_id)


async def _refresh_one(session, user_id: int, cutoff) -> None:
    # 1) 用户最近阅读的去重笔记（按时间倒序取前 N）
    view_result = await session.execute(
        select(NoteViewLog.note_id, NoteViewLog.viewed_at)
        .where(NoteViewLog.user_id == user_id, NoteViewLog.viewed_at >= cutoff)
        .order_by(NoteViewLog.viewed_at.desc())
    )
    read_ids: list[str] = []
    seen: set[str] = set()
    for note_id, _ in view_result.all():
        if note_id not in seen:
            seen.add(note_id)
            read_ids.append(note_id)
        if len(read_ids) >= TOP_READ_NOTES:
            break
    if not read_ids:
        return

    # 2) 取这些笔记的文本并平均得到兴趣向量
    texts: list[str] = []
    for note_id in read_ids:
        note = await session.get(Note, note_id)
        if not note:
            continue
        texts.append(note.title or "")
        block_result = await session.execute(
            select(NoteBlock).where(NoteBlock.note_id == note_id)
            .order_by(NoteBlock.sort_order)
        )
        blocks = [
            {"type": b.type, "content": b.content or {}}
            for b in block_result.scalars().all()
        ]
        chunks = chunker.chunk_blocks(blocks, fallback_heading=note.title or "")
        for c in chunks[:3]:
            texts.append(c["text"][:2000])
    if not texts:
        return

    vecs = embedding.embed_texts(texts)
    dim = len(vecs[0])
    interest = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]
    qdrant_service.upsert_user_profile(user_id, interest)

    # 3) 用户可读项目集合
    org_ids = list(
        (
            await session.execute(
                select(OrganizationMember.organization_id)
                .where(OrganizationMember.user_id == user_id)
            )
        ).scalars().all()
    )
    accessible_project_ids: list[str] = []
    if org_ids:
        accessible_project_ids = list(
            (
                await session.execute(
                    select(Project.id).where(Project.organization_id.in_(org_ids))
                )
            ).scalars().all()
        )
    if not accessible_project_ids:
        return

    # 4) 检索候选并排除“自己创建”与“已读”
    scored = qdrant_service.search_notes(
        interest,
        accessible_project_ids,
        limit=CANDIDATE_COUNT,
        exclude_owner_id=user_id,
        exclude_note_ids=read_ids,
    )
    items = []
    for item in scored:
        p = item.get("payload") or {}
        items.append({
            "note_id": p.get("note_id"),
            "title": p.get("note_title") or "",
            "slug": p.get("note_slug") or "",
            "project_id": p.get("project_id"),
            "heading_path": p.get("heading_path") or "",
            "score": round(item.get("score", 0.0), 4),
        })
    cache_recommendations(user_id, items)
    logger.info("用户推荐已刷新 user=%s count=%s", user_id, len(items))
