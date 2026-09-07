"""笔记路由：项目内笔记树 / 笔记 CRUD / 统计 / 链接 / ACL

注意：文件导入的笔记由文件流水线生成；编辑器内容块操作见 blocks.py。
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.core.deps import get_current_user
from app.core.permissions import PermissionChecker, get_permission_checker
from app.database import get_session
from app.models.note import (
    Note,
    NoteAcl,
    NoteBlock,
    NoteBlockRead,
    NoteCreate,
    NoteDetail,
    NoteLink,
    NoteRead,
    NoteStats,
    NoteTreeNode,
    NoteUpdate,
    NoteViewLog,
)
from app.models.org import OrgRole
from app.models.project import Project, ProjectMember, PROJECT_ADMIN_ROLES
from app.models.user import User
from app.services.note_service import (
    build_note_graph,
    build_note_tree,
    compute_note_stats,
    get_note_blocks,
    get_project_notes,
    sync_note_link_blocks_order,
)
from app.services.note_service import purge_note_tree
from app.tasks.index import queue_delete_note_index, queue_index_note

collection = APIRouter(prefix="/projects/{project_id}/notes", tags=["笔记"])
items = APIRouter(prefix="/notes", tags=["笔记"])


def _gen_note_dict(note: Note) -> NoteRead:
    return NoteRead.model_validate(note)


# ========== 项目内笔记集合 ==========

@collection.get("/", response_model=list[NoteTreeNode], summary="项目笔记树")
async def list_notes(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    notes = await get_project_notes(perm.session, project_id)
    note_ids = [n.id for n in notes]
    links = []
    if note_ids:
        result = await perm.session.execute(
            select(NoteLink).where(NoteLink.source_note_id.in_(note_ids))
        )
        links = list(result.scalars().all())
    return build_note_tree(notes, links)


@collection.get("/graph", summary="项目关系图")
async def note_graph(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    return await build_note_graph(perm.session, project_id)


@collection.get("/search", response_model=list[NoteRead], summary="搜索项目内笔记")
async def search_notes(
    project_id: str,
    q: str = Query(..., min_length=1),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    result = await perm.session.execute(
        select(Note).where(Note.project_id == project_id, Note.title.contains(q))
    )
    return [_gen_note_dict(p) for p in result.scalars().all()]


@collection.post("/", response_model=NoteRead, summary="创建笔记")
async def create_note(
    project_id: str,
    body: NoteCreate,
    current_user: User = Depends(get_current_user),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.MAINTAINER.value)
    note = Note(
        project_id=project.id,
        title=body.title,
        icon=body.icon,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
        owner_id=current_user.id,
        creator_id=current_user.id,
        last_editor_id=current_user.id,
    )
    perm.session.add(note)
    await perm.session.commit()
    await perm.session.refresh(note)
    # 占位段落（与旧编辑器行为一致）
    perm.session.add(NoteBlock(
        note_id=note.id,
        type="paragraph",
        content={"text": ""},
        sort_order=0,
    ))
    await perm.session.commit()
    return _gen_note_dict(note)


@collection.get("/by-slug/{slug}", response_model=NoteDetail, summary="按 slug 获取笔记")
async def get_note_by_slug(
    project_id: str,
    slug: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    result = await perm.session.execute(
        select(Note).where(Note.project_id == project_id, Note.slug == slug)
    )
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="笔记不存在或无权访问")
    await perm.require_note(note.id, "read")
    return await _detail(perm.session, note)


# ========== 笔记条目 ==========

async def _detail(session: AsyncSession, note: Note) -> NoteDetail:
    blocks = await get_note_blocks(session, note.id)
    return NoteDetail(
        **NoteRead.model_validate(note).model_dump(),
        blocks=[NoteBlockRead.model_validate(b) for b in blocks],
    )


@items.get("/{note_id}", response_model=NoteDetail, summary="笔记详情")
async def get_note_detail(
    note_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, _ = await perm.require_note(note_id, "read")
    return await _detail(perm.session, note)


@items.patch("/{note_id}", response_model=NoteRead, summary="更新笔记元信息")
async def update_note(
    note_id: str,
    body: NoteUpdate,
    current_user: User = Depends(get_current_user),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, _ = await perm.require_note(note_id, "write")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(note, key, value)
    note.updated_at = datetime.utcnow()
    note.last_editor_id = current_user.id
    perm.session.add(note)
    await perm.session.commit()
    await perm.session.refresh(note)

    if "sort_order" in body.model_dump(exclude_unset=True) or "parent_id" in body.model_dump(exclude_unset=True):
        await sync_note_link_blocks_order(perm.session, note.id)
    # 公开属性变化影响向量过滤条件 → 触发重建
    if "is_public" in body.model_dump(exclude_unset=True):
        queue_index_note(note.id)
    return _gen_note_dict(note)


@items.delete("/{note_id}", summary="删除笔记（含子页面子树）")
async def delete_note(
    note_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, _ = await perm.require_note(note_id, "delete")
    await purge_note_tree(perm.session, note.id)
    queue_delete_note_index(note_id)
    # 同步引用该笔记的 note_link 块
    await sync_note_link_blocks_order(perm.session, note_id)
    return {"message": "笔记已删除"}


@items.post("/{note_id}/duplicate", response_model=NoteRead, summary="复制笔记")
async def duplicate_note(
    note_id: str,
    current_user: User = Depends(get_current_user),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, _ = await perm.require_note(note_id, "write")
    blocks = await get_note_blocks(perm.session, note.id)

    new_note = Note(
        project_id=note.project_id,
        title=f"{note.title} (副本)",
        icon=note.icon,
        parent_id=note.parent_id,
        sort_order=note.sort_order + 1,
        owner_id=current_user.id,
        creator_id=current_user.id,
        last_editor_id=current_user.id,
    )
    perm.session.add(new_note)
    await perm.session.flush()

    for block in blocks:
        import copy

        perm.session.add(NoteBlock(
            note_id=new_note.id,
            type=block.type,
            content=copy.deepcopy(block.content),
            sort_order=block.sort_order,
        ))
    await perm.session.commit()
    await perm.session.refresh(new_note)
    queue_index_note(new_note.id)
    return _gen_note_dict(new_note)


@items.get("/{note_id}/stats", response_model=NoteStats, summary="笔记统计（同时记录浏览）")
async def get_note_stats(
    note_id: str,
    current_user: User = Depends(get_current_user),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, _ = await perm.require_note(note_id, "read")
    note.view_count = (note.view_count or 0) + 1
    perm.session.add(note)
    # 浏览记录（推荐引擎输入）
    perm.session.add(NoteViewLog(user_id=current_user.id, note_id=note.id))
    await perm.session.commit()
    await perm.session.refresh(note)

    blocks = await get_note_blocks(perm.session, note.id)
    stats = await compute_note_stats(perm.session, note, blocks)
    return stats


@items.post("/{note_id}/sync-link-blocks", summary="同步引用本笔记的链接块")
async def sync_link_blocks(
    note_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_note(note_id, "write")
    await sync_note_link_blocks_order(perm.session, note_id)
    return {"message": "同步完成", "note_id": note_id}


# ---------- ABAC ACL ----------

class BatchDeleteRequest(SQLModel):
    note_ids: list[str]


@items.post("/batch-delete", summary="批量删除笔记（每篇含子树）")
async def batch_delete_notes(
    body: BatchDeleteRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    deleted: list[str] = []
    failed: list[str] = []
    for nid in dict.fromkeys(body.note_ids or []):
        try:
            note, _ = await perm.require_note(nid, "delete")
        except HTTPException:
            failed.append(nid)
            continue
        await purge_note_tree(perm.session, note.id)
        queue_delete_note_index(nid)
        deleted.append(nid)
    return {"deleted": deleted, "failed": failed,
            "deleted_count": len(deleted), "failed_count": len(failed)}


@collection.delete("/", summary="清空项目内全部笔记（危险）")
async def clear_project_notes(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.ADMIN.value)
    rows = await perm.session.execute(
        select(Note).where(Note.project_id == project_id)
    )
    all_ids = [n.id for n in rows.scalars().all()]
    total = len(all_ids)
    root_rows = await perm.session.execute(
        select(Note).where(Note.project_id == project_id, Note.parent_id.is_(None))
    )
    roots = [n.id for n in root_rows.scalars().all()]
    for rid in roots:
        await purge_note_tree(perm.session, rid)
        queue_delete_note_index(rid)
    return {"deleted_roots": len(roots), "notes_removed": total}


class AclGrantRequest(SQLModel):
    username: str
    permission: str = "read"  # read / write / delete


@items.post("/{note_id}/acl", summary="授予用户笔记级权限")
async def grant_acl(
    note_id: str,
    body: AclGrantRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, role = await perm.require_note(note_id, "delete")
    # 只有 owner 或项目 Owner/Admin 可管理 ACL
    if note.owner_id != perm.user.id and (not role or role not in PROJECT_ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    if body.permission not in ("read", "write", "delete"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="permission 需为 read/write/delete")

    target_result = await perm.session.execute(select(User).where(User.username == body.username))
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    existing = await perm.session.execute(
        select(NoteAcl).where(NoteAcl.note_id == note_id, NoteAcl.user_id == target.id)
    )
    acl = existing.scalar_one_or_none()
    if acl:
        acl.permission = body.permission
        perm.session.add(acl)
    else:
        acl = NoteAcl(note_id=note_id, user_id=target.id, permission=body.permission)
        perm.session.add(acl)
    await perm.session.commit()
    return {"message": "授权成功", "user_id": target.id, "permission": acl.permission}


@items.delete("/{note_id}/acl/{user_id}", summary="撤销笔记级权限")
async def revoke_acl(
    note_id: str,
    user_id: int,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    note, role = await perm.require_note(note_id, "delete")
    if note.owner_id != perm.user.id and (not role or role not in PROJECT_ADMIN_ROLES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    existing = await perm.session.execute(
        select(NoteAcl).where(NoteAcl.note_id == note_id, NoteAcl.user_id == user_id)
    )
    acl = existing.scalar_one_or_none()
    if not acl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="授权记录不存在")
    await perm.session.delete(acl)
    await perm.session.commit()
    return {"message": "已撤销授权"}
