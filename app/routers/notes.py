# app/routers/notes.py
import json
import os
from typing import List, Optional, Sequence

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from starlette.responses import HTMLResponse

from app.database import get_session
from app.models import Note, NoteCreate, NoteRead, NoteUpdate
from datetime import datetime

from app.utils.markdown import fix_html_assets
from app.core.config import settings

NOTES_ROOT = os.path.abspath(settings.notes_data_path)

router = APIRouter(prefix="/notes", tags=["笔记管理"])


def build_tree(nodes: List[Note], parent_id=None):
    """递归构建树结构"""
    tree = []
    for node in nodes:
        if node.parent_id == parent_id:
            node_dict = node.dict()
            node_dict["children"] = build_tree(nodes, node.id)
            tree.append(node_dict)
    return tree


##################################################
#                 静态路由                        #
##################################################
@router.post("/", response_model=NoteRead, summary="创建笔记")
async def create_note(note: NoteCreate, session: AsyncSession = Depends(get_session)):
    db_note = Note.from_orm(note)
    session.add(db_note)
    await session.commit()
    await session.refresh(db_note)
    return db_note


@router.get("/", response_model=List[NoteRead], summary="获取笔记列表")
async def list_notes(
        skip: int = Query(0, description="跳过条数"),
        limit: int = Query(10, description="每页条数"),
        session: AsyncSession = Depends(get_session),
):
    query = select(Note)
    query = query.offset(skip).limit(limit).order_by(Note.created_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/tree", summary="获取笔记树列表")
async def get_notes_tree(session: AsyncSession = Depends(get_session)):
    """获取整站笔记目录树接口"""
    query = select(Note)
    results = await session.execute(query)
    all_notes = results.scalars().all()

    return build_tree(all_notes, parent_id=None)


##################################################
#                 动态路由                        #
##################################################
@router.get("/{note_id}", response_model=NoteRead, summary="获取单篇笔记")
async def get_note(note_id: int, session: AsyncSession = Depends(get_session)):
    note = await session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    return note


@router.get("/{note_id}/detail", response_class=HTMLResponse, summary="获取笔记详情页")
async def get_note_detail(note_id: int, session: AsyncSession = Depends(get_session)):
    note = await session.get(Note, note_id)
    if not note or note.content_type != "file":
        raise HTTPException(status_code=404, detail="笔记不存在或无HTML内容")

    # 实际的 HTML 文件路径
    base_path = os.path.join(NOTES_ROOT, note.content_path)

    # 目录下 HTML 文件
    html_files = [f for f in os.listdir(base_path) if f.endswith(".html")]
    if not html_files:
        raise HTTPException(status_code=404, detail="未找到HTML文件")

    file_path = os.path.join(base_path, html_files[0])

    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        content = await f.read()

    fixed_content = fix_html_assets(content, note.content_path)

    return HTMLResponse(content=fixed_content)


@router.patch("/{note_id}", response_model=NoteRead, summary="更新笔记")
async def update_note(
        note_id: int, note_update: NoteUpdate, session: AsyncSession = Depends(get_session)
):
    note = await session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")

    update_data = note_update.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    for key, value in update_data.items():
        setattr(note, key, value)

    session.add(note)
    await session.commit()
    await session.refresh(note)
    return note


@router.delete("/{note_id}", summary="删除笔记")
async def delete_note(note_id: int, session: AsyncSession = Depends(get_session)):
    note = await session.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="笔记不存在")
    await session.delete(note)
    await session.commit()
    return {"message": f"笔记 {note_id} 已删除"}

