"""Block CRUD 路由"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_user
from app.database import get_session
from app.models.page import Block, BlockCreate, BlockRead, BlockUpdate, Page
from app.models.user import User
from app.services.page_service import get_user_workspace, sync_page_links

router = APIRouter(prefix="/blocks", tags=["内容块"])


async def _verify_page_access(session: AsyncSession, page_id: int, user_id: int) -> Page:
    workspace = await get_user_workspace(session, user_id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")
    return page


@router.post("/{page_id}", response_model=BlockRead, summary="创建 Block")
async def create_block(
    page_id: int,
    body: BlockCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _verify_page_access(session, page_id, current_user.id)
    block = Block(page_id=page_id, **body.model_dump())
    session.add(block)
    await session.commit()
    await session.refresh(block)

    blocks = (await session.execute(select(Block).where(Block.page_id == page_id))).scalars().all()
    await sync_page_links(session, page_id, blocks)
    return BlockRead.model_validate(block)


@router.patch("/{block_id}", response_model=BlockRead, summary="更新 Block")
async def update_block(
    block_id: int,
    body: BlockUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    block = await session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block 不存在")
    await _verify_page_access(session, block.page_id, current_user.id)

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(block, key, value)
    block.updated_at = datetime.utcnow()
    session.add(block)
    await session.commit()
    await session.refresh(block)

    blocks = (await session.execute(select(Block).where(Block.page_id == block.page_id))).scalars().all()
    await sync_page_links(session, block.page_id, blocks)
    return BlockRead.model_validate(block)


@router.delete("/{block_id}", summary="删除 Block")
async def delete_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    block = await session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block 不存在")
    page_id = block.page_id
    await _verify_page_access(session, page_id, current_user.id)

    await session.delete(block)
    await session.commit()

    blocks = (await session.execute(select(Block).where(Block.page_id == page_id))).scalars().all()
    await sync_page_links(session, page_id, blocks)
    return {"message": "Block 已删除"}


@router.put("/{page_id}/reorder", response_model=list[BlockRead], summary="批量重排 Block")
async def reorder_blocks(
    page_id: int,
    block_ids: list[int],
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await _verify_page_access(session, page_id, current_user.id)
    for order, bid in enumerate(block_ids):
        block = await session.get(Block, bid)
        if block and block.page_id == page_id:
            block.sort_order = order
            block.updated_at = datetime.utcnow()
            session.add(block)
    await session.commit()

    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.sort_order)
        )
    ).scalars().all()
    return [BlockRead.model_validate(b) for b in blocks]
