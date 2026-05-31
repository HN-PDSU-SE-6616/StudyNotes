# app/utils/markdown.py
import os
import re

import aiofiles
import markdown
from async_lru import alru_cache
from markdown.extensions import fenced_code, tables, toc

from app.models import Note

ASSET_PATTERN = re.compile(r'(src|href|url)\s*=\s*["\'](?!http|/|data:)([^"\']+)["\']')


def fix_html_assets(html_content: str, note_relative_dir: str) -> str:
    """
    智能修复 HTML 中的所有相对路径
    例如: href="css/style.css" -> href="/note_assets/目录/css/style.css"
    """
    # 确保路径是 / 分隔
    note_dir = note_relative_dir.replace("\\", "/")

    def replacer(match):
        attr = match.group(1)  # src / href / url
        path = match.group(2)  # css/style.css
        # 拼接后的绝对路径：/note_assets/笔记目录/css/style.css
        return f'{attr}="/note_assets/{note_dir}/{path}"'

    return ASSET_PATTERN.sub(replacer, html_content)


# @alru_cache(maxsize=128) 缓存文件读取结果，极大减少频繁IO
@alru_cache(maxsize=128)
async def read_content_from_disk(file_path: str, relative_dir: str) -> str:
    """读取 HTML，并动态修复媒体路径后返回"""
    async with aiofiles.open(file_path, mode='r', encoding='utf-8') as f:
        content = await f.read()

    # 修复图片路径
    return fix_html_assets(content, relative_dir)


def md_to_html(md_content: str) -> str:
    """
    将 Markdown 文本转换为 HTML
    支持：代码块高亮、表格、目录
    """
    extensions = [
        "fenced_code",  # ```代码块
        "tables",  # 表格
        "toc",  # 目录 [TOC]
        "nl2br",  # 换行转 <br>
        "codehilite",  # 代码高亮
    ]
    return markdown.markdown(md_content, extensions=extensions)


async def get_note_content(note: "Note") -> str:
    if note.content_type == "file" and note.content_path:
        # 获取文件所在的相对目录
        relative_dir = os.path.dirname(note.content_path)
        full_path = os.path.join("data", note.content_path)
        return await read_content_from_disk(full_path, relative_dir)
    return note.content_db or ""
