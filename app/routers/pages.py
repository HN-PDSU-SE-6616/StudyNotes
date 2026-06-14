"""页面 CRUD 路由"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_user
from app.database import get_session
from app.models.page import (
    Block,
    BlockRead,
    Page,
    PageCreate,
    PageDetail,
    PageGraph,
    PageLink,
    PageRead,
    PageTreeNode,
    PageUpdate,
)
from app.models.user import User
from app.services.page_service import (
    build_page_graph,
    build_page_tree,
    get_user_workspace,
    sync_page_links,
)

router = APIRouter(prefix="/pages", tags=["页面管理"])


@router.get("/tree", response_model=list[PageTreeNode], summary="获取页面树")
async def get_page_tree(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    pages = (await session.execute(select(Page).where(Page.workspace_id == workspace.id))).scalars().all()
    page_ids = [p.id for p in pages]
    links = (await session.execute(select(PageLink).where(PageLink.source_page_id.in_(page_ids)))).scalars().all() if page_ids else []
    return build_page_tree(pages, links)


@router.get("/graph", response_model=PageGraph, summary="获取页面关系图")
async def get_page_graph(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    return await build_page_graph(session, workspace.id)


@router.post("/", response_model=PageRead, summary="创建页面")
async def create_page(
    body: PageCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    page = Page(workspace_id=workspace.id, **body.model_dump())
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return PageRead.model_validate(page)


@router.get("/search", response_model=list[PageRead], summary="搜索页面")
async def search_pages(
    q: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    result = await session.execute(
        select(Page).where(Page.workspace_id == workspace.id, Page.title.contains(q))
    )
    return [PageRead.model_validate(p) for p in result.scalars().all()]


@router.get("/{page_id}", response_model=PageDetail, summary="获取页面详情")
async def get_page_detail(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.sort_order)
        )
    ).scalars().all()

    return PageDetail(
        **PageRead.model_validate(page).model_dump(),
        blocks=[BlockRead.model_validate(b) for b in blocks],
    )


@router.patch("/{page_id}", response_model=PageRead, summary="更新页面")
async def update_page(
    page_id: int,
    body: PageUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(page, key, value)
    page.updated_at = datetime.utcnow()
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return PageRead.model_validate(page)


@router.delete("/{page_id}", summary="删除页面")
async def delete_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    blocks = (await session.execute(select(Block).where(Block.page_id == page_id))).scalars().all()
    for block in blocks:
        await session.delete(block)

    from app.models.page import PageLink

    links = (
        await session.execute(
            select(PageLink).where(
                (PageLink.source_page_id == page_id) | (PageLink.target_page_id == page_id)
            )
        )
    ).scalars().all()
    for link in links:
        await session.delete(link)

    await session.delete(page)
    await session.commit()
    return {"message": "页面已删除"}
