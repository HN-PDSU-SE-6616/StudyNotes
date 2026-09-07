"""文档 → Block(dict) 解析服务

Block 列表协议（与前端 BlockRenderer 对齐）：
- list 块 content：
    {ordered?: bool, task?: bool, start?: int,
     items?: [{text, checked?, indent?}], text?: str(兼容旧数据)}
- 相邻同型的列表（有序/无序/任务）合并为一个 list 块的多行 items，
  有序从 start ?? 1 连续编号；任务项 checked 记录勾选状态；
  嵌套列表用 item.indent（0 起）表达层级缩进。

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
    filename: str,
    data: bytes,
    content_url: str = "",
    rel_url_map: Optional[dict[str, str]] = None,
) -> list[dict[str, Any]]:
    """解析文件内容为 block 字典列表（content 结构兼容前端 BlockRenderer）。

    rel_url_map：{规范化相对路径: 可访问 URL}，用于把 md 图片相对路径 /
    html 相对资源改写为已上传资源的访问地址；未命中保留原样。
    """
    file_type = get_file_type(filename)
    name = os.path.basename(filename)

    try:
        text = _decode(data)
    except Exception:  # noqa: BLE001
        text = ""

    if file_type == "md":
        return _parse_md(text, rel_url_map=rel_url_map)
    if file_type == "html":
        return _parse_html(text, rel_url_map=rel_url_map)
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
            return _normalize_blocks(blocks)
        return _attachment_block(name, content_url)
    if file_type == "docx":
        blocks = _parse_docx(data, content_url)
        if blocks is not None:
            return _normalize_blocks(blocks)
        return _attachment_block(name, content_url)
    if file_type == "xlsx":
        blocks = _parse_xlsx(data, content_url)
        if blocks is not None:
            return _normalize_blocks(blocks)
        return _attachment_block(name, content_url)
    if file_type == "ppt":
        blocks = _parse_pptx(data, content_url)
        if blocks is not None:
            return _normalize_blocks(blocks)
        return _attachment_block(name, content_url)
    if file_type == "xmind":
        blocks = _parse_xmind(data, content_url)
        if blocks is not None:
            return _normalize_blocks(blocks)
        return _attachment_block(name, content_url)
    return _attachment_block(name, content_url)


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "big5", "utf-16"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _norm_rel(path: str) -> str:
    norm = path.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return re.sub(r"/+", "/", norm).strip("/").lower()


def _rewrite_url(url: str, rel_url_map: Optional[dict[str, str]]) -> str:
    """若相对路径命中资源映射则替换为访问 URL；否则原样返回"""
    if not rel_url_map or not url or re.match(r"^(https?://|data:|/|#)", url, re.I):
        return url
    key = _norm_rel(url)
    return rel_url_map.get(key) or url


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


def _normalize_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """通用后处理：把内容中的非标准 list（text 单行）规整为规范 items；
    并合并相邻同型 list 块（来自 office/pdf 等解析器的冗余行）"""
    out: list[dict[str, Any]] = []

    def append(b: dict[str, Any]) -> None:
        if b.get("type") == "list":
            c = dict(b.get("content") or {})
            items: list[dict[str, Any]] = []
            for raw in c.get("items") or []:
                if isinstance(raw, dict):
                    items.append({"text": str(raw.get("text") or ""),
                                  "checked": bool(raw.get("checked")),
                                  "indent": int(raw.get("indent") or 0)})
                else:
                    items.append({"text": str(raw), "checked": False, "indent": 0})
            t = c.get("text")
            if isinstance(t, str) and t.strip() and not items:
                items.append({"text": t.strip(), "checked": False, "indent": 0})
            if not items:
                return
            # 与上一个同为同型 list 块时合并 items
            if out and out[-1].get("type") == "list":
                prev_c = out[-1].get("content") or {}
                if prev_c.get("ordered") == c.get("ordered") and bool(prev_c.get("task")) == bool(c.get("task")):
                    prev_c.setdefault("items", []).extend(items)
                    return
            out.append({"type": "list", "content": {
                "ordered": bool(c.get("ordered")),
                "task": bool(c.get("task")),
                "start": int(c.get("start") or 1) if c.get("ordered") else 1,
                "items": items,
            }})
            return
        out.append(b)

    for b in blocks:
        append(b)
    return out


def _list_item(text: str, checked: bool = False, indent: int = 0) -> dict[str, Any]:
    return {"text": text.strip(), "checked": checked, "indent": indent}


def _indent_of(line: str, marker_len: int) -> int:
    """前导空白 → 缩进层级（约 2 空格 = 1 级）"""
    lead = len(line) - len(line.lstrip(" \t"))
    return max(0, lead // 2)


# ==================== Markdown ====================

_TOC_HEADING_RE = re.compile(
    r"^\s*#{1,3}\s*(目录|目錄|Table\s*of\s*Contents|Contents)\s*$", re.IGNORECASE
)
_TOC_ITEM_RE = re.compile(r"^\s*[-*+]\s+\[[^\]]+\]\(#[^)]+\)\s*$")


def _strip_md_toc(md_text: str) -> str:
    """去除 VSCode 风格 Markdown 自动目录（目录标题 + 仅含 [text](#anchor) 的行）"""
    lines = md_text.split("\n")
    n = len(lines)
    toc_start = -1
    for i in range(n):
        stripped = lines[i].strip()
        if _TOC_HEADING_RE.match(stripped):
            toc_start = i
            break
        if stripped and not re.match(r"^#{1,6}\s", stripped) and not _TOC_ITEM_RE.match(stripped):
            break
    if toc_start < 0:
        return md_text
    i = toc_start + 1
    toc_item_count = 0
    while i < n:
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if _TOC_ITEM_RE.match(stripped):
            toc_item_count += 1
            i += 1
            continue
        break
    if toc_item_count < 2:
        return md_text
    # 跳到目录结束后的首个空行，保留其后的正文
    while i < n and not lines[i].strip():
        i += 1
    result = lines[:toc_start]
    while result and not result[-1].strip():
        result.pop()
    result.append("")
    result.extend(lines[i:])
    return "\n".join(result)


_TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|[\s:-]+\|[\s|:-]+$")
_IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)")
_TASK_RE = re.compile(r"^(\s*)[-*+]\s+\[([ xX])\]\s+(.+)$")
_UL_RE = re.compile(r"^(\s*)[-*+]\s+(.+)$")
_OL_RE = re.compile(r"^(\s*)(\d+)[.、]\s+(.+)$")


def _unescape_md_table_cell(cell: str) -> str:
    """处理 Markdown 表格单元格中的反斜杠转义序列"""
    cell = cell.replace("\\\\", "\x00")
    for esc, ch in (("\\|", "|"), ("\\*", "*"), ("\\_", "_"), ("\\#", "#"),
                    ("\\-", "-"), ("\\`", "`"), ("\\~", "~")):
        cell = cell.replace(esc, ch)
    return cell.replace("\x00", "\\")


def _split_table_cells(cell_part: str) -> list[str]:
    """按 | 拆分单元格，但忽略 \| 转义（先占位再拆再还原）"""
    parts = []
    buf = []
    escaped = False
    for ch in cell_part:
        if escaped:
            buf.append(ch)
            escaped = False
        elif ch == "\\":
            buf.append(ch)
            escaped = True
        elif ch == "|":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return parts


def _parse_md(md_text: str, rel_url_map: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    md_text = _strip_md_toc(md_text)
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

    def flush_list():
        nonlocal group
        if group["items"]:
            content: dict[str, Any] = {"items": group["items"]}
            if group["kind"] == "task":
                content["ordered"] = False
                content["task"] = True
            elif group["kind"] == "ol":
                content["ordered"] = True
                content["start"] = group["start"]
            else:
                content["ordered"] = False
            blocks.append({"type": "list", "content": content})
            group = {"kind": None, "items": [], "start": 1}

    group: dict[str, Any] = {"kind": None, "items": [], "start": 1}

    while i < n:
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            if group["kind"]:
                flush_list()
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
            if group["kind"]:
                flush_list()
            i += 1
            continue

        # 列表（任务/有序/无序）——同型才合并，异型立即断组
        task_m = _TASK_RE.match(line)
        if task_m:
            if group["kind"] != "task":
                flush_list()
            group["kind"] = "task"
            group["items"].append(_list_item(task_m.group(3),
                                             checked=task_m.group(2).lower() == "x",
                                             indent=_indent_of(line, len(task_m.group(1)) + len(task_m.group(2)) + 4)))
            i += 1
            continue

        ul_m = _UL_RE.match(line)
        if ul_m:
            if group["kind"] != "ul":
                flush_list()
            group["kind"] = "ul"
            group["items"].append(_list_item(ul_m.group(2), indent=_indent_of(line, len(ul_m.group(1)) + 2)))
            i += 1
            continue

        ol_m = _OL_RE.match(line)
        if ol_m:
            if group["kind"] != "ol":
                flush_list()
                group["start"] = int(ol_m.group(2))
            group["kind"] = "ol"
            group["items"].append(_list_item(ol_m.group(3), indent=_indent_of(line, len(ol_m.group(1)) + len(ol_m.group(2)) + 1)))
            i += 1
            continue
        if group["kind"]:
            flush_list()

        # 表格
        m = _TABLE_ROW_RE.match(stripped)
        if m and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1].strip()):
            headers = [_unescape_md_table_cell(c.strip()) for c in _split_table_cells(m.group(1))]
            rows: list[list[str]] = []
            i += 2
            while i < n:
                row = _TABLE_ROW_RE.match(lines[i].strip())
                if not row:
                    break
                cells = [_unescape_md_table_cell(c.strip()) for c in _split_table_cells(row.group(1))]
                while len(cells) < len(headers):
                    cells.append("")
                rows.append(cells[: len(headers)])
                i += 1
            blocks.append({"type": "table", "content": {"headers": headers, "rows": rows}})
            continue

        img = _IMG_RE.match(stripped)
        if img:
            blocks.append({
                "type": "image",
                "content": {"url": _rewrite_url(img.group(2), rel_url_map), "alt": img.group(1)},
            })
            i += 1
            continue

        h = _HEADING_RE.match(stripped)
        if h:
            blocks.append({
                "type": "heading",
                "content": {"level": len(h.group(1)), "text": h.group(2).strip()},
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

        blocks.append({"type": "paragraph", "content": {"text": stripped}})
        i += 1

    if group["kind"]:
        flush_list()
    flush_code()
    return blocks


# ==================== HTML（结构化：表格/列表嵌套/引用/代码/图片） ====================

_HTML_STATIC_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _parse_html(html_text: str, rel_url_map: Optional[dict[str, str]] = None) -> list[dict[str, Any]]:
    from html.parser import HTMLParser

    blocks: list[dict[str, Any]] = []

    class _SimpleParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            # 表格状态
            self.in_table = False
            self.in_thead = False
            self.in_tbody = False
            self.table_headers: list[str] = []
            self.table_rows: list[list[str]] = []
            self.current_row: list[str] = []
            self.in_th = False
            self.in_td = False
            self.current_cell = ""
            # 文本/上下文
            self.current_text: list[str] = []
            self.current_type = "paragraph"  # paragraph | quote | code
            self.heading_level = 0
            self.in_pre = False
            # 列表状态：栈 {kind: ul/ol}
            self.list_stack: list[str] = []
            self.in_li = False
            self.li_parts: list[str] = []
            self.li_children_indent: Optional[int] = None
            self.li_indent = 0
            self.table_warnings: list[str] = []

        # ---- 表格 ----
        def _flush_current_row(self):
            if not self.current_row:
                return
            if self.in_thead and not self.table_headers:
                self.table_headers = list(self.current_row)
            else:
                self.table_rows.append(list(self.current_row))
            self.current_row = []

        def _flush_table(self):
            headers = self.table_headers or []
            rows = self.table_rows
            if self.table_warnings:
                blocks.append({
                    "type": "callout",
                    "content": {"type": "warning",
                                "text": "表格导入警告：" + "; ".join(self.table_warnings)},
                })
                self.table_warnings = []
            if headers or rows:
                blocks.append({"type": "table", "content": {"headers": headers, "rows": rows}})
            # 复位状态，避免未闭合/重复 endtag 造成二次输出
            self.table_headers = []
            self.table_rows = []
            self.current_row = []

        # ---- 通用 ----
        def _flush_text_block(self):
            text = "".join(self.current_text).strip()
            self.current_text = []
            if not text:
                return
            if self.current_type == "quote":
                blocks.append({"type": "quote", "content": {"text": text}})
            elif self.current_type == "code":
                blocks.append({"type": "code", "content": {"language": "text", "code": text}})
            else:
                blocks.append({"type": "paragraph", "content": {"text": text}})

        def _flush_li(self):
            """结束一个 li：文本入当前列表上下文（成为一条待定 item）"""
            if self.in_li:
                text = "".join(self.li_parts).strip()
                self.li_parts = []
                self.in_li = False
                if text:
                    indent = len(self.list_stack) - 1
                    blocks.append({
                        "_li": True,
                        "kind": self.list_stack[-1] if self.list_stack else "ul",
                        "text": text,
                        "indent": indent,
                    })

        def _append_text(self, data: str):
            if self.in_th or self.in_td:
                self.current_cell += data
            elif self.in_li:
                self.li_parts.append(data)
            else:
                # pre/code 内的文本同样收集，由 endtag 按当前上下文落块
                self.current_text.append(data)

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            if tag == "table":
                self._flush_li()
                self._flush_text_block()
                self.in_table = True
                self.in_thead = False
                self.in_tbody = False
                self.table_headers = []
                self.table_rows = []
                self.current_row = []
                return
            if self.in_table:
                if tag == "thead":
                    self.in_thead = True
                elif tag == "tbody":
                    self.in_tbody = True
                elif tag == "tr":
                    self.current_row = []
                elif tag in ("th", "td"):
                    if tag == "th":
                        self.in_th = True
                    else:
                        self.in_td = True
                    self.current_cell = ""
                    if attrs_dict.get("colspan") and int(attrs_dict["colspan"]) > 1:
                        self.table_warnings.append(f"cell with colspan={attrs_dict['colspan']} will be split")
                    if attrs_dict.get("rowspan") and int(attrs_dict["rowspan"]) > 1:
                        self.table_warnings.append(f"cell with rowspan={attrs_dict['rowspan']} may lose merge info")
                return
            if tag in ("ul", "ol"):
                self._flush_li()
                self.list_stack.append("ol" if tag == "ol" else "ul")
                return
            if tag == "li":
                self._flush_li()
                self.in_li = True
                self.li_parts = []
                self.li_indent = max(0, len(self.list_stack) - 1)
                return
            if tag in _HTML_STATIC_TAGS:
                self._flush_li()
                self._flush_text_block()
                self.heading_level = int(tag[1])
            elif tag == "blockquote":
                self._flush_li()
                self._flush_text_block()
                self.current_type = "quote"
            elif tag in ("pre",):
                self._flush_li()
                self._flush_text_block()
                self.in_pre = True
                self.current_type = "code"
            elif tag == "img":
                src = attrs_dict.get("src") or ""
                alt = attrs_dict.get("alt") or ""
                if src:
                    self._flush_li()
                    self._flush_text_block()
                    blocks.append({
                        "type": "image",
                        "content": {"url": _rewrite_url(src, rel_url_map), "alt": alt},
                    })
            elif tag == "hr":
                self._flush_li()
                self._flush_text_block()
                blocks.append({"type": "divider", "content": {}})

        def handle_endtag(self, tag):
            if tag == "table":
                self._flush_current_row()
                self._flush_table()
                self.in_table = False
                self.in_thead = False
                self.in_tbody = False
                self.in_th = False
                self.in_td = False
                return
            if self.in_table:
                if tag == "thead":
                    self.in_thead = False
                elif tag == "tbody":
                    self.in_tbody = False
                elif tag == "tr":
                    self._flush_current_row()
                elif tag == "th":
                    self.in_th = False
                    self.current_row.append(self.current_cell.strip())
                elif tag == "td":
                    self.in_td = False
                    self.current_row.append(self.current_cell.strip())
                return
            if tag in ("ul", "ol"):
                self._flush_li()
                if self.list_stack:
                    self.list_stack.pop()
                return
            if tag == "li":
                self._flush_li()
                return
            if tag in _HTML_STATIC_TAGS:
                text = "".join(self.current_text).strip()
                self.current_text = []
                if text:
                    blocks.append({
                        "type": "heading",
                        "content": {"level": self.heading_level, "text": text},
                    })
                self.heading_level = 0
            elif tag == "blockquote":
                self._flush_text_block()
                self.current_type = "paragraph"
            elif tag == "pre":
                text = "".join(self.current_text).strip()
                self.current_text = []
                self.in_pre = False
                if text:
                    blocks.append({"type": "code", "content": {"language": "text", "code": text}})
                self.current_type = "paragraph"
            elif tag in ("p", "div", "br"):
                self._flush_text_block()
            elif tag == "code" and self.in_pre:
                # <pre><code>…</code></pre>：code 结束由 pre 结束统一落块，无需处理
                pass

        def handle_data(self, data):
            self._append_text(data)

    parser = _SimpleParser()
    try:
        parser.feed(html_text)
    except Exception:  # noqa: BLE001
        blocks = [{"type": "paragraph", "content": {"text": html_text[:5000]}}]
    parser._flush_li()
    parser._flush_text_block()
    if parser.table_headers or parser.table_rows:
        parser._flush_table()

    if not blocks:
        blocks.append({"type": "paragraph", "content": {"text": "（空内容）"}})
    return _merge_html_li_blocks(blocks)


def _merge_html_li_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 html 解析出的临时 '_li' 标记合并为规范 list 块：
    连续同型（ul/ol）且同缩进深度的项合并为一个块，多行 items。"""
    out: list[dict[str, Any]] = []
    pending: dict[str, Any] | None = None  # 当前收集中 list 块

    def flush_pending():
        nonlocal pending
        if pending:
            out.append(pending)
            pending = None

    for b in blocks:
        if "_li" in b:
            kind = b["kind"]
            ordered = kind == "ol"
            item = _list_item(b["text"], indent=b["indent"])
            # 同型（ul/ol）连续项并入同一块；嵌套深度体现在 item.indent，由前端缩进/连号渲染
            if pending and bool(pending["content"].get("ordered")) == ordered:
                pending["content"].setdefault("items", []).append(item)
                continue
            flush_pending()
            pending = {
                "type": "list",
                "content": {
                    "ordered": ordered,
                    "start": 1,
                    "items": [item],
                },
            }
            continue
        flush_pending()
        out.append(b)

    flush_pending()
    return out


# ==================== PDF / Office / XMind（可选依赖） ====================

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


def _parse_xmind(data: bytes, content_url: str) -> Optional[list[dict[str, Any]]]:
    try:
        import json as _json
        from io import BytesIO
        import zipfile

        zf = zipfile.ZipFile(BytesIO(data))
        name = "content.json" if "content.json" in zf.namelist() else None
        if name is None:
            return None
        raw = zf.read(name)
        payload = _json.loads(raw.decode("utf-8", errors="replace"))
        blocks: list[dict[str, Any]] = []
        if isinstance(payload, dict) and "rootTopic" in payload:
            blocks = _xmind_topic_blocks(payload["rootTopic"], level=1)
        elif isinstance(payload, list):
            for sheet in payload:
                if isinstance(sheet, dict) and sheet.get("rootTopic"):
                    blocks.extend(_xmind_topic_blocks(sheet["rootTopic"], level=1))
        return blocks or None
    except Exception:  # noqa: BLE001
        return None


def _xmind_topic_blocks(topic: dict, level: int) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    if not isinstance(topic, dict):
        return blocks
    title = topic.get("title") or ""
    if isinstance(title, list):
        title = "".join(str(t) for t in title if t)
    title = str(title).strip()
    if title:
        blocks.append({"type": "heading",
                       "content": {"level": min(level, 6), "text": title}})
    children = topic.get("children") or {}
    if isinstance(children, dict):
        attached = children.get("attached") or []
        for child in attached:
            blocks.extend(_xmind_topic_blocks(child, level=level + 1))
    return blocks
