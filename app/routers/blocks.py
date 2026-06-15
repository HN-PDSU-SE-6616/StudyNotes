"""Block CRUD 路由"""
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
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


class ImportRequest(BaseModel):
    content: str
    format: str  # "html" or "md"


@router.post("/{page_id}/import", response_model=list[BlockRead], summary="导入HTML/MD到页面")
async def import_to_page(
    page_id: int,
    body: ImportRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """将 HTML 或 Markdown 内容解析为 Block 列表并添加到页面"""
    await _verify_page_access(session, page_id, current_user.id)

    # 获取当前最大 sort_order
    existing = (await session.execute(
        select(Block).where(Block.page_id == page_id)
    )).scalars().all()
    max_order = max([b.sort_order for b in existing], default=-1)

    new_blocks: list[Block] = []

    if body.format == 'md':
        new_blocks = _parse_markdown(body.content, page_id, max_order + 1)
    elif body.format == 'html':
        new_blocks = _parse_html(body.content, page_id, max_order + 1)

    for block in new_blocks:
        session.add(block)
    await session.commit()
    for block in new_blocks:
        await session.refresh(block)

    await sync_page_links(session, page_id, existing + new_blocks)
    return [BlockRead.model_validate(b) for b in new_blocks]


@router.post("/{block_id}/duplicate", response_model=BlockRead, summary="复制 Block")
async def duplicate_block(
    block_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    block = await session.get(Block, block_id)
    if not block:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Block 不存在")
    await _verify_page_access(session, block.page_id, current_user.id)

    new_block = Block(
        page_id=block.page_id,
        type=block.type,
        content=block.content,
        sort_order=block.sort_order + 1,
    )
    session.add(new_block)
    await session.commit()
    await session.refresh(new_block)

    blocks = (await session.execute(select(Block).where(Block.page_id == block.page_id))).scalars().all()
    await sync_page_links(session, block.page_id, blocks)
    return BlockRead.model_validate(new_block)


def _parse_markdown(md_text: str, page_id: int, start_order: int) -> list[Block]:
    """简易 Markdown 解析为 Block 列表"""
    blocks: list[Block] = []
    order = start_order
    lines = md_text.strip().split('\n')
    code_buffer: list[str] = []
    code_lang = ''
    in_code = False

    def flush_blocks():
        nonlocal order
        if code_buffer:
            blocks.append(Block(
                page_id=page_id, type='code',
                content={'language': code_lang or 'text', 'code': '\n'.join(code_buffer)},
                sort_order=order,
            ))
            order += 1
            code_buffer.clear()

    for line in lines:
        stripped = line.strip()

        # 代码块
        if stripped.startswith('```'):
            if in_code:
                flush_blocks()
                in_code = False
                code_lang = ''
            else:
                code_lang = stripped[3:].strip()
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        # 空行
        if not stripped:
            continue

        # 标题
        h_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if h_match:
            blocks.append(Block(
                page_id=page_id, type='heading',
                content={'level': len(h_match.group(1)), 'text': h_match.group(2)},
                sort_order=order,
            ))
            order += 1
            continue

        # 引用
        if stripped.startswith('> '):
            blocks.append(Block(
                page_id=page_id, type='quote',
                content={'text': stripped[2:]},
                sort_order=order,
            ))
            order += 1
            continue

        # 分割线
        if re.match(r'^[-*_]{3,}$', stripped):
            blocks.append(Block(
                page_id=page_id, type='divider',
                content={},
                sort_order=order,
            ))
            order += 1
            continue

        # 无序列表
        if re.match(r'^[-*+]\s', stripped):
            blocks.append(Block(
                page_id=page_id, type='list',
                content={'ordered': False, 'text': re.sub(r'^[-*+]\s', '', stripped)},
                sort_order=order,
            ))
            order += 1
            continue

        # 默认段落
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': stripped},
            sort_order=order,
        ))
        order += 1

    flush_blocks()
    return blocks


def _parse_html(html_text: str, page_id: int, start_order: int) -> list[Block]:
    """简易 HTML 解析为 Block 列表（去除标签保留文本）"""
    from html.parser import HTMLParser

    blocks: list[Block] = []
    order = start_order

    class SimpleParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current_type = 'paragraph'
            self.current_text = ''
            self.heading_level = 0

        def handle_starttag(self, tag, attrs):
            if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                self.heading_level = int(tag[1])
            elif tag == 'blockquote':
                self.current_type = 'quote'
            elif tag in ('pre', 'code'):
                self.current_type = 'code'

        def handle_endtag(self, tag):
            nonlocal order
            if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                if self.current_text.strip():
                    blocks.append(Block(
                        page_id=page_id, type='heading',
                        content={'level': self.heading_level, 'text': self.current_text.strip()},
                        sort_order=order,
                    ))
                    order += 1
                self.heading_level = 0
                self.current_text = ''
            elif tag == 'blockquote':
                if self.current_text.strip():
                    blocks.append(Block(
                        page_id=page_id, type='quote',
                        content={'text': self.current_text.strip()},
                        sort_order=order,
                    ))
                    order += 1
                self.current_text = ''
                self.current_type = 'paragraph'
            elif tag in ('p', 'li', 'div', 'br'):
                if self.current_text.strip() or tag == 'br':
                    blocks.append(Block(
                        page_id=page_id, type='paragraph',
                        content={'text': self.current_text.strip()},
                        sort_order=order,
                    ))
                    order += 1
                self.current_text = ''
            elif tag in ('hr',):
                blocks.append(Block(
                    page_id=page_id, type='divider',
                    content={},
                    sort_order=order,
                ))
                order += 1

        def handle_data(self, data):
            self.current_text += data

    parser = SimpleParser()
    try:
        parser.feed(html_text)
    except Exception:
        # 如果HTML解析失败，当作纯文本
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': html_text[:5000]},
            sort_order=order,
        ))

    if not blocks:
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': '（空内容）'},
            sort_order=order,
        ))

    return blocks
