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


async def sync_page_link_blocks_order(session: AsyncSession, moved_page_id: int) -> None:
    """
    当页面排序/位置改变（或删除）后，同步更新所有引用该页面的 page_link 块。
    
    策略：将指向 moved_page_id 的 page_link 块移动到其所在页面的最大 sort_order 之后，
    确保引用块始终位于页面内容末尾，不干扰主要内容的排序。
    同时更新引用块的 content.title 为被引用页面的最新标题。
    """
    from app.models.page import Page

    # 获取被引用的页面信息（可能已被删除，仅尝试获取）
    target_page = await session.get(Page, moved_page_id)
    target_title = target_page.title if target_page else None

    # 查询所有 type='page_link' 且 content.page_id == moved_page_id 的 Block
    result = await session.execute(
        select(Block).where(Block.type == BlockType.PAGE_LINK.value)
    )
    all_page_link_blocks = result.scalars().all()

    # 筛选 content.page_id == moved_page_id 的块
    matched_blocks = [
        b for b in all_page_link_blocks
        if isinstance(b.content, dict) and b.content.get('page_id') == moved_page_id
    ]

    if not matched_blocks:
        return

    # 按所在页面分组，计算每个页面的最大 sort_order
    page_max_orders: dict[int, int] = {}
    page_blocks_map: dict[int, list[Block]] = {}
    for b in matched_blocks:
        page_blocks_map.setdefault(b.page_id, []).append(b)

    # 获取各页面当前最大 sort_order
    for pid in page_blocks_map:
        result = await session.execute(
            select(Block).where(Block.page_id == pid).order_by(Block.sort_order.desc()).limit(1)
        )
        last_block = result.scalar_one_or_none()
        page_max_orders[pid] = (last_block.sort_order if last_block else -1) + 1

    # 更新每个引用块
    for b in matched_blocks:
        updated = False
        if isinstance(b.content, dict):
            # 更新标题（如果被引用页面存在且标题不同）
            if target_title and b.content.get('title') != target_title:
                b.content = {**b.content, 'title': target_title}
                updated = True
            # 将引用块移到页面末尾
            pid = b.page_id
            new_order = page_max_orders.get(pid, b.sort_order + 1)
            if b.sort_order < new_order:
                b.sort_order = new_order
                page_max_orders[pid] = new_order + 1  # 递增，防止多个引用块冲突
                updated = True
        if updated:
            session.add(b)

    if matched_blocks:
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
