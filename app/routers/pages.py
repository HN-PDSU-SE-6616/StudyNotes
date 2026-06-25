"""页面 CRUD 路由"""
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
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
    PageStats,
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

# 静态资源目录（用于HTML导入时的资源上传）
STATIC_UPLOAD_ROOT = Path("static/uploads")
# MD子页面链接正则：[text](path/to/file.md "title") - 同时匹配 .md/.html/.htm 和无后缀路径
MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+?)(?:\s+"[^"]*")?\)')
# HTML资源引用正则
HTML_SRC_RE = re.compile(r'(src|href|url)\s*=\s*["\'](?!https?://|data:|/|#)([^"\']+)["\']', re.IGNORECASE)


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
    page = Page(
        workspace_id=workspace.id,
        creator_id=current_user.id,
        last_editor_id=current_user.id,
        **body.model_dump(),
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)

    # 新增页面默认添加一个空段落 block（用于内容占位提示）
    block = Block(
        page_id=page.id, type='paragraph',
        content={'text': ''},
        sort_order=0,
    )
    session.add(block)
    await session.commit()

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


@router.get("/by-slug/{slug}", response_model=PageDetail, summary="通过 slug 获取页面详情")
async def get_page_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    workspace = await get_user_workspace(session, current_user.id)
    result = await session.execute(
        select(Page).where(Page.workspace_id == workspace.id, Page.slug == slug)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page.id).order_by(Block.sort_order)
        )
    ).scalars().all()

    return PageDetail(
        **PageRead.model_validate(page).model_dump(),
        blocks=[BlockRead.model_validate(b) for b in blocks],
    )


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
    page.last_editor_id = current_user.id
    session.add(page)
    await session.commit()
    await session.refresh(page)

    # 如果排序或父级发生了变化，同步引用该页面的 page_link 块
    if 'sort_order' in body.model_dump(exclude_unset=True) or 'parent_id' in body.model_dump(exclude_unset=True):
        from app.services.page_service import sync_page_link_blocks_order
        await sync_page_link_blocks_order(session, page_id)

    return PageRead.model_validate(page)


@router.get("/{page_id}/stats", response_model=PageStats, summary="获取页面统计信息")
async def get_page_stats(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取页面的字数、块数、浏览量、创建/编辑者等统计信息"""
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    # 获取所有 blocks 并计算字数
    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.sort_order)
        )
    ).scalars().all()

    total_words = 0
    for b in blocks:
        c = b.content or {}
        if isinstance(c, dict):
            for tf in ('text', 'code'):
                text_val = c.get(tf, '')
                if isinstance(text_val, str):
                    total_words += len(text_val.replace(' ', ''))
            # list items
            items = c.get('items', [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        item_text = item.get('text', '')
                        if isinstance(item_text, str):
                            total_words += len(item_text.replace(' ', ''))
                    elif isinstance(item, str):
                        total_words += len(item.replace(' ', ''))

    # 获取创建者和最后编辑者的用户名
    from app.models.user import User as UserModel
    creator_name = None
    last_editor_name = None
    if page.creator_id:
        creator = await session.get(UserModel, page.creator_id)
        if creator:
            creator_name = creator.display_name or creator.username
    if page.last_editor_id:
        editor = await session.get(UserModel, page.last_editor_id)
        if editor:
            last_editor_name = editor.display_name or editor.username

    # 增加浏览量（每次获取统计信息时 +1）
    page.view_count = (page.view_count or 0) + 1
    session.add(page)
    await session.commit()
    await session.refresh(page)

    return PageStats(
        total_words=total_words,
        block_count=len(blocks),
        view_count=page.view_count,
        created_at=page.created_at,
        creator_name=creator_name,
        updated_at=page.updated_at,
        last_editor_name=last_editor_name,
    )


@router.post("/{page_id}/sync-link-blocks", summary="同步页面引用块")
async def sync_page_link_blocks(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """同步所有引用该页面的 page_link 块的排序位置和标题"""
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    from app.services.page_service import sync_page_link_blocks_order
    await sync_page_link_blocks_order(session, page_id)
    return {"message": "同步完成", "page_id": page_id}


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
    from app.services.page_service import sync_page_link_blocks_order

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

    # 同步所有引用该页面的 page_link 块
    await sync_page_link_blocks_order(session, page_id)

    return {"message": "页面已删除"}


@router.post("/{page_id}/duplicate", response_model=PageRead, summary="复制页面")
async def duplicate_page(
    page_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """拷贝页面副本，包含所有 Block 内容"""
    workspace = await get_user_workspace(session, current_user.id)
    page = await session.get(Page, page_id)
    if not page or page.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="页面不存在")

    # 获取原页面的 blocks
    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.sort_order)
        )
    ).scalars().all()

    # 创建副本页面
    new_page = Page(
        workspace_id=workspace.id,
        title=f"{page.title} (副本)",
        icon=page.icon,
        category=page.category,
        parent_id=page.parent_id,
        sort_order=page.sort_order + 1,
        creator_id=current_user.id,
        last_editor_id=current_user.id,
    )
    session.add(new_page)
    await session.commit()
    await session.refresh(new_page)

    # 复制 blocks
    for block in blocks:
        new_block = Block(
            page_id=new_page.id,
            type=block.type,
            content=block.content,
            sort_order=block.sort_order,
        )
        session.add(new_block)
    await session.commit()

    return PageRead.model_validate(new_page)


# ========== 导入目录/文件 ==========


# ---- 辅助函数 ----


def _detect_common_prefix(paths: list[str]) -> str:
    """
    检测所有路径的公共顶层目录前缀。
    如果有单一公共顶层目录则返回该目录名，否则返回空字符串。
    例如: ["大数据/大数据.md", "大数据/Spark/Spark.md"] → "大数据"
    """
    if not paths or len(paths) <= 1:
        return ''
    norms = [p.replace('\\', '/') for p in paths]
    first_parts = norms[0].split('/')
    common = []
    for i, part in enumerate(first_parts):
        for p in norms:
            p_parts = p.split('/')
            if i >= len(p_parts) or p_parts[i] != part:
                return '/'.join(common)
        common.append(part)
    return ''


def _is_placeholder_only_page(existing_blocks: list[Block]) -> bool:
    """检查页面是否只有占位 block（默认空段落块或空 H1 标题块）"""
    if len(existing_blocks) == 1:
        b = existing_blocks[0]
        if b.type == 'paragraph':
            para_text = (b.content.get('text') or '').strip()
            return not para_text
        if b.type == 'heading' and b.content.get('level') == 1:
            h1_text = (b.content.get('text') or '').strip()
            return not h1_text
    return False


def _group_md_files(
    file_map: dict[str, bytes],
) -> tuple[list[tuple[str, bytes]], dict[str, bytes], dict[str, list[tuple[str, bytes]]]]:
    """
    分组MD导入文件：
    - top_md_files: 顶层 .md 文件
    - image_files: image/media/img/images/assets 目录下的图片
    - regular_sub_dirs: 普通子目录
    """
    top_md_files: list[tuple[str, bytes]] = []
    image_files: dict[str, bytes] = {}
    regular_sub_dirs: dict[str, list[tuple[str, bytes]]] = defaultdict(list)

    for fp, content in file_map.items():
        norm = fp.replace('\\', '/')
        parts = norm.split('/')
        if len(parts) == 1:
            if norm.lower().endswith('.md'):
                top_md_files.append((fp, content))
        else:
            sub_dir = parts[0]
            sub_path = '/'.join(parts[1:])
            if sub_dir.lower() in ('image', 'media', 'img', 'images', 'assets'):
                image_files[norm] = content
            else:
                regular_sub_dirs[sub_dir].append((sub_path, content))

    return top_md_files, image_files, regular_sub_dirs


def _resolve_page_from_path(
    link_path: str,
    path_to_page: dict[str, PageRead],
) -> Optional[PageRead]:
    """
    多策略查找路径对应的页面。
    用于 _fix_page_links 中匹配 [text](path/to/file.md) 的 path 部分。
    """
    clean = link_path.replace('\\', '/').lower().strip()

    # 策略1：精确匹配
    if clean in path_to_page:
        return path_to_page[clean]

    # 策略2：去后缀匹配（.md / .html / .htm）
    no_ext = re.sub(r'\.(md|html|htm)$', '', clean)
    if no_ext in path_to_page:
        return path_to_page[no_ext]

    # 策略3：只用路径最后一段匹配（纯文件名/目录名）
    basename = os.path.basename(clean)
    no_ext_base = re.sub(r'\.(md|html|htm)$', '', basename)
    for k, v in path_to_page.items():
        k_lower = k.lower()
        k_basename = os.path.basename(k_lower)
        k_no_ext = re.sub(r'\.(md|html|htm)$', '', k_basename)
        if k_no_ext == no_ext_base:
            return v

    # 策略4：路径最后两段匹配（目录/文件名）
    parts = clean.strip('/').split('/')
    if len(parts) >= 2:
        last_two = '/'.join(parts[-2:])
        for k, v in path_to_page.items():
            k_lower = k.lower()
            if k_lower.endswith(last_two):
                return v
            k_no_ext = re.sub(r'\.(md|html|htm)$', '', k_lower)
            if k_no_ext.endswith('/'.join(parts[-2:])):
                return v

    return None


async def _clear_placeholder_blocks(session: AsyncSession, page_id: int) -> int:
    """
    如果页面只有占位 H1 block，则删除并返回 0（后续从 sort_order=0 开始导入）。
    否则返回当前最大 sort_order + 1。
    """
    existing = (
        await session.execute(
            select(Block).where(Block.page_id == page_id).order_by(Block.sort_order)
        )
    ).scalars().all()

    if _is_placeholder_only_page(existing):
        for b in existing:
            await session.delete(b)
        await session.commit()
        return 0
    else:
        return max([b.sort_order for b in existing], default=-1) + 1


# ---- MD 解析 ----

# TOC 条目正则：可选缩进 + - [text](#anchor)
_TOC_ITEM_RE = re.compile(r'^\s*[-*+]\s+\[[^\]]+\]\(#[^)]+\)\s*$')


def _strip_md_toc(md_text: str) -> str:
    """
    检测并移除 Markdown 文件中的目录（TOC）部分。
    目录特征：
    1. 以"目录"/"Table of Contents"等标题开头，后跟锚点链接列表项
    2. 或文档中首次出现连续锚点链接列表项（至少2个）

    返回移除目录后的 Markdown 文本。
    """
    lines = md_text.split('\n')
    n = len(lines)

    # 查找目录标题位置或首个 TOC 条目位置
    toc_start = -1
    for i in range(n):
        stripped = lines[i].strip()
        # 目录标题行：## 目录 / # Table of Contents 等
        if re.match(
            r'^#{1,3}\s*(目录|Table\s*of\s*Contents|Contents|目錄|目次)\s*$',
            stripped, re.IGNORECASE,
        ):
            toc_start = i
            break
        # 未遇到目录标题前，如果遇到非空且非 TOC 条目的行，说明没有目录
        if stripped and not re.match(r'^#{1,6}\s', stripped):
            if not _TOC_ITEM_RE.match(stripped):
                # 不是标题也不是 TOC 条目，不是目录，停止搜索
                break

    if toc_start < 0:
        return md_text  # 未找到目录

    # 从目录起始位置读取：跳过目录标题行（如果有），收集所有 TOC 条目
    i = toc_start
    if re.match(
        r'^#{1,3}\s*(目录|Table\s*of\s*Contents|Contents|目錄|目次)\s*$',
        lines[i].strip(), re.IGNORECASE,
    ):
        i += 1  # 跳过"目录"标题行

    toc_item_count = 0
    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1  # 跳过空行（目录内分隔）
            continue
        if _TOC_ITEM_RE.match(stripped):
            toc_item_count += 1
            i += 1
            continue
        # 遇到非 TOC 条目，停止
        break

    # 至少需要 2 个 TOC 条目才算有效目录
    if toc_item_count < 2:
        return md_text

    # 拼接结果：保留目录之前的内容，移除目录区域，拼接剩余内容
    # 移除 toc_start 到 i 之间的所有行
    # 跳过目录后的连续空行
    while i < n and not lines[i].strip():
        i += 1

    result = lines[:toc_start]
    # 清理结果尾部的空行
    while result and not result[-1].strip():
        result.pop()
    # 如果结果非空，添加一个空行作为分隔
    if result:
        result.append('')
    result.extend(lines[i:])

    return '\n'.join(result)


def _parse_md_to_blocks(md_text: str, page_id: int, start_order: int) -> list[Block]:
    """简易 Markdown 解析为 Block 列表，支持表格解析"""
    # 预处理：移除目录
    md_text = _strip_md_toc(md_text)

    blocks: list[Block] = []
    order = start_order
    lines = md_text.strip().split('\n')
    code_buffer: list[str] = []
    code_lang = ''
    in_code = False

    # 表格解析正则：匹配 | cell | cell | 格式的行
    _TABLE_ROW_RE = re.compile(r'^\s*\|(.+)\|\s*$')
    _TABLE_SEP_RE = re.compile(r'^\s*\|[\s:-]+\|[\s|:-]+$')

    def flush_code():
        nonlocal order
        if code_buffer:
            blocks.append(Block(
                page_id=page_id, type='code',
                content={'language': code_lang or 'text', 'code': '\n'.join(code_buffer)},
                sort_order=order,
            ))
            order += 1
            code_buffer.clear()

    def parse_table_cells(stripped_line: str) -> list[str]:
        """解析表格行中的单元格列表，并对每个单元格处理 Markdown 转义字符"""
        m = _TABLE_ROW_RE.match(stripped_line)
        if not m:
            return []
        return [unescape_md_table_cell(cell.strip()) for cell in m.group(1).split('|')]

    def unescape_md_table_cell(cell: str) -> str:
        """处理 Markdown 表格单元格中的反斜杠转义序列
        
        Markdown 表格中常用转义：
        - \| → |  （管道符）
        - \* → *  （星号）
        - \_ → _  （下划线）
        - \\ → \  （反斜杠）
        - \# → #  （井号）
        - \- → -  （连字符，避免被当作分隔行）
        - \` → `  （反引号）
        - \~ → ~  （波浪号）
        """
        # 先处理双反斜杠 → 占位符，避免被后续替换干扰
        cell = cell.replace('\\\\', '\x00')
        cell = cell.replace('\\|', '|')
        cell = cell.replace('\\*', '*')
        cell = cell.replace('\\_', '_')
        cell = cell.replace('\\#', '#')
        cell = cell.replace('\\-', '-')
        cell = cell.replace('\\`', '`')
        cell = cell.replace('\\~', '~')
        # 还原占位符为单个反斜杠
        cell = cell.replace('\x00', '\\')
        return cell

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith('```'):
            if in_code:
                flush_code()
                in_code = False
                code_lang = ''
            else:
                code_lang = stripped[3:].strip()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buffer.append(line)
            i += 1
            continue
        if not stripped:
            i += 1
            continue

        # ---- 表格检测：至少两列的表头行，且下一行是分隔行 ----
        header_cells = parse_table_cells(stripped)
        if len(header_cells) >= 2 and i + 1 < len(lines):
            next_stripped = lines[i + 1].strip()
            if _TABLE_SEP_RE.match(next_stripped):
                # 收集所有数据行
                headers = header_cells
                rows: list[list[str]] = []
                i += 2  # 跳过表头和分隔行
                while i < len(lines):
                    row_stripped = lines[i].strip()
                    if not row_stripped:
                        # 空行：允许在表格中保留，收集后继续看下一行
                        i += 1
                        continue
                    row_cells = parse_table_cells(row_stripped)
                    if len(row_cells) >= 2:
                        # 补齐列数到与表头一致
                        while len(row_cells) < len(headers):
                            row_cells.append('')
                        rows.append(row_cells)
                        i += 1
                    else:
                        # 不是表格行，结束表格收集
                        break
                # 创建表格块
                blocks.append(Block(
                    page_id=page_id, type='table',
                    content={'headers': headers, 'rows': rows},
                    sort_order=order,
                ))
                order += 1
                continue

        # 图片：![alt](path)
        img_match = re.match(r'^!\[([^\]]*)\]\(([^)]+)\)$', stripped)
        if img_match:
            blocks.append(Block(
                page_id=page_id, type='image',
                content={'url': img_match.group(2), 'alt': img_match.group(1)},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        h_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if h_match:
            blocks.append(Block(
                page_id=page_id, type='heading',
                content={'level': len(h_match.group(1)), 'text': h_match.group(2)},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        if stripped.startswith('> '):
            blocks.append(Block(
                page_id=page_id, type='quote',
                content={'text': stripped[2:]},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        if re.match(r'^[-*_]{3,}$', stripped):
            blocks.append(Block(
                page_id=page_id, type='divider',
                content={},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        # 任务列表
        task_match = re.match(r'^-\s+\[([ x])\]\s+(.+)', stripped)
        if task_match:
            blocks.append(Block(
                page_id=page_id, type='list',
                content={'ordered': False, 'task': True, 'items': [{'text': task_match.group(2), 'checked': task_match.group(1) == 'x'}]},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        if re.match(r'^[-*+]\s', stripped):
            blocks.append(Block(
                page_id=page_id, type='list',
                content={'ordered': False, 'text': re.sub(r'^[-*+]\s', '', stripped)},
                sort_order=order,
            ))
            order += 1
            i += 1
            continue
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': stripped},
            sort_order=order,
        ))
        order += 1
        i += 1

    flush_code()
    return blocks


# ---- HTML 解析 ----


def _parse_html_to_blocks_with_assets(
    html_text: str, page_id: int, start_order: int,
    file_map: dict[str, bytes], user_id: int,
) -> tuple[list[Block], str]:
    """解析HTML为Block，同时处理静态资源上传，支持表格解析，返回(blocks, 修复后的HTML)"""
    from html.parser import HTMLParser

    blocks: list[Block] = []
    order = start_order
    user_upload_dir = STATIC_UPLOAD_ROOT / str(user_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    # 修复HTML中的资源路径
    def fix_asset_path(match):
        attr = match.group(1)
        rel_path = match.group(2).replace('\\', '/')
        # 尝试在 file_map 中查找
        for fp, content in file_map.items():
            norm_fp = fp.replace('\\', '/')
            if norm_fp.endswith(rel_path) or norm_fp == rel_path:
                safe_name = f"{uuid.uuid4().hex[:8]}/{os.path.basename(rel_path)}"
                dest = user_upload_dir / safe_name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                return f'{attr}="/static/uploads/{user_id}/{safe_name}"'
        # 未找到，保持原样
        return match.group(0)

    fixed_html = HTML_SRC_RE.sub(fix_asset_path, html_text)

    # 解析为 blocks
    class SimpleParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.current_type = 'paragraph'
            self.current_text = ''
            self.heading_level = 0
            # 表格状态
            self.in_table = False
            self.in_thead = False
            self.in_tbody = False
            self.in_th = False
            self.in_td = False
            self.current_cell = ''
            self.table_headers: list[str] = []
            self.table_rows: list[list[str]] = []
            self.current_row: list[str] = []
            self.warnings: list[str] = []

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)

            # 表格相关标签
            if tag == 'table':
                self.in_table = True
                self.table_headers = []
                self.table_rows = []
                self.current_row = []
                return
            if not self.in_table:
                if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                    self.heading_level = int(tag[1])
                elif tag == 'blockquote':
                    self.current_type = 'quote'
                elif tag in ('pre', 'code'):
                    self.current_type = 'code'
                return

            # 表格内部标签
            if tag == 'thead':
                self.in_thead = True
            elif tag == 'tbody':
                self.in_tbody = True
            elif tag == 'tr':
                self.current_row = []
            elif tag in ('th', 'td'):
                if tag == 'th':
                    self.in_th = True
                else:
                    self.in_td = True
                self.current_cell = ''
                # 检查 colspan / rowspan
                colspan = attrs_dict.get('colspan')
                rowspan = attrs_dict.get('rowspan')
                if colspan and int(colspan) > 1:
                    self.warnings.append(f'cell with colspan={colspan} will be split')
                if rowspan and int(rowspan) > 1:
                    self.warnings.append(f'cell with rowspan={rowspan} may lose merge info')

        def handle_endtag(self, tag):
            nonlocal order

            if tag == 'table':
                self.in_table = False
                self.in_thead = False
                self.in_tbody = False
                # 如果只有 thead 没有 tbody，当前行可能还在
                self._flush_current_row()
                # 创建表格块
                headers = self.table_headers if self.table_headers else []
                rows = self.table_rows
                # 如果有 warnings，在表格块前插入一个 callout 提示
                if self.warnings:
                    blocks.append(Block(
                        page_id=page_id, type='callout',
                        content={'type': 'warning', 'text': '表格导入警告：' + '; '.join(self.warnings)},
                        sort_order=order,
                    ))
                    order += 1
                    self.warnings.clear()
                if headers or rows:
                    blocks.append(Block(
                        page_id=page_id, type='table',
                        content={'headers': headers, 'rows': rows},
                        sort_order=order,
                    ))
                    order += 1
                return

            if not self.in_table:
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
                return

            # 表格内部结束标签
            if tag == 'thead':
                self.in_thead = False
            elif tag == 'tbody':
                self.in_tbody = False
            elif tag == 'tr':
                self._flush_current_row()
            elif tag == 'th':
                self.in_th = False
                self.current_row.append(self.current_cell.strip())
            elif tag == 'td':
                self.in_td = False
                self.current_row.append(self.current_cell.strip())

        def _flush_current_row(self):
            if not self.current_row:
                return
            if self.in_thead:
                # 将 thead 中的行收集为 headers（可能多行thead，取第一行）
                if not self.table_headers:
                    self.table_headers = list(self.current_row)
                else:
                    # 额外的 thead 行作为数据行
                    self.table_rows.append(list(self.current_row))
            else:
                self.table_rows.append(list(self.current_row))
            self.current_row = []

        def handle_data(self, data):
            if self.in_th or self.in_td:
                self.current_cell += data
            else:
                self.current_text += data

    parser = SimpleParser()
    try:
        parser.feed(fixed_html)
    except Exception:
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': fixed_html[:5000]},
            sort_order=order,
        ))

    if not blocks:
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': '（空内容）'},
            sort_order=order,
        ))
    return blocks, fixed_html


# ---- 图片资源处理 ----


def _upload_md_image_assets(
    image_files: dict[str, bytes],
    user_id: int,
) -> dict[str, str]:
    """上传MD导入中的图片文件到静态目录。返回 {原始相对路径: 静态URL}"""
    mapping: dict[str, str] = {}
    user_upload_dir = STATIC_UPLOAD_ROOT / str(user_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)

    for file_path, content in image_files.items():
        norm = file_path.replace('\\', '/')
        ext = os.path.splitext(norm)[1].lower()
        if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'):
            continue
        safe_name = f"{uuid.uuid4().hex[:8]}/{os.path.basename(norm)}"
        dest = user_upload_dir / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        url = f"/static/uploads/{user_id}/{safe_name}"
        # 同时按完整路径和文件名索引
        mapping[norm] = url
        mapping[os.path.basename(norm)] = url

    return mapping


def _replace_md_image_paths(md_text: str, image_map: dict[str, str]) -> str:
    """替换MD文本中的图片路径为上传后的静态URL"""
    def replacer(m: re.Match) -> str:
        alt = m.group(1)
        img_path = m.group(2).replace('\\', '/')
        # 精确匹配
        if img_path in image_map:
            return f'![{alt}]({image_map[img_path]})'
        # 去掉可能的 ./ 前缀
        clean = re.sub(r'^\./', '', img_path)
        if clean in image_map:
            return f'![{alt}]({image_map[clean]})'
        # 按文件名匹配
        basename = os.path.basename(img_path)
        if basename in image_map:
            return f'![{alt}]({image_map[basename]})'
        return m.group(0)

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replacer, md_text)


# ---- 核心导入逻辑 ----


async def _import_md_tree(
    session: AsyncSession,
    workspace_id: int,
    file_map: dict[str, bytes],
    parent_page: Page,
    user_id: int,
    path_prefix: str = '',
    processed: Optional[set[str]] = None,
) -> dict[str, PageRead]:
    """
    递归导入MD文件树。
    顶层 .md 文件内容注入 parent_page 的 blocks。
    普通子目录创建为子页面。
    image/media/img/images/assets 目录作为静态资源上传。

    path_prefix: 从导入根目录到当前目录的路径（用于构建正确的映射键）
    processed: 已处理的完整路径集合（防止重复导入）

    返回 {完整规范化路径: PageRead} 映射，用于后续链接修复。
    """
    if processed is None:
        processed = set()

    path_to_page: dict[str, PageRead] = {}

    top_md_files, image_files, regular_sub_dirs = _group_md_files(file_map)

    # ---- 上传图片资源 ----
    image_map: dict[str, str] = {}
    if image_files:
        image_map = _upload_md_image_assets(image_files, user_id)

    # ---- 第一阶段：处理顶层 .md 文件，内容注入 parent_page ----
    # 如果 parent_page 只有占位 H1 block，先清除
    current_order = await _clear_placeholder_blocks(session, parent_page.id)

    for file_path, content in top_md_files:
        norm = file_path.replace('\\', '/')
        # 构建完整路径（相对于导入根目录）
        full_path = f"{path_prefix}/{norm}".lstrip('/') if path_prefix else norm

        if full_path in processed:
            continue
        processed.add(full_path)

        md_text = content.decode('utf-8', errors='replace')

        # 替换MD中的图片路径
        if image_map:
            md_text = _replace_md_image_paths(md_text, image_map)

        # 解析为 blocks 添加到 parent_page
        blocks = _parse_md_to_blocks(md_text, parent_page.id, current_order)
        for b in blocks:
            session.add(b)
            current_order += 1
        await session.commit()

        # 记录路径→页面映射（完整路径 + 去后缀路径）
        path_key = full_path.rstrip('/').lower()
        path_to_page[path_key] = PageRead.model_validate(parent_page)
        # 同时记录去后缀版本（方便匹配不带后缀的链接）
        no_ext_key = re.sub(r'\.md$', '', path_key)
        if no_ext_key != path_key:
            path_to_page[no_ext_key] = PageRead.model_validate(parent_page)

        # 同步标题
        all_blocks = (
            await session.execute(
                select(Block).where(Block.page_id == parent_page.id).order_by(Block.sort_order)
            )
        ).scalars().all()
        _sync_title_from_blocks(parent_page, all_blocks)
        session.add(parent_page)
        await session.commit()
        await session.refresh(parent_page)
        # 更新映射中的页面信息
        page_read = PageRead.model_validate(parent_page)
        path_to_page[path_key] = page_read
        if no_ext_key != path_key:
            path_to_page[no_ext_key] = page_read

    # ---- 第二阶段：普通子目录创建为子页面并递归 ----
    for dir_name, sub_files in regular_sub_dirs.items():
        sub_map = {fp: fc for fp, fc in sub_files}
        # 构建子目录的完整路径前缀
        sub_prefix = f"{path_prefix}/{dir_name}".lstrip('/') if path_prefix else dir_name

        # 创建子页面
        child_page = Page(
            workspace_id=workspace_id,
            title=dir_name,
            icon='📁',
            parent_id=parent_page.id,
            creator_id=user_id,
            last_editor_id=user_id,
        )
        session.add(child_page)
        await session.commit()
        await session.refresh(child_page)

        # 递归导入子目录内容
        child_map = await _import_md_tree(
            session, workspace_id, sub_map, child_page, user_id,
            path_prefix=sub_prefix,
            processed=processed,
        )

        # 合并子目录的路径映射
        for k, v in child_map.items():
            path_to_page[k] = v

        # 子目录本身也加入映射
        dir_key = sub_prefix.lower()
        path_to_page[dir_key] = PageRead.model_validate(child_page)

    return path_to_page


async def _import_html_tree(
    session: AsyncSession,
    workspace_id: int,
    file_map: dict[str, bytes],
    user_id: int,
    parent_page: Page,
    path_prefix: str = '',
    processed: Optional[set[str]] = None,
) -> dict[str, PageRead]:
    """
    递归导入HTML文件树。
    顶层 .html 文件内容注入 parent_page 的 blocks。
    CSS/media/fonts/image/img 作为静态资源上传。
    普通子目录创建为子页面。
    返回 {完整规范化路径: PageRead} 映射。
    """
    if processed is None:
        processed = set()

    path_to_page: dict[str, PageRead] = {}

    # 分类：顶层HTML、静态资源、普通子目录
    top_html_files: dict[str, bytes] = {}
    asset_files: dict[str, bytes] = {}
    regular_sub_dirs: dict[str, list[tuple[str, bytes]]] = defaultdict(list)
    static_dirs = {'css', 'media', 'fonts', 'js', 'image', 'img', 'images'}

    for fp, content in file_map.items():
        norm = fp.replace('\\', '/')
        parts = norm.split('/')

        if len(parts) == 1:
            if norm.lower().endswith(('.html', '.htm')):
                top_html_files[fp] = content
            else:
                asset_files[fp] = content
        else:
            sub_dir = parts[0]
            sub_path = '/'.join(parts[1:])
            if sub_dir.lower() in static_dirs:
                asset_files[norm] = content
            else:
                regular_sub_dirs[sub_dir].append((sub_path, content))

    # ---- 第一阶段：顶层 HTML 文件内容注入 parent_page ----
    current_order = await _clear_placeholder_blocks(session, parent_page.id)

    for file_path, content in top_html_files.items():
        norm = file_path.replace('\\', '/')
        full_path = f"{path_prefix}/{norm}".lstrip('/') if path_prefix else norm

        if full_path in processed:
            continue
        processed.add(full_path)

        html_text = content.decode('utf-8', errors='replace')

        all_files = {**asset_files, file_path: content}
        blocks, _ = _parse_html_to_blocks_with_assets(html_text, parent_page.id, current_order, all_files, user_id)
        for b in blocks:
            session.add(b)
            current_order += 1
        await session.commit()

        # 记录路径映射
        path_key = full_path.rstrip('/').lower()
        path_to_page[path_key] = PageRead.model_validate(parent_page)
        no_ext_key = re.sub(r'\.(html|htm)$', '', path_key)
        if no_ext_key != path_key:
            path_to_page[no_ext_key] = PageRead.model_validate(parent_page)

        # 同步标题
        all_blocks_list = (
            await session.execute(
                select(Block).where(Block.page_id == parent_page.id).order_by(Block.sort_order)
            )
        ).scalars().all()
        _sync_title_from_blocks(parent_page, all_blocks_list)
        session.add(parent_page)
        await session.commit()
        await session.refresh(parent_page)
        page_read = PageRead.model_validate(parent_page)
        path_to_page[path_key] = page_read
        if no_ext_key != path_key:
            path_to_page[no_ext_key] = page_read

    # ---- 第二阶段：普通子目录创建为子页面 ----
    for dir_name, sub_files in regular_sub_dirs.items():
        sub_map = {fp: fc for fp, fc in sub_files}
        sub_prefix = f"{path_prefix}/{dir_name}".lstrip('/') if path_prefix else dir_name

        # 创建子页面
        child_page = Page(
            workspace_id=workspace_id,
            title=dir_name,
            icon='📁',
            parent_id=parent_page.id,
            creator_id=user_id,
            last_editor_id=user_id,
        )
        session.add(child_page)
        await session.commit()
        await session.refresh(child_page)

        # 判断子目录中的文件类型
        md_count = sum(1 for fp in sub_map if fp.lower().endswith('.md'))
        html_count = sum(1 for fp in sub_map if fp.lower().endswith(('.html', '.htm')))

        if md_count >= html_count:
            child_map = await _import_md_tree(
                session, workspace_id, sub_map, child_page, user_id,
                path_prefix=sub_prefix,
                processed=processed,
            )
        else:
            child_map = await _import_html_tree(
                session, workspace_id, sub_map, user_id, child_page,
                path_prefix=sub_prefix,
                processed=processed,
            )

        for k, v in child_map.items():
            path_to_page[k] = v

        path_to_page[sub_prefix.lower()] = PageRead.model_validate(child_page)

    return path_to_page


# ---- 链接修复 ----


def _sync_title_from_blocks(page: Page, blocks: list[Block]) -> None:
    """如果页面标题为默认值，从第一个 H1 block 提取标题"""
    if page.title in ('无标题页面', '无标题子页面', ''):
        for b in blocks:
            if b.type == 'heading' and b.content.get('level') == 1:
                h1_text = (b.content.get('text') or '').strip()
                if h1_text:
                    page.title = h1_text
                return


async def _fix_page_links(
    session: AsyncSession,
    page: Page,
    path_to_page: dict[str, PageRead],
) -> None:
    """
    第二阶段：将页面 blocks 中的文件路径链接替换为实际页面 URL。
    - MD: [text](path/to/file.md) → [页面标题](/notes/{slug})
    - 路径匹配策略由 _resolve_page_from_path 处理
    """
    blocks = (
        await session.execute(
            select(Block).where(Block.page_id == page.id).order_by(Block.sort_order)
        )
    ).scalars().all()

    modified = False

    def _replace_link(m: re.Match) -> str:
        link_path = m.group(2)
        # 跳过外部链接（http/https/data/mailto）
        if re.match(r'^(https?:|data:|mailto:|#|/)', link_path):
            return m.group(0)
        target = _resolve_page_from_path(link_path, path_to_page)
        if target:
            return f'[{target.title}](/notes/{target.slug})'
        return m.group(0)

    link_re_loose = re.compile(r'\[([^\]]+)\]\(([^)]+?)(?:\s+"[^"]*")?\)')

    for block in blocks:
        # 浅拷贝 content dict，确保后续赋值是一个新对象，
        # 否则 SQLAlchemy 的 dirty-check 无法检测到 JSON 列的变更。
        raw_content = block.content
        if isinstance(raw_content, dict):
            content = dict(raw_content)
        elif raw_content:
            # 非 dict 类型（如 list/str），先跳过，后续会被 continue 过滤
            content = raw_content
        else:
            content = {}
        if not isinstance(content, dict):
            continue
        changed = False

        # 处理 page_link 类型：修正 page_id
        if block.type == 'page_link':
            raw_page_id = content.get('page_id')
            if isinstance(raw_page_id, str):
                target = _resolve_page_from_path(raw_page_id, path_to_page)
                if target:
                    content['page_id'] = target.id
                    content['title'] = target.title
                    changed = True
            elif isinstance(raw_page_id, (int, float)):
                pass  # 已经是数字ID，跳过

        # 处理 text/code 字段中的 MD 链接
        for tf in ('text', 'code'):
            raw = content.get(tf, '')
            if not isinstance(raw, str) or not raw:
                continue
            new_raw = MD_LINK_RE.sub(_replace_link, raw)
            if new_raw != raw:
                content[tf] = new_raw
                changed = True

        if 'items' in content and isinstance(content['items'], list):
            new_items = []
            items_changed = False
            for item in content['items']:
                if isinstance(item, dict) and 'text' in item and isinstance(item['text'], str):
                    new_text = MD_LINK_RE.sub(_replace_link, item['text'])
                    if new_text != item['text']:
                        items_changed = True
                        new_items.append({**item, 'text': new_text})
                    else:
                        new_items.append(item)
                else:
                    new_items.append(item)
            if items_changed:
                content['items'] = new_items
                changed = True

        # 处理 table 块的 rows 中的 MD 链接
        if block.type == 'table' and 'rows' in content and isinstance(content['rows'], list):
            new_rows = []
            rows_changed = False
            for row in content['rows']:
                if isinstance(row, list):
                    new_row = []
                    for cell in row:
                        if isinstance(cell, str):
                            new_cell = MD_LINK_RE.sub(_replace_link, cell)
                            if new_cell != cell:
                                rows_changed = True
                            new_row.append(new_cell)
                        else:
                            new_row.append(cell)
                    new_rows.append(new_row)
                else:
                    new_rows.append(row)
            if rows_changed:
                content['rows'] = new_rows
                changed = True

        if changed:
            block.content = content
            session.add(block)
            modified = True

    if modified:
        await session.commit()


# ---- 通用文件类型解析 ----

# 代码文件扩展名 → highlight.js 语言映射
CODE_EXT_TO_LANG: dict[str, str] = {
    '.py': 'python', '.js': 'javascript', '.jsx': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript', '.vue': 'html',
    '.css': 'css', '.scss': 'css', '.less': 'css',
    '.html': 'html', '.htm': 'html', '.xml': 'xml', '.svg': 'xml',
    '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml',
    '.sql': 'sql', '.sh': 'bash', '.bash': 'bash', '.zsh': 'bash',
    '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.h': 'c', '.hpp': 'cpp',
    '.go': 'go', '.rs': 'rust', '.rb': 'ruby', '.php': 'php',
    '.r': 'r', '.swift': 'swift', '.kt': 'kotlin', '.scala': 'scala',
    '.lua': 'lua', '.dart': 'dart', '.cs': 'csharp',
    '.md': 'markdown', '.txt': 'text',
    '.ini': 'ini', '.cfg': 'ini', '.conf': 'ini',
    '.env': 'bash', '.gitignore': 'bash', '.dockerfile': 'dockerfile',
    '.bat': 'bash', '.ps1': 'powershell',
}

# 文件扩展名 → 类型分类
FILE_TYPE_MAP: dict[str, str] = {
    '.md': 'md', '.html': 'html', '.htm': 'html',
    '.txt': 'txt', '.csv': 'txt', '.log': 'txt',
    '.py': 'code', '.js': 'code', '.jsx': 'code', '.ts': 'code', '.tsx': 'code',
    '.css': 'code', '.scss': 'code', '.less': 'code',
    '.java': 'code', '.c': 'code', '.cpp': 'code', '.h': 'code', '.hpp': 'code',
    '.go': 'code', '.rs': 'code', '.rb': 'code', '.php': 'code',
    '.r': 'code', '.swift': 'code', '.kt': 'code', '.scala': 'code',
    '.lua': 'code', '.dart': 'code', '.cs': 'code',
    '.sql': 'code', '.sh': 'code', '.bash': 'code', '.zsh': 'code',
    '.json': 'code', '.yaml': 'code', '.yml': 'code', '.toml': 'code', '.xml': 'code',
    '.ini': 'code', '.cfg': 'code', '.conf': 'code',
    '.bat': 'code', '.ps1': 'code',
    '.png': 'image', '.jpg': 'image', '.jpeg': 'image', '.gif': 'image',
    '.webp': 'image', '.svg': 'image', '.bmp': 'image', '.ico': 'image',
    '.xlsx': 'xlsx', '.xls': 'xlsx',
    '.docx': 'docx', '.doc': 'docx',
    '.pdf': 'pdf',
    '.pptx': 'ppt', '.ppt': 'ppt',
    '.xmind': 'xmind',
}


def _get_file_type(file_path: str) -> str:
    """根据文件扩展名返回文件类型分类"""
    ext = os.path.splitext(file_path)[1].lower()
    return FILE_TYPE_MAP.get(ext, 'unknown')


def _get_language_for_code_file(file_path: str) -> str:
    """根据文件扩展名返回代码语言标识"""
    ext = os.path.splitext(file_path)[1].lower()
    return CODE_EXT_TO_LANG.get(ext, 'text')


def _parse_generic_file_to_blocks(
    file_path: str, content: bytes, page_id: int, user_id: int, start_order: int,
) -> list[Block]:
    """
    将非 MD/HTML 文件解析为 Block 列表。
    对于无法解析内容的文件（如 PDF、图片等），创建描述性 block 并上传源文件。
    """
    file_type = _get_file_type(file_path)
    file_name = os.path.basename(file_path)

    # MD 文件解析为 blocks
    if file_type == 'md':
        try:
            md_text = content.decode('utf-8', errors='replace')[:50000]
        except Exception:
            md_text = content.decode('latin-1', errors='replace')[:50000]
        md_text = _strip_md_toc(md_text)
        return _parse_md_to_blocks(md_text, page_id, start_order)

    # HTML 文件解析为 blocks
    if file_type == 'html':
        try:
            html_text = content.decode('utf-8', errors='replace')[:50000]
        except Exception:
            html_text = content.decode('latin-1', errors='replace')[:50000]
        blocks, _ = _parse_html_to_blocks_with_assets(html_text, page_id, start_order, {file_path: content}, user_id)
        return blocks

    if file_type == 'txt':
        try:
            text = content.decode('utf-8', errors='replace')[:50000]
        except Exception:
            text = content.decode('latin-1', errors='replace')[:50000]
        return [Block(
            page_id=page_id, type='paragraph',
            content={'text': text},
            sort_order=start_order,
        )]

    if file_type == 'code':
        try:
            code = content.decode('utf-8', errors='replace')[:50000]
        except Exception:
            code = content.decode('latin-1', errors='replace')[:50000]
        lang = _get_language_for_code_file(file_path)
        return [Block(
            page_id=page_id, type='code',
            content={'language': lang, 'code': code},
            sort_order=start_order,
        )]

    if file_type == 'image':
        # 上传图片文件到静态目录
        user_upload_dir = STATIC_UPLOAD_ROOT / str(user_id)
        user_upload_dir.mkdir(parents=True, exist_ok=True)
        ext = os.path.splitext(file_name)[1].lower()
        safe_name = f"{uuid.uuid4().hex[:8]}/{file_name}"
        dest = user_upload_dir / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        url = f"/static/uploads/{user_id}/{safe_name}"
        return [Block(
            page_id=page_id, type='image',
            content={'url': url, 'alt': file_name},
            sort_order=start_order,
        )]

    if file_type == 'xlsx':
        return _parse_xlsx_to_blocks(content, page_id, start_order, file_name, user_id)

    if file_type == 'docx':
        return _parse_docx_to_blocks(content, page_id, start_order, file_name, user_id)

    if file_type == 'pdf':
        return _parse_pdf_to_blocks(content, page_id, start_order, file_name, user_id)

    if file_type == 'ppt':
        return _parse_pptx_to_blocks(content, page_id, start_order, file_name, user_id)

    if file_type == 'xmind':
        return _parse_xmind_to_blocks(content, page_id, start_order, file_name, user_id)

    # 未知类型：上传文件并创建引用
    return _create_file_reference_block(content, page_id, user_id, start_order, file_name)


def _create_file_reference_block(
    content: bytes, page_id: int, user_id: int, start_order: int, file_name: str,
) -> list[Block]:
    """对于无法解析的文件，上传并创建引用 block"""
    user_upload_dir = STATIC_UPLOAD_ROOT / str(user_id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}/{file_name}"
    dest = user_upload_dir / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    url = f"/static/uploads/{user_id}/{safe_name}"
    return [Block(
        page_id=page_id, type='paragraph',
        content={'text': f"📎 [{file_name}]({url})"},
        sort_order=start_order,
    )]


def _parse_xlsx_to_blocks(content: bytes, page_id: int, start_order: int, file_name: str, user_id: int = 0) -> list[Block]:
    """解析 Excel 文件为表格 block"""
    try:
        import openpyxl
        from io import BytesIO
        wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
        blocks: list[Block] = []
        order = start_order
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(max_row=min(ws.max_row, 500), values_only=True))
            if not rows:
                continue
            headers = [str(c) if c is not None else '' for c in rows[0]]
            data_rows = [[str(c) if c is not None else '' for c in row] for row in rows[1:]]
            if wb.sheetnames[0] != sheet_name:
                blocks.append(Block(
                    page_id=page_id, type='heading',
                    content={'level': 2, 'text': f'工作表: {sheet_name}'},
                    sort_order=order,
                ))
                order += 1
            blocks.append(Block(
                page_id=page_id, type='table',
                content={'headers': headers, 'rows': data_rows},
                sort_order=order,
            ))
            order += 1
        wb.close()
        return blocks
    except ImportError:
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except Exception:
        return [Block(
            page_id=page_id, type='callout',
            content={'type': 'warning', 'text': f'无法解析 Excel 文件: {file_name}'},
            sort_order=start_order,
        )]


def _parse_docx_to_blocks(content: bytes, page_id: int, start_order: int, file_name: str, user_id: int = 0) -> list[Block]:
    """解析 Word 文档为段落 blocks"""
    try:
        from docx import Document
        from io import BytesIO
        doc = Document(BytesIO(content))
        blocks: list[Block] = []
        order = start_order
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            # 检测样式作为标题
            if para.style and para.style.name and 'Heading' in para.style.name:
                level_str = para.style.name.replace('Heading', '').strip()
                try:
                    level = int(level_str) if level_str else 1
                except ValueError:
                    level = 1
                blocks.append(Block(
                    page_id=page_id, type='heading',
                    content={'level': min(level, 6), 'text': text},
                    sort_order=order,
                ))
            else:
                blocks.append(Block(
                    page_id=page_id, type='paragraph',
                    content={'text': text},
                    sort_order=order,
                ))
            order += 1
            if len(blocks) >= 500:
                break
        return blocks
    except ImportError:
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except Exception:
        return [Block(
            page_id=page_id, type='callout',
            content={'type': 'warning', 'text': f'无法解析 Word 文档: {file_name}'},
            sort_order=start_order,
        )]


def _parse_pdf_to_blocks(content: bytes, page_id: int, start_order: int, file_name: str, user_id: int = 0) -> list[Block]:
    """解析 PDF 文件文本内容为段落 blocks"""
    try:
        from PyPDF2 import PdfReader
        from io import BytesIO
        reader = PdfReader(BytesIO(content))
        blocks: list[Block] = []
        order = start_order
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                if len(reader.pages) > 1:
                    blocks.append(Block(
                        page_id=page_id, type='heading',
                        content={'level': 3, 'text': f'第 {page_num + 1} 页'},
                        sort_order=order,
                    ))
                    order += 1
                # 按段落分割
                for para in text.strip().split('\n\n'):
                    para = para.strip()
                    if para:
                        blocks.append(Block(
                            page_id=page_id, type='paragraph',
                            content={'text': para},
                            sort_order=order,
                        ))
                        order += 1
                if len(blocks) >= 500:
                    break
        return blocks if blocks else _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except ImportError:
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except Exception:
        return [Block(
            page_id=page_id, type='callout',
            content={'type': 'warning', 'text': f'无法解析 PDF 文件: {file_name}'},
            sort_order=start_order,
        )]


def _parse_pptx_to_blocks(content: bytes, page_id: int, start_order: int, file_name: str, user_id: int = 0) -> list[Block]:
    """解析 PPT 文件文本内容为段落 blocks"""
    try:
        from pptx import Presentation
        from io import BytesIO
        prs = Presentation(BytesIO(content))
        blocks: list[Block] = []
        order = start_order
        for slide_num, slide in enumerate(prs.slides):
            slide_texts: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            slide_texts.append(t)
            if slide_texts:
                blocks.append(Block(
                    page_id=page_id, type='heading',
                    content={'level': 3, 'text': f'幻灯片 {slide_num + 1}'},
                    sort_order=order,
                ))
                order += 1
                for t in slide_texts:
                    blocks.append(Block(
                        page_id=page_id, type='paragraph',
                        content={'text': t},
                        sort_order=order,
                    ))
                    order += 1
            if len(blocks) >= 500:
                break
        return blocks if blocks else _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except ImportError:
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except Exception:
        return [Block(
            page_id=page_id, type='callout',
            content={'type': 'warning', 'text': f'无法解析 PPT 文件: {file_name}'},
            sort_order=start_order,
        )]


def _parse_xmind_to_blocks(content: bytes, page_id: int, start_order: int, file_name: str, user_id: int = 0) -> list[Block]:
    """解析 XMind 文件为大纲 blocks"""
    try:
        import zipfile
        from io import BytesIO
        import json as json_lib
        with zipfile.ZipFile(BytesIO(content)) as zf:
            # XMind 文件中的 content.json 包含思维导图数据
            if 'content.json' in zf.namelist():
                data = json_lib.loads(zf.read('content.json').decode('utf-8'))
                blocks = _parse_xmind_json(data, page_id, start_order)
                if blocks:
                    return blocks
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except ImportError:
        return _create_file_reference_block(content, page_id, user_id, start_order, file_name)
    except Exception:
        return [Block(
            page_id=page_id, type='callout',
            content={'type': 'warning', 'text': f'无法解析 XMind 文件: {file_name}'},
            sort_order=start_order,
        )]


def _parse_xmind_json(data, page_id: int, start_order: int, level: int = 1) -> list[Block]:
    """递归解析 XMind JSON 结构"""
    blocks: list[Block] = []
    order = start_order
    # XMind 数据结构多样，尝试多种格式
    root_topic = None
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                rt = item.get('rootTopic')
                if rt:
                    root_topic = rt
                    break
    elif isinstance(data, dict):
        root_topic = data.get('rootTopic')

    if root_topic and isinstance(root_topic, dict):
        title = root_topic.get('title', '')
        if title:
            blocks.append(Block(
                page_id=page_id, type='heading',
                content={'level': min(level, 6), 'text': str(title)},
                sort_order=order,
            ))
            order += 1
        # 递归处理子节点
        children = root_topic.get('children', {})
        if isinstance(children, dict):
            attached = children.get('attached', [])
            for child in attached:
                if isinstance(child, dict):
                    child_blocks = _parse_xmind_topic(child, page_id, order, level + 1)
                    blocks.extend(child_blocks)
                    order += len(child_blocks)
    return blocks


def _parse_xmind_topic(topic: dict, page_id: int, start_order: int, level: int) -> list[Block]:
    """递归解析 XMind 主题节点"""
    blocks: list[Block] = []
    order = start_order
    title = topic.get('title', '')
    if title:
        indent = '  ' * (level - 1)
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': f'{indent}• {title}'},
            sort_order=order,
        ))
        order += 1
    children = topic.get('children', {})
    if isinstance(children, dict):
        attached = children.get('attached', [])
        for child in attached:
            if isinstance(child, dict):
                child_blocks = _parse_xmind_topic(child, page_id, order, level + 1)
                blocks.extend(child_blocks)
                order += len(child_blocks)
    return blocks


async def _check_duplicate_child_page(session: AsyncSession, workspace_id: int, parent_id: int, title: str) -> Optional[int]:
    """检查同一父页面下是否存在同名的子页面，返回已有页面ID或None"""
    result = await session.execute(
        select(Page).where(
            Page.workspace_id == workspace_id,
            Page.parent_id == parent_id,
            Page.title == title,
        )
    )
    existing = result.scalar_one_or_none()
    return existing.id if existing else None


async def _import_generic_files(
    session: AsyncSession,
    workspace_id: int,
    file_map: dict[str, bytes],
    user_id: int,
    parent_page: Optional[Page],
    overwrite: bool = False,
) -> list[PageRead]:
    """
    导入通用文件（非 MD/HTML）：每个文件创建为独立页面。
    目录结构保留为页面层级。
    """
    # 将文件按目录结构分组
    top_files: list[tuple[str, bytes]] = []  # 顶层文件
    sub_dirs: dict[str, dict[str, bytes]] = defaultdict(lambda: {})
    file_icon = {'image': '🖼️', 'code': '💻', 'txt': '📄', 'xlsx': '📊', 'docx': '📝', 'pdf': '📕', 'ppt': '📽️', 'xmind': '🧠'}

    for fp, content in file_map.items():
        norm = fp.replace('\\', '/')
        parts = norm.split('/')
        if len(parts) == 1:
            top_files.append((fp, content))
        else:
            sub_dir = parts[0]
            sub_path = '/'.join(parts[1:])
            sub_dirs[sub_dir][sub_path] = content

    created_pages: list[PageRead] = []

    # 处理顶层文件
    for file_path, content in top_files:
        file_name = os.path.basename(file_path)
        title = os.path.splitext(file_name)[0]
        file_type = _get_file_type(file_path)
        icon = file_icon.get(file_type, '📎')

        parent_id = parent_page.id if parent_page else None

        # 检查重名
        if not overwrite and parent_id:
            dup_id = await _check_duplicate_child_page(session, workspace_id, parent_id, title)
            if dup_id:
                # 跳过重复文件
                continue

        new_page = Page(
            workspace_id=workspace_id,
            title=title,
            icon=icon,
            parent_id=parent_id,
            creator_id=user_id,
            last_editor_id=user_id,
        )
        session.add(new_page)
        await session.commit()
        await session.refresh(new_page)

        blocks = _parse_generic_file_to_blocks(file_path, content, new_page.id, user_id, 0)
        for b in blocks:
            session.add(b)
        await session.commit()
        created_pages.append(PageRead.model_validate(new_page))

    # 递归处理子目录
    for dir_name, sub_files in sub_dirs.items():
        dir_page = Page(
            workspace_id=workspace_id,
            title=dir_name,
            icon='📁',
            parent_id=parent_page.id if parent_page else None,
            creator_id=user_id,
            last_editor_id=user_id,
        )
        session.add(dir_page)
        await session.commit()
        await session.refresh(dir_page)
        created_pages.append(PageRead.model_validate(dir_page))

        sub_created = await _import_generic_files(
            session, workspace_id, sub_files, user_id, dir_page, overwrite,
        )
        created_pages.extend(sub_created)

    return created_pages


@router.get("/check-duplicate", summary="检查页面重名")
async def check_duplicate_page(
    parent_id: int = Query(...),
    title: str = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """检查同一父页面下是否有同名子页面"""
    workspace = await get_user_workspace(session, current_user.id)
    dup_id = await _check_duplicate_child_page(session, workspace.id, parent_id, title)
    return {"exists": dup_id is not None, "page_id": dup_id}


@router.post("/import", response_model=list[PageRead], summary="导入目录/文件到页面树")
async def import_pages(
    files: list[UploadFile] = File(...),
    parent_id: Optional[int] = Form(None),
    overwrite: bool = Form(False),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    导入目录或文件到指定页面（或新建根页面）。

    流程：
    1. 收集文件，如果指定了 parent_id 则导入到已有页面，否则创建新根页面
    2. 递归构建页面树（目录结构 = 页面层级）
       - 目录根的 .md/.html 文件内容注入目标页面的 blocks
       - 子目录创建为子页面
       - image/media 作为静态资源上传，图片路径替换为静态 URL
    3. 所有页面创建完毕后，二阶段修复：
       - [text](path/to/file.md) → [页面标题](/notes/{slug})
    """
    workspace = await get_user_workspace(session, current_user.id)

    # ---- 收集所有文件 ----
    file_map: dict[str, bytes] = {}
    for file in files:
        if not file.filename:
            continue
        path = file.filename.replace('\\', '/')
        content = await file.read()
        file_map[path] = content

    if not file_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可导入的文件")

    # ---- 确定目标页面 ----
    if parent_id is not None:
        target_page = await session.get(Page, parent_id)
        if not target_page or target_page.workspace_id != workspace.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标页面不存在")
        is_new = False
    else:
        target_page = Page(
            workspace_id=workspace.id,
            title='导入的页面',
            icon='📥',
            creator_id=current_user.id,
            last_editor_id=current_user.id,
        )
        session.add(target_page)
        await session.commit()
        await session.refresh(target_page)
        is_new = True

    # ---- 检测格式 ----
    md_count = sum(1 for p in file_map if p.lower().endswith('.md'))
    html_count = sum(1 for p in file_map if p.lower().endswith(('.html', '.htm')))

    # ---- 分离 MD/HTML 文件和通用文件 ----
    md_html_map: dict[str, bytes] = {}
    generic_map: dict[str, bytes] = {}
    for fp, fc in file_map.items():
        ft = _get_file_type(fp)
        if ft in ('md', 'html'):
            md_html_map[fp] = fc
        else:
            generic_map[fp] = fc

    # ---- 检测并剥离公共路径前缀 ----
    common_prefix = _detect_common_prefix(list(file_map.keys()))
    stripped_map: dict[str, str] = {}  # stripped_path → original_path
    if common_prefix and parent_id is not None:
        prefix_len = len(common_prefix) + 1  # +1 for trailing '/'
        tree_file_map: dict[str, bytes] = {}
        generic_stripped: dict[str, bytes] = {}
        for path, content in file_map.items():
            norm = path.replace('\\', '/')
            if norm.startswith(common_prefix + '/'):
                stripped = norm[prefix_len:]
            else:
                stripped = norm
            if _get_file_type(path) in ('md', 'html'):
                tree_file_map[stripped] = content
            else:
                generic_stripped[stripped] = content
            if stripped != norm:
                stripped_map[stripped] = norm
    else:
        tree_file_map = md_html_map
        generic_stripped = generic_map

    # ---- 第一阶段：处理 MD/HTML 文件（保留原有逻辑）----
    path_to_page: dict[str, PageRead] = {}

    # 当所有文件都在顶层（无子目录结构）时，统一用 generic 导入确保每个文件独立页面
    has_subdirs = any('/' in fp.replace('\\', '/') for fp in tree_file_map) if tree_file_map else False
    use_generic_for_all = not has_subdirs and len(generic_stripped) + len(tree_file_map) > 1

    if use_generic_for_all:
        # 将所有文件合并到 generic 导入
        all_generic = dict(generic_stripped)
        all_generic.update(tree_file_map)
        generic_pages = await _import_generic_files(
            session, workspace.id, all_generic, current_user.id,
            target_page, overwrite=overwrite,
        )
        generic_stripped = {}  # 已处理
        tree_file_map = {}  # 已处理
    elif tree_file_map:
        if md_count >= html_count:
            path_to_page = await _import_md_tree(
                session, workspace.id, tree_file_map, target_page, current_user.id,
            )
        else:
            path_to_page = await _import_html_tree(
                session, workspace.id, tree_file_map, current_user.id, target_page,
            )

    # ---- 处理通用文件（txt/xlsx/docx/pdf/图片/代码等）----
    generic_pages: list[PageRead] = []
    if generic_stripped:
        # 如果有公共前缀剥离了，通用文件需用 stripped 版本
        target_for_generic = target_page
        generic_pages = await _import_generic_files(
            session, workspace.id, generic_stripped, current_user.id,
            target_for_generic, overwrite=overwrite,
        )

    # ---- 路径映射补全：将 stripped 键映射回 original 键 ----
    # 例如 stripped="大数据.md" → original="大数据/大数据.md"
    # 这样页面内容中的 [text](大数据/大数据.md) 链接才能被匹配到
    extra_mapping: dict[str, PageRead] = {}
    for stripped_key, page in list(path_to_page.items()):
        # 尝试找到对应的 original 路径
        # 精确匹配
        if stripped_key in stripped_map:
            orig = stripped_map[stripped_key]
            extra_mapping[orig.lower()] = page
            extra_mapping[re.sub(r'\.(md|html|htm)$', '', orig.lower())] = page
        # 模糊匹配：前缀替换
        for s_path, o_path in stripped_map.items():
            if s_path.rstrip('/').lower() == stripped_key.rstrip('/'):
                extra_mapping[o_path.lower()] = page
                extra_mapping[re.sub(r'\.(md|html|htm)$', '', o_path.lower())] = page
                break
    path_to_page.update(extra_mapping)

    # 确保根页面在映射中
    await session.refresh(target_page)
    path_to_page[''] = PageRead.model_validate(target_page)
    path_to_page[target_page.title.lower()] = PageRead.model_validate(target_page)

    # ---- 第二阶段：修复所有受影响页面中的文件路径链接 ----
    # 收集所有页面 ID（去重）
    affected_page_ids: set[int] = {target_page.id}
    for p in path_to_page.values():
        affected_page_ids.add(p.id)

    # 修复每个页面的链接
    for pid in affected_page_ids:
        page = await session.get(Page, pid)
        if page:
            await _fix_page_links(session, page, path_to_page)

    # ---- 返回所有创建的页面 ----
    await session.refresh(target_page)
    created = [PageRead.model_validate(target_page)]
    seen_ids = {target_page.id}
    for p in path_to_page.values():
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            created.append(p)
    for p in generic_pages:
        if p.id not in seen_ids:
            seen_ids.add(p.id)
            created.append(p)

    return created


class FilePathRequest(BaseModel):
    file_path: str

@router.post("/upload-local-file", summary="上传本地文件(file://路径)")
async def upload_local_file(
    body: FilePathRequest,
    current_user: User = Depends(get_current_user),
):
    """接收本地文件路径，读取并上传到静态目录，返回访问URL"""
    from pydantic import BaseModel as PydBaseModel
    file_path = body.file_path
    # 规范化路径
    if file_path.startswith('/'):
        file_path = file_path[1:]
    path_obj = Path(file_path)
    if not path_obj.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    if not path_obj.is_file():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="路径不是文件")
    # 读取并上传
    content = path_obj.read_bytes()
    user_upload_dir = STATIC_UPLOAD_ROOT / str(current_user.id)
    user_upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex[:8]}/{path_obj.name}"
    dest = user_upload_dir / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    url = f"/static/uploads/{current_user.id}/{safe_name}"
    return {"url": url, "filename": path_obj.name}


class UrlRequest(BaseModel):
    url: str

@router.post("/fetch-page-title", summary="获取网页标题")
async def fetch_page_title(body: UrlRequest):
    """获取指定URL的网页标题"""
    import re as re_mod
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(body.url)
            html = resp.text[:10000]
            title_match = re_mod.search(r'<title[^>]*>([^<]+)</title>', html, re_mod.IGNORECASE)
            title = title_match.group(1).strip() if title_match else body.url
            return {"title": title}
    except ImportError:
        return {"title": body.url}
    except Exception:
        return {"title": body.url}
