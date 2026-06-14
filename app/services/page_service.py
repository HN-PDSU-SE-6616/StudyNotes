"""页面服务逻辑"""
from datetime import datetime
from typing import Sequence, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.page import (
    Block,
    BlockType,
    Page,
    PageGraph,
    PageGraphEdge,
    PageGraphNode,
    PageLink,
    PageTreeNode,
    Workspace,
)


async def get_user_workspace(session: AsyncSession, user_id: int) -> Workspace:
    """获取或创建用户默认工作区"""
    result = await session.execute(select(Workspace).where(Workspace.owner_id == user_id))
    workspace = result.scalar_one_or_none()
    if workspace:
        return workspace
    workspace = Workspace(owner_id=user_id)
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


def build_page_tree(
    pages: Sequence[Page],
    links: Sequence[PageLink],
    parent_id: Optional[int] = None,
) -> list[PageTreeNode]:
    """构建侧边栏树：parent_id 层级 + 链接子页面"""
    page_map = {p.id: p for p in pages}
    link_map: dict[int, list[int]] = {}
    for link in links:
        link_map.setdefault(link.source_page_id, []).append(link.target_page_id)

    def to_node(page: Page) -> PageTreeNode:
        children = [
            to_node(page_map[cid])
            for cid in (c.id for c in pages if c.parent_id == page.id)
            if cid in page_map
        ]
        linked = [
            to_node(page_map[tid])
            for tid in link_map.get(page.id, [])
            if tid in page_map and tid != page.id
        ]
        return PageTreeNode(
            **page.model_dump(),
            children=children,
            linked_children=linked,
        )

    roots = [p for p in pages if p.parent_id == parent_id]
    return [to_node(p) for p in sorted(roots, key=lambda x: (-x.is_pinned, x.sort_order, x.id))]


async def sync_page_links(session: AsyncSession, page_id: int, blocks: Sequence[Block]) -> None:
    """从 Block 内容同步页面链接关系"""
    existing = await session.execute(select(PageLink).where(PageLink.source_page_id == page_id))
    for link in existing.scalars().all():
        await session.delete(link)

    target_ids: set[int] = set()
    for block in blocks:
        if block.type == BlockType.PAGE_LINK.value:
            tid = block.content.get("page_id")
            if isinstance(tid, int) and tid != page_id:
                target_ids.add(tid)

    for tid in target_ids:
        session.add(PageLink(source_page_id=page_id, target_page_id=tid))
    await session.commit()


async def build_page_graph(session: AsyncSession, workspace_id: int) -> PageGraph:
    """构建工作区内页面关系图"""
    pages_result = await session.execute(select(Page).where(Page.workspace_id == workspace_id))
    pages = pages_result.scalars().all()
    page_ids = [p.id for p in pages]

    links_result = await session.execute(
        select(PageLink).where(PageLink.source_page_id.in_(page_ids))
    )
    links = links_result.scalars().all()

    nodes = [PageGraphNode(id=p.id, title=p.title, icon=p.icon) for p in pages]
    edges = [PageGraphEdge(source=l.source_page_id, target=l.target_page_id) for l in links]

    for p in pages:
        if p.parent_id and p.parent_id in page_ids:
            edge = PageGraphEdge(source=p.parent_id, target=p.id)
            if edge not in edges:
                edges.append(edge)

    return PageGraph(nodes=nodes, edges=edges)
