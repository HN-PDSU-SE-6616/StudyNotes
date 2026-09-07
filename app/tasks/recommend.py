"""推荐任务：加权混合推荐（画像/行为/热度/时效）

score = w_profile×sim(职业+技术栈画像向量) + w_read×sim(近期阅读兴趣向量)
        + w_pop×热度(浏览量 min-max 归一) + w_fresh×时效(7 日线性衰减)

权重取 settings.rec_w_*（默认 0.40/0.25/0.25/0.10）；缺失因子时其权重并入
其余可用因子后再归一。新用户 onboarding 提交画像后即时 refresh_user_now 刷新；
每日 beat 刷新“活跃(有浏览) ∪ 有画像”用户。Embedding 不可用时整体静默跳过。
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.models.note import Note, NoteViewLog
from app.models.org import OrganizationMember
from app.models.profile import UserProfile
from app.models.project import Project
from app.services import careers, embedding, qdrant_service
from app.tasks.common import run_async
from app.worker import celery_app

logger = logging.getLogger(__name__)

RECENT_DAYS = 7
TOP_READ_NOTES = 10
CANDIDATE_COUNT = 40
RESULT_COUNT = 20
REDIS_TTL = 60 * 60 * 24  # 24h


# ---------------- Redis 缓存 ----------------

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


# ---------------- 权重 ----------------

def _effective_weights(has_profile: bool, has_read: bool) -> dict[str, float]:
    """按可用因子分配权重：缺失因子权重并入另一相似度因子（0.4↔0.25），总权恒为 1。

    - 画像 + 行为：0.40 / 0.25 / 0.25 / 0.10
    - 仅画像：行为权重并入画像 → 0.65 / 0 / 0.25 / 0.10
    - 仅行为：画像权重并入行为 → 0 / 0.65 / 0.25 / 0.10
    - 全无（纯冷启动且未设画像）：0 / 0 / 0.8 / 0.2（热门+时效）
    """
    wp = settings.rec_w_profile if has_profile else 0.0
    wr = settings.rec_w_read if has_read else 0.0
    wv = settings.rec_w_pop
    wf = settings.rec_w_fresh
    if has_profile and not has_read:
        wp = settings.rec_w_profile + settings.rec_w_read
        wr = 0.0
    elif has_read and not has_profile:
        wr = settings.rec_w_read + settings.rec_w_profile
        wp = 0.0
    elif not has_profile and not has_read:
        # 纯冷启动且未设画像：以热度为主
        wp = wr = 0.0
        wv = 0.8
        wf = 0.2
    total = wp + wr + wv + wf
    if total <= 0:
        wp, wv, wf = 0.5, 0.4, 0.1
        total = 1.0
    return {"wp": wp / total, "wr": wr / total, "wv": wv / total, "wf": wf / total}


# ---------------- Celery 入口 ----------------

@celery_app.task(name="app.tasks.recommend.refresh_recommendations")
def refresh_recommendations() -> None:
    """每日刷新所有活跃（浏览 ∪ 画像）用户的推荐结果"""
    if not embedding.is_configured():
        logger.warning("Embedding 未配置，跳过推荐刷新")
        return
    try:
        run_async(_refresh_all)
    except Exception:  # noqa: BLE001
        logger.exception("推荐刷新失败")


@celery_app.task(name="app.tasks.recommend.refresh_user_now")
def refresh_user_now(user_id: int) -> None:
    """单用户即时刷新（onboarding 保存画像后调用；失败静默，不影响主链路）"""
    if not embedding.is_configured():
        logger.info("Embedding 未配置，跳过用户推荐刷新 user=%s", user_id)
        return
    try:
        run_async(lambda session: refresh_user(session, user_id))
    except Exception:  # noqa: BLE001
        logger.exception("用户推荐即时刷新失败 user=%s", user_id)


# ---------------- 主流程 ----------------

async def _refresh_all(session) -> None:
    try:
        qdrant_service.ensure_collections(vector_size=embedding.dimension())
    except RuntimeError as exc:
        logger.warning("Embedding 不可用，跳过推荐刷新: %s", exc)
        return
    cutoff = datetime.utcnow() - timedelta(days=RECENT_DAYS)

    # 活跃用户 = 近期有浏览 ∪ 已设画像
    user_ids: set[int] = set()
    view_rows = await session.execute(
        select(NoteViewLog.user_id).where(NoteViewLog.viewed_at >= cutoff).distinct()
    )
    user_ids.update(view_rows.scalars().all())
    profile_rows = await session.execute(select(UserProfile.user_id))
    user_ids.update(profile_rows.scalars().all())

    for user_id in sorted(user_ids):
        try:
            await refresh_user(session, user_id, cutoff=cutoff)
        except Exception:  # noqa: BLE001
            logger.exception("用户推荐刷新失败 user=%s", user_id)


async def refresh_user(session, user_id: int, cutoff: Optional[datetime] = None) -> None:
    """刷新单用户推荐并写缓存。任何一步失败由调用方兜底（不抛致命异常）。"""
    try:
        qdrant_service.ensure_collections(vector_size=embedding.dimension())
    except RuntimeError as exc:
        logger.warning("Embedding 不可用，跳过推荐 user=%s: %s", user_id, exc)
        return
    cutoff = cutoff or (datetime.utcnow() - timedelta(days=RECENT_DAYS))
    _ = embedding.dimension()

    # 1) 可读项目
    org_ids = list((
        await session.execute(
            select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id)
        )
    ).scalars().all())
    accessible: list[str] = []
    if org_ids:
        accessible = list((
            await session.execute(select(Project.id).where(Project.organization_id.in_(org_ids)))
        ).scalars().all())
    if not accessible:
        return

    # 2) 画像向量
    profile_vec = None
    profile = (await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )).scalar_one_or_none()
    if profile and (profile.job_role or profile.tech_tags):
        terms = careers.profile_search_text(
            profile.job_role or "", profile.job_role_custom, profile.tech_tags or [])
        vecs = embedding.embed_texts([terms])
        profile_vec = vecs[0]
        qdrant_service.upsert_user_profile(user_id, profile_vec)

    # 3) 行为兴趣向量（近 7 日阅读去重 Top10）
    read_ids: list[str] = []
    seen: set[str] = set()
    view_rows = await session.execute(
        select(NoteViewLog.note_id, NoteViewLog.viewed_at)
        .where(NoteViewLog.user_id == user_id, NoteViewLog.viewed_at >= cutoff)
        .order_by(NoteViewLog.viewed_at.desc())
    )
    for note_id, _ in view_rows.all():
        if note_id not in seen:
            seen.add(note_id)
            read_ids.append(note_id)
        if len(read_ids) >= TOP_READ_NOTES:
            break
    read_vec = None
    if read_ids:
        note_rows = await session.execute(
            select(Note).where(Note.id.in_(read_ids))
        )
        texts = [n.title or "" for n in note_rows.scalars().all() if n and n.title]
        if texts:
            vecs = embedding.embed_texts([t[:2000] for t in texts[:TOP_READ_NOTES]])
            dim = len(vecs[0])
            read_vec = [sum(v[i] for v in vecs) / len(vecs) for i in range(dim)]

    w = _effective_weights(profile_vec is not None, read_vec is not None)

    # 4) 候选（画像/行为各自检索 topK 再并集）
    candidates: dict[str, dict] = {}
    if profile_vec is not None:
        for item in qdrant_service.search_notes(profile_vec, accessible,
                                                limit=CANDIDATE_COUNT,
                                                exclude_owner_id=user_id,
                                                exclude_note_ids=read_ids):
            pid = (item.get("payload") or {}).get("note_id")
            if pid:
                hit = candidates.setdefault(pid, {})
                hit["sim_profile"] = max(hit.get("sim_profile", 0.0), float(item.get("score", 0)))
                hit.setdefault("payload", item.get("payload") or {})
    if read_vec is not None:
        for item in qdrant_service.search_notes(read_vec, accessible,
                                                limit=CANDIDATE_COUNT,
                                                exclude_owner_id=user_id,
                                                exclude_note_ids=read_ids):
            pid = (item.get("payload") or {}).get("note_id")
            if pid:
                hit = candidates.setdefault(pid, {})
                hit["sim_read"] = max(hit.get("sim_read", 0.0), float(item.get("score", 0)))
                hit.setdefault("payload", item.get("payload") or {})
    if not candidates:
        logger.info("无候选 note 缓存 user=%s", user_id)
        cache_recommendations(user_id, [])
        return

    # 5) 热度/时效（DB 批量取）
    rows = await session.execute(
        select(Note).where(Note.id.in_(list(candidates.keys())))
    )
    notes = {n.id: n for n in rows.scalars().all()}
    now = datetime.utcnow()
    views = [n.view_count or 0 for n in notes.values()]
    vmin, vmax = (min(views), max(views)) if views else (0, 0)

    scored: list[dict] = []
    for nid, hit in candidates.items():
        note = notes.get(nid)
        if not note:
            continue
        sim_p = float(hit.get("sim_profile") or 0.0)
        sim_r = float(hit.get("sim_read") or 0.0)
        pop = ((note.view_count or 0) - vmin) / (vmax - vmin) if vmax > vmin else 0.0
        age_days = max(0.0, (now - (note.updated_at or now)).total_seconds() / 86400)
        fresh = max(0.0, 1.0 - age_days / RECENT_DAYS)
        score = w["wp"] * sim_p + w["wr"] * sim_r + w["wv"] * pop + w["wf"] * fresh
        payload = hit.get("payload") or {}
        # 归因标签（前端可显示推荐理由）
        parts = []
        if w["wp"] and sim_p >= max(sim_r, 1e-9):
            parts.append("profile")
        if w["wr"] and sim_r > sim_p + 1e-9:
            parts.append("behavior")
        if w["wv"] and pop >= 0.7:
            parts.append("popular")
        scored.append({
            "note_id": nid,
            "title": payload.get("note_title") or note.title or "",
            "slug": payload.get("note_slug") or (note.slug or ""),
            "project_id": payload.get("project_id") or note.project_id,
            "heading_path": payload.get("heading_path") or "",
            "score": round(score, 5),
            "reason": parts[:1],
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    cache_recommendations(user_id, scored[:RESULT_COUNT])
    logger.info("用户推荐已刷新 user=%s count=%s", user_id, min(len(scored), RESULT_COUNT))
