"""页面 CRUD 路由"""
import os
import re
import uuid
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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
    page = Page(workspace_id=workspace.id, **body.model_dump())
    session.add(page)
    await session.commit()
    await session.refresh(page)

    # 新增页面默认添加一个一级标题 block
    h1_text = page.title if page.title not in ('无标题页面', '无标题子页面') else ''
    block = Block(
        page_id=page.id, type='heading',
        content={'level': 1, 'text': h1_text},
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
    """检查页面是否只有占位 block（默认 H1 空标题）"""
    if len(existing_blocks) == 1:
        b = existing_blocks[0]
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
        k_basename = os.path.basename(k)
        k_no_ext = re.sub(r'\.(md|html|htm)$', '', k_basename)
        if k_no_ext == no_ext_base:
            return v

    # 策略4：路径最后两段匹配（目录/文件名）
    parts = clean.strip('/').split('/')
    if len(parts) >= 2:
        last_two = '/'.join(parts[-2:])
        for k, v in path_to_page.items():
            if k.endswith(last_two):
                return v
            k_no_ext = re.sub(r'\.(md|html|htm)$', '', k)
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


def _parse_md_to_blocks(md_text: str, page_id: int, start_order: int) -> list[Block]:
    """简易 Markdown 解析为 Block 列表"""
    blocks: list[Block] = []
    order = start_order
    lines = md_text.strip().split('\n')
    code_buffer: list[str] = []
    code_lang = ''
    in_code = False

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

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code:
                flush_code()
                in_code = False
                code_lang = ''
            else:
                code_lang = stripped[3:].strip()
                in_code = True
            continue
        if in_code:
            code_buffer.append(line)
            continue
        if not stripped:
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
            continue
        h_match = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if h_match:
            blocks.append(Block(
                page_id=page_id, type='heading',
                content={'level': len(h_match.group(1)), 'text': h_match.group(2)},
                sort_order=order,
            ))
            order += 1
            continue
        if stripped.startswith('> '):
            blocks.append(Block(
                page_id=page_id, type='quote',
                content={'text': stripped[2:]},
                sort_order=order,
            ))
            order += 1
            continue
        if re.match(r'^[-*_]{3,}$', stripped):
            blocks.append(Block(
                page_id=page_id, type='divider',
                content={},
                sort_order=order,
            ))
            order += 1
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
            continue
        if re.match(r'^[-*+]\s', stripped):
            blocks.append(Block(
                page_id=page_id, type='list',
                content={'ordered': False, 'text': re.sub(r'^[-*+]\s', '', stripped)},
                sort_order=order,
            ))
            order += 1
            continue
        blocks.append(Block(
            page_id=page_id, type='paragraph',
            content={'text': stripped},
            sort_order=order,
        ))
        order += 1

    flush_code()
    return blocks


# ---- HTML 解析 ----


def _parse_html_to_blocks_with_assets(
    html_text: str, page_id: int, start_order: int,
    file_map: dict[str, bytes], user_id: int,
) -> tuple[list[Block], str]:
    """解析HTML为Block，同时处理静态资源上传，返回(blocks, 修复后的HTML)"""
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
        content = block.content or {}
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

        if changed:
            block.content = content
            session.add(block)
            modified = True

    if modified:
        await session.commit()


# ---- 导入端点 ----


@router.post("/import", response_model=list[PageRead], summary="导入目录/文件到页面树")
async def import_pages(
    files: list[UploadFile] = File(...),
    parent_id: Optional[int] = Form(None),
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
        )
        session.add(target_page)
        await session.commit()
        await session.refresh(target_page)
        is_new = True

    # ---- 检测格式 ----
    md_count = sum(1 for p in file_map if p.lower().endswith('.md'))
    html_count = sum(1 for p in file_map if p.lower().endswith(('.html', '.htm')))

    # ---- 检测并剥离公共路径前缀 ----
    # 当用户通过 webkitdirectory 选择目录时，所有文件共享一个顶层目录名
    # 例如 "大数据/大数据.md", "大数据/Spark/Spark.md" → 剥离前缀 "大数据/"
    # 这样顶层 .md 文件就能正确注入 target_page 而非创建子页面
    common_prefix = _detect_common_prefix(list(file_map.keys()))
    stripped_map: dict[str, str] = {}  # stripped_path → original_path
    if common_prefix and parent_id is not None:
        prefix_len = len(common_prefix) + 1  # +1 for trailing '/'
        tree_file_map: dict[str, bytes] = {}
        for path, content in file_map.items():
            norm = path.replace('\\', '/')
            if norm.startswith(common_prefix + '/'):
                stripped = norm[prefix_len:]
            else:
                stripped = norm
            tree_file_map[stripped] = content
            # 记录映射：stripped → original（用于后续 path_to_page 键补全）
            if stripped != norm:
                stripped_map[stripped] = norm
    else:
        tree_file_map = file_map

    # ---- 第一阶段：递归导入页面树，收集完整路径映射 ----
    path_to_page: dict[str, PageRead] = {}

    if md_count >= html_count:
        path_to_page = await _import_md_tree(
            session, workspace.id, tree_file_map, target_page, current_user.id,
        )
    else:
        path_to_page = await _import_html_tree(
            session, workspace.id, tree_file_map, current_user.id, target_page,
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

    return created
