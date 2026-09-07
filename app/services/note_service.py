"""笔记服务逻辑：树构建、链接同步、关系图、字数统计、浏览记录"""
from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.note import (
    Note,
    NoteBlock,
    NoteLink,
    NoteStats,
    NoteTreeNode,
)
from app.models.user import User


def build_note_tree(
    notes: Sequence[Note],
    links: Sequence[NoteLink],
    parent_id: Optional[str] = None,
) -> list[NoteTreeNode]:
    """构建项目内笔记树：parent_id 层级 + 链接子笔记"""
    page_map = {p.id: p for p in notes}
    link_map: dict[str, list[str]] = {}
    for link in links:
        link_map.setdefault(link.source_note_id, []).append(link.target_note_id)

    def to_node(note: Note) -> NoteTreeNode:
        children = [
            to_node(page_map[cid])
            for cid in (c.id for c in notes if c.parent_id == note.id)
            if cid in page_map
        ]
        linked = [
            to_node(page_map[tid])
            for tid in link_map.get(note.id, [])
            if tid in page_map and tid != note.id
        ]
        return NoteTreeNode(
            **note.model_dump(),
            children=children,
            linked_children=linked,
        )

    roots = [p for p in notes if p.parent_id == parent_id]
    return [
        to_node(p)
        for p in sorted(roots, key=lambda x: (-(x.is_pinned or False), x.sort_order, x.id or ""))
    ]


async def get_project_notes(session: AsyncSession, project_id: str) -> list[Note]:
    result = await session.execute(select(Note).where(Note.project_id == project_id))
    return list(result.scalars().all())


async def get_note_blocks(session: AsyncSession, note_id: str) -> list[NoteBlock]:
    result = await session.execute(
        select(NoteBlock).where(NoteBlock.note_id == note_id).order_by(NoteBlock.sort_order)
    )
    return list(result.scalars().all())


async def sync_note_links(session: AsyncSession, note_id: str, blocks: Sequence[NoteBlock]) -> None:
    """从 note_link 块内容同步笔记间链接关系"""
    existing = await session.execute(select(NoteLink).where(NoteLink.source_note_id == note_id))
    for link in existing.scalars().all():
        await session.delete(link)

    target_ids: set[str] = set()
    for block in blocks:
        # 兼容新旧链接块类型名（旧前端使用 page_link）
        if block.type in ("note_link", "page_link"):
            tid = block.content.get("note_id")
            if isinstance(tid, str) and tid != note_id:
                target_ids.add(tid)

    for tid in target_ids:
        session.add(NoteLink(source_note_id=note_id, target_note_id=tid))
    await session.commit()


async def sync_note_link_blocks_order(session: AsyncSession, moved_note_id: str) -> None:
    """笔记移动/删除后，将引用块排到所在笔记末尾并更新标题"""
    target_note = await session.get(Note, moved_note_id)
    target_title = target_note.title if target_note else None

    result = await session.execute(
        select(NoteBlock).where(NoteBlock.type.in_(("note_link", "page_link")))
    )
    all_blocks = result.scalars().all()
    matched = [
        b for b in all_blocks
        if isinstance(b.content, dict) and b.content.get("note_id") == moved_note_id
    ]
    if not matched:
        return

    page_max_orders: dict[str, int] = {}
    grouped: dict[str, list[NoteBlock]] = {}
    for b in matched:
        grouped.setdefault(b.note_id, []).append(b)

    for nid in grouped:
        result = await session.execute(
            select(NoteBlock).where(NoteBlock.note_id == nid)
            .order_by(NoteBlock.sort_order.desc()).limit(1)
        )
        last = result.scalar_one_or_none()
        page_max_orders[nid] = (last.sort_order if last else -1) + 1

    for b in matched:
        updated = False
        if isinstance(b.content, dict):
            if target_title and b.content.get("title") != target_title:
                b.content = {**b.content, "title": target_title}
                updated = True
            nid = b.note_id
            new_order = page_max_orders.get(nid, b.sort_order + 1)
            if b.sort_order < new_order:
                b.sort_order = new_order
                page_max_orders[nid] = new_order + 1
                updated = True
        if updated:
            session.add(b)

    if matched:
        await session.commit()


async def build_note_graph(session: AsyncSession, project_id: str) -> dict:
    """构建项目内关系图（nodes/edges 结构同旧版 PageGraph）"""
    notes = await get_project_notes(session, project_id)
    note_ids = [n.id for n in notes]

    nodes = [{"id": n.id, "title": n.title, "icon": n.icon} for n in notes]
    edges: list[dict] = []
    if note_ids:
        result = await session.execute(select(NoteLink).where(NoteLink.source_note_id.in_(note_ids)))
        for link in result.scalars().all():
            edges.append({"source": link.source_note_id, "target": link.target_note_id})

    id_set = set(note_ids)
    for n in notes:
        if n.parent_id and n.parent_id in id_set:
            edge = {"source": n.parent_id, "target": n.id}
            if edge not in edges:
                edges.append(edge)

    return {"nodes": nodes, "edges": edges}


async def compute_note_stats(
    session: AsyncSession, note: Note, blocks: Sequence[NoteBlock]
) -> NoteStats:
    """统计字数/块数，并查创建者/最后编辑者姓名"""
    total_words = 0
    for b in blocks:
        c = b.content or {}
        if isinstance(c, dict):
            for tf in ("text", "code"):
                val = c.get(tf, "")
                if isinstance(val, str):
                    total_words += len(val.replace(" ", ""))
            items = c.get("items", [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        it = item.get("text", "")
                        if isinstance(it, str):
                            total_words += len(it.replace(" ", ""))
                    elif isinstance(item, str):
                        total_words += len(item.replace(" ", ""))

    creator_name = last_editor_name = None
    if note.creator_id:
        creator = await session.get(User, note.creator_id)
        if creator:
            creator_name = creator.display_name or creator.username
    if note.last_editor_id:
        editor = await session.get(User, note.last_editor_id)
        if editor:
            last_editor_name = editor.display_name or editor.username

    return NoteStats(
        total_words=total_words,
        block_count=len(blocks),
        view_count=note.view_count or 0,
        created_at=note.created_at,
        creator_name=creator_name,
        updated_at=note.updated_at,
        last_editor_name=last_editor_name,
    )
