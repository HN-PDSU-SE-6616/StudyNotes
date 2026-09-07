"""推荐路由：读取 Redis 个性化缓存；miss 时按浏览量兜底"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.permissions import PermissionChecker, get_permission_checker
from app.models.note import Note
from app.models.project import Project
from app.tasks.recommend import get_cached_recommendations

router = APIRouter(prefix="/recommendations", tags=["推荐"])


@router.get("/", summary="我的推荐列表")
async def my_recommendations(
    perm: PermissionChecker = Depends(get_permission_checker),
):
    """优先返回当日个性化缓存；缓存未就绪时返回可读项目中的热门笔记。"""
    cached = get_cached_recommendations(perm.user.id)
    if cached:
        return cached

    # 兜底：可读范围内的热门笔记（view_count 排序）
    accessible = await perm.get_accessible_project_ids(include_read=True)
    if not accessible:
        return []
    result = await perm.session.execute(
        select(Note)
        .where(Note.project_id.in_(accessible))
        .order_by(Note.view_count.desc(), Note.updated_at.desc())
        .limit(12)
    )
    items = []
    for n in result.scalars().all():
        items.append({
            "note_id": n.id,
            "title": n.title,
            "slug": n.slug,
            "project_id": n.project_id,
            "heading_path": "",
            "score": 0.0,
        })
    return items
