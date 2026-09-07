"""内容块路由：NoteBlock CRUD / 重排 / 导入（编辑器数据面）"""
import copy
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.core.permissions import PermissionChecker, get_permission_checker
from app.models.note import (
    Note,
    NoteBlock,
    NoteBlockCreate,
    NoteBlockRead,
    NoteBlockUpdate,
    NoteLink,
)
from app.services import parser as parser_service
from app.services.note_service import get_note_blocks, sync_note_links
from app.tasks.index import queue_index_note

router = APIRouter(tags=["内容块"])


async def _verify_write_note(note_id: str, perm: PermissionChecker) -> Note:
    """要求对笔记可写并返回笔记"""
    note, _ = await perm.require_note(note_id, "write")
    return note


async def _after_change(session, note_id: str) -> None:
    """块变更后：同步链接 + 触发向量重建（幂等）"""
    blocks = await get_note_blocks(session, note_id)
    await sync_note_links(session, note_id, blocks)
    queue_index_note(note_id)


@router.post("/notes/{note_id}/blocks", response_model=NoteBlockRead, summary="创建块")
async def create_block(
    note_id: str,
    body: NoteBlockCreate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await _verify_write_note(note_id, perm)
    block = NoteBlock(note_id=note_id, **body.model_dump())
    perm.session.add(block)
    await perm.session.commit()
    await perm.session.refresh(block)
    await _after_change(perm.session, note_id)
    return NoteBlockRead.model_validate(block)


@router.patch("/blocks/{block_id}", response_model=NoteBlockRead, summary="更新块")
async def update_block(
    block_id: str,
    body: NoteBlockUpdate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    block = await perm.session.get(NoteBlock, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="块不存在")
    await _verify_write_note(block.note_id, perm)

    data = body.model_dump(exclude_unset=True)
    # JSON 变更需触发 SQLAlchemy JSONB dirty 检测：替换为新 dict
    if "content" in data and isinstance(data["content"], dict):
        old = dict(block.content or {})
        old.update(data["content"])
        data["content"] = old
    for key, value in data.items():
        setattr(block, key, value)
    block.updated_at = datetime.utcnow()
    perm.session.add(block)
    await perm.session.commit()
    await perm.session.refresh(block)
    await _after_change(perm.session, block.note_id)
    return NoteBlockRead.model_validate(block)


@router.delete("/blocks/{block_id}", summary="删除块")
async def delete_block(
    block_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    block = await perm.session.get(NoteBlock, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="块不存在")
    note_id = block.note_id
    await _verify_write_note(note_id, perm)
    await perm.session.delete(block)
    await perm.session.commit()
    await _after_change(perm.session, note_id)
    return {"message": "块已删除"}


@router.post("/blocks/{block_id}/duplicate", response_model=NoteBlockRead, summary="复制块")
async def duplicate_block(
    block_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    block = await perm.session.get(NoteBlock, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="块不存在")
    await _verify_write_note(block.note_id, perm)

    max_order = 0
    others = (await perm.session.execute(
        select(NoteBlock).where(NoteBlock.note_id == block.note_id)
    )).scalars().all()
    if others:
        max_order = max(b.sort_order for b in others)

    new_block = NoteBlock(
        note_id=block.note_id,
        type=block.type,
        content=copy.deepcopy(block.content),
        sort_order=max_order + 1,
    )
    perm.session.add(new_block)
    await perm.session.commit()
    await perm.session.refresh(new_block)
    await _after_change(perm.session, block.note_id)
    return NoteBlockRead.model_validate(new_block)


@router.put("/notes/{note_id}/blocks/reorder", response_model=list[NoteBlockRead], summary="批量重排块")
async def reorder_blocks(
    note_id: str,
    block_ids: list[str],
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await _verify_write_note(note_id, perm)
    for order, bid in enumerate(block_ids):
        block = await perm.session.get(NoteBlock, bid)
        if block and block.note_id == note_id:
            block.sort_order = order
            block.updated_at = datetime.utcnow()
            perm.session.add(block)
    await perm.session.commit()

    blocks = await get_note_blocks(perm.session, note_id)
    await sync_note_links(perm.session, note_id, blocks)
    queue_index_note(note_id)
    return [NoteBlockRead.model_validate(b) for b in blocks]


class ImportContentRequest(SQLModel):
    content: str
    format: str  # "html" or "md"


@router.post("/notes/{note_id}/blocks/import", response_model=list[NoteBlockRead], summary="导入 HTML/MD 到笔记")
async def import_to_note(
    note_id: str,
    body: ImportContentRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await _verify_write_note(note_id, perm)

    existing = await get_note_blocks(perm.session, note_id)
    max_order = max([b.sort_order for b in existing], default=-1)

    if body.format == "md":
        parsed = parser_service.parse_document("x.md", body.content.encode("utf-8"), "")
    elif body.format == "html":
        parsed = parser_service.parse_document("x.html", body.content.encode("utf-8"), "")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="format 需为 html 或 md")

    if not parsed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无可导入内容")

    new_blocks: list[NoteBlock] = []
    for order, item in enumerate(parsed, start=max_order + 1):
        block = NoteBlock(
            note_id=note_id,
            type=item.get("type", "paragraph"),
            content=item.get("content") or {},
            sort_order=order,
        )
        perm.session.add(block)
        new_blocks.append(block)
    await perm.session.commit()
    for block in new_blocks:
        await perm.session.refresh(block)

    all_blocks = existing + new_blocks
    await sync_note_links(perm.session, note_id, all_blocks)
    queue_index_note(note_id)
    return [NoteBlockRead.model_validate(b) for b in new_blocks]
