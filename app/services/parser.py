"""文档 → Block(dict) 解析服务

支持纯文本类（md/html/txt/code/*.py 等）；PDF/Office/XMind 等尽量提取文本，
解析器未安装时降级为“附件引用段落”，不影响文件状态机推进。
"""
import os
import re
from typing import Any, Optional

# 扩展名 → 解析器类型
FILE_TYPE_MAP: dict[str, str] = {
    ".md": "md", ".markdown": "md",
    ".html": "html", ".htm": "html",
    ".txt": "txt", ".csv": "txt", ".log": "txt",
    ".py": "code", ".js": "code", ".jsx": "code", ".ts": "code", ".tsx": "code",
    ".css": "code", ".scss": "code", ".less": "code",
    ".java": "code", ".c": "code", ".cpp": "code", ".h": "code", ".hpp": "code",
    ".go": "code", ".rs": "code", ".rb": "code", ".php": "code",
    ".r": "code", ".swift": "code", ".kt": "code", ".scala": "code",
    ".lua": "code", ".dart": "code", ".cs": "code",
    ".sql": "code", ".sh": "code", ".bash": "code", ".zsh": "code",
    ".json": "code", ".yaml": "code", ".yml": "code", ".toml": "code", ".xml": "code",
    ".ini": "code", ".cfg": "code", ".conf": "code",
    ".bat": "code", ".ps1": "code",
    ".pdf": "pdf",
    ".docx": "docx", ".doc": "docx",
    ".xlsx": "xlsx", ".xls": "xlsx",
    ".pptx": "ppt", ".ppt": "ppt",
    ".xmind": "xmind",
}

CODE_LANG_MAP: dict[str, str] = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".css": "css", ".html": "html", ".json": "json", ".sql": "sql",
    ".sh": "bash", ".bat": "bash", ".ps1": "powershell", ".md": "markdown",
}


def get_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return FILE_TYPE_MAP.get(ext, "unknown")


def parse_document(
    filename: str, data: bytes, content_url: str = ""
) -> list[dict[str, Any]]:
    """解析文件内容为 block 字典列表（content 结构兼容前端 BlockRenderer）。

    content_url：文件经存储层后的访问地址（降级附件引用时使用）。
    """
    file_type = get_file_type(filename)
    name = os.path.basename(filename)

    try:
        text = _decode(data)
    except Exception:  # noqa: BLE001
        text = ""

    if file_type == "md":
        return _parse_md(text)
    if file_type == "html":
        return _parse_html(text)
    if file_type in ("txt",):
        return _simple_blocks("paragraph", [text]) if text.strip() else []
    if file_type == "code":
        return _simple_blocks("code", [{
            "language": CODE_LANG_MAP.get(os.path.splitext(name)[1].lower(), "text"),
            "code": text,
        }])
    if file_type == "pdf":
        blocks = _parse_pdf(data, content_url)
        if blocks is not None:
            return blocks
        return _attachment_block(name, content_url)
    if file_type == "docx":
        blocks = _parse_docx(data, content_url)
        if blocks is not None:
            return blocks
        return _attachment_block(name, content_url)
    if file_type == "xlsx":
        blocks = _parse_xlsx(data, content_url)
        if blocks is not None:
            return blocks
        return _attachment_block(name, content_url)
    if file_type == "ppt":
        blocks = _parse_pptx(data, content_url)
        if blocks is not None:
            return blocks
        return _attachment_block(name, content_url)
    # 其余（含 xmind/图片等）降级为附件引用
    return _attachment_block(name, content_url)


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _simple_blocks(block_type: str, payloads: list[Any]) -> list[dict[str, Any]]:
    blocks = []
    for payload in payloads:
        content = payload if isinstance(payload, dict) else {"text": payload}
        blocks.append({"type": block_type, "content": content})
    return blocks


def _attachment_block(filename: str, content_url: str) -> list[dict[str, Any]]:
    if not content_url:
        return [{"type": "paragraph", "content": {"text": f"📎 {filename}"}}]
    return [{"type": "paragraph", "content": {"text": f"📎 [{filename}]({content_url})"}}]


# ---------- Markdown ----------

_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:-]+\|[\s|:-]+$")
_IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)")
_TASK_RE = re.compile(r"^-\s+\[([ x])\]\s+(.+)")
_LIST_RE = re.compile(r"^[-*+]\s(.+)")


def _parse_md(md_text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lines = md_text.strip().split("\n")
    code_buffer: list[str] = []
    code_lang = ""
    in_code = False
    i = 0
    n = len(lines)

    def flush_code():
        if code_buffer:
            blocks.append({
                "type": "code",
                "content": {"language": code_lang or "text", "code": "\n".join(code_buffer)},
            })
            code_buffer.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
                code_lang = ""
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

        # 表格
        m = _TABLE_ROW_RE.match(stripped)
        if m and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            headers = [c.strip() for c in m.group(1).split("|")]
            rows: list[list[str]] = []
            i += 2
            while i < n:
                row = _TABLE_ROW_RE.match(lines[i].strip())
                if not row:
                    break
                cells = [c.strip() for c in row.group(1).split("|")]
                while len(cells) < len(headers):
                    cells.append("")
                rows.append(cells[: len(headers)])
                i += 1
            blocks.append({"type": "table", "content": {"headers": headers, "rows": rows}})
            continue

        img = _IMG_RE.match(stripped)
        if img:
            blocks.append({"type": "image", "content": {"url": img.group(2), "alt": img.group(1)}})
            i += 1
            continue

        h = _HEADING_RE.match(stripped)
        if h:
            blocks.append({
                "type": "heading",
                "content": {"level": len(h.group(1)), "text": h.group(2)},
            })
            i += 1
            continue

        if stripped.startswith("> "):
            blocks.append({"type": "quote", "content": {"text": stripped[2:]}})
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", stripped):
            blocks.append({"type": "divider", "content": {}})
            i += 1
            continue

        task = _TASK_RE.match(stripped)
        if task:
            blocks.append({
                "type": "list",
                "content": {
                    "ordered": False, "task": True,
                    "items": [{"text": task.group(2), "checked": task.group(1) == "x"}],
                },
            })
            i += 1
            continue

        lst = _LIST_RE.match(stripped)
        if lst:
            blocks.append({"type": "list", "content": {"ordered": False, "text": lst.group(1)}})
            i += 1
            continue

        blocks.append({"type": "paragraph", "content": {"text": stripped}})
        i += 1

    flush_code()
    return blocks


# ---------- HTML（轻量，取文本/标题/代码结构） ----------

def _parse_html(html_text: str) -> list[dict[str, Any]]:
    from html.parser import HTMLParser

    blocks: list[dict[str, Any]] = []

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.heading_level = 0
            self.buf: list[str] = []
            self.in_pre = False

        def handle_starttag(self, tag, attrs):
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self._flush()
                self.heading_level = int(tag[1])
            elif tag in ("pre", "code"):
                self.in_pre = True
            elif tag in ("p", "li", "div", "br", "tr", "blockquote"):
                pass

        def handle_endtag(self, tag):
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                text = self._drain_text()
                if text:
                    blocks.append({
                        "type": "heading",
                        "content": {"level": self.heading_level, "text": text},
                    })
                self.heading_level = 0
            elif tag in ("pre", "code") and self.in_pre:
                text = self._drain_text()
                if text:
                    blocks.append({
                        "type": "code",
                        "content": {"language": "text", "code": text},
                    })
                self.in_pre = False
            elif tag in ("p", "li", "div", "br"):
                text = self._drain_text()
                if text:
                    blocks.append({"type": "paragraph", "content": {"text": text}})
            elif tag == "blockquote":
                text = self._drain_text()
                if text:
                    blocks.append({"type": "quote", "content": {"text": text}})

        def handle_data(self, data):
            self.buf.append(data)

        def _flush(self):
            self._drain_text()

        def _drain_text(self) -> str:
            text = "".join(self.buf).strip()
            self.buf.clear()
            return text

    p = _P()
    p.feed(html_text)
    text = p._drain_text()
    if text and not blocks:
        blocks.append({"type": "paragraph", "content": {"text": text}})
    if not blocks:
        blocks.append({"type": "paragraph", "content": {"text": "（空内容）"}})
    return blocks


# ---------- PDF / Office（可选依赖） ----------

def _parse_pdf(data: bytes, content_url: str) -> Optional[list[dict[str, Any]]]:
    try:
        from io import BytesIO

        from PyPDF2 import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(BytesIO(data))
        blocks: list[dict[str, Any]] = []
        for page_num, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if not text:
                continue
            blocks.append({
                "type": "heading",
                "content": {"level": 3, "text": f"第 {page_num + 1} 页", "page": page_num + 1},
            })
            for para in text.split("\n\n"):
                para = para.strip()
                if para:
                    blocks.append({"type": "paragraph", "content": {"text": para}})
        return blocks or None
    except Exception:  # noqa: BLE001
        return None


def _parse_docx(data: bytes, content_url: str) -> Optional[list[dict[str, Any]]]:
    try:
        from io import BytesIO

        from docx import Document
    except ImportError:
        return None
    try:
        doc = Document(BytesIO(data))
        blocks: list[dict[str, Any]] = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
            style_name = para.style.name if para.style and para.style.name else ""
            if "Heading" in style_name:
                level_str = style_name.replace("Heading", "").strip()
                try:
                    level = int(level_str) if level_str else 1
                except ValueError:
                    level = 1
                blocks.append({"type": "heading", "content": {"level": min(level, 6), "text": text}})
            else:
                blocks.append({"type": "paragraph", "content": {"text": text}})
        return blocks or None
    except Exception:  # noqa: BLE001
        return None


def _parse_xlsx(data: bytes, content_url: str) -> Optional[list[dict[str, Any]]]:
    try:
        from io import BytesIO

        import openpyxl
    except ImportError:
        return None
    try:
        wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        blocks: list[dict[str, Any]] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(max_row=min(ws.max_row, 300), values_only=True))
            if not rows:
                continue
            headers = [str(c) if c is not None else "" for c in rows[0]]
            data_rows = [
                [str(c) if c is not None else "" for c in row] for row in rows[1:]
            ]
            blocks.append({"type": "heading", "content": {"level": 2, "text": f"工作表: {sheet_name}"}})
            blocks.append({"type": "table", "content": {"headers": headers, "rows": data_rows}})
        wb.close()
        return blocks or None
    except Exception:  # noqa: BLE001
        return None


def _parse_pptx(data: bytes, content_url: str) -> Optional[list[dict[str, Any]]]:
    try:
        from io import BytesIO

        from pptx import Presentation
    except ImportError:
        return None
    try:
        prs = Presentation(BytesIO(data))
        blocks: list[dict[str, Any]] = []
        for slide_num, slide in enumerate(prs.slides):
            texts: list[str] = []
            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            texts.append(t)
            if texts:
                blocks.append({
                    "type": "heading",
                    "content": {"level": 3, "text": f"幻灯片 {slide_num + 1}"},
                })
                for t in texts:
                    blocks.append({"type": "paragraph", "content": {"text": t}})
        return blocks or None
    except Exception:  # noqa: BLE001
        return None
