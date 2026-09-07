"""内容切分服务：将笔记的 Block 序列切成带锚点的文本块（chunk）

锚点体系（与 Qdrant payload 对齐）：
- heading_path：由 heading 块维护的标题层级路径，如 "第三章/3.1节"
- page：来自 PDF 导入块 content.page（若有）
- block_start / block_end：chunk 覆盖的块索引区间（引用跳转落点）
"""
from typing import Any, Optional

# 单 chunk 最大字符数（含 overlap 前）
MAX_CHARS = 800
OVERLAP_CHARS = 80


def _block_text(block_type: str, content: dict[str, Any]) -> Optional[str]:
    """提取单个块的可向量化文本；无文本返回 None"""
    if not isinstance(content, dict):
        return None
    if block_type == "heading":
        text = content.get("text")
        return text if isinstance(text, str) and text.strip() else None
    if block_type in ("paragraph", "quote", "callout"):
        text = content.get("text")
        return text if isinstance(text, str) and text.strip() else None
    if block_type == "code":
        code = content.get("code")
        lang = content.get("language") or "text"
        if isinstance(code, str) and code.strip():
            return f"[{lang}代码块]\n{code}"
        return None
    if block_type == "list":
        parts: list[str] = []
        if content.get("items"):
            for item in content.get("items", []):
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    prefix = "[x] " if item.get("checked") else "[ ] "
                    parts.append(prefix + item["text"])
                elif isinstance(item, str):
                    parts.append(item)
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
        return "\n".join(parts) if parts else None
    if block_type == "table":
        headers = content.get("headers") or []
        rows = content.get("rows") or []
        lines = [" | ".join(str(h) for h in headers)]
        for row in rows:
            lines.append(" | ".join(str(c) for c in row))
        return "\n".join(lines) if lines else None
    # image / divider / file / chart 等不参与向量化
    return None


class _HeadingStack:
    """维护当前标题层级路径"""

    def __init__(self) -> None:
        self.path: list[tuple[int, str]] = []  # (level, title)

    def push(self, level: int, title: str) -> None:
        while self.path and self.path[-1][0] >= level:
            self.path.pop()
        self.path.append((level, title))

    def value(self) -> str:
        return "/".join(t for _, t in self.path)


def chunk_blocks(
    blocks: list[dict[str, Any]],
    fallback_heading: str = "",
) -> list[dict[str, Any]]:
    """将 blocks（dict 形式）切分为 chunk 列表。

    每个 chunk: {text, heading_path, page, block_start, block_end, anchor}
    """
    stack = _HeadingStack()
    chunks: list[dict[str, Any]] = []
    pending_texts: list[str] = []
    current_page: Optional[int] = None
    current_heading = ""
    current_start: Optional[int] = None
    current_end: Optional[int] = None

    def flush() -> None:
        nonlocal pending_texts, current_start, current_end, current_heading, current_page
        text = "\n".join(t for t in pending_texts if t)
        if text.strip():
            chunk = {
                "text": text,
                "heading_path": current_heading or fallback_heading,
                "page": current_page,
                "block_start": current_start,
                "block_end": current_end,
                "anchor": (current_heading or fallback_heading),
            }
            chunks.append(chunk)
        pending_texts = []
        current_start = current_end = None

    for idx, block in enumerate(blocks):
        btype = block.get("type", "paragraph")
        content = block.get("content") or {}

        if btype == "heading":
            level = content.get("level") or 1
            title = str(content.get("text") or "").strip()
            flush()
            if title:
                stack.push(int(level), title)
            current_heading = stack.value()
            page_marker = content.get("page")
            if page_marker is not None:
                current_page = int(page_marker)
            continue

        text = _block_text(btype, content)
        if text is None:
            flush()
            continue
        if current_start is None:
            current_start = idx
        current_end = idx
        pending_texts.append(text)

        # 长度裁剪：整体过长则 flush
        while True:
            joined = "\n".join(pending_texts)
            if len(joined) <= MAX_CHARS:
                break
            # 超长时先落一条（前 MAX_CHARS），保留 overlap 尾巴到下一块
            text_to_emit = joined[:MAX_CHARS]
            # 找到最后一个换行切割点，避免切断语义
            cut = text_to_emit.rfind("\n")
            if cut > MAX_CHARS * 0.6:
                text_to_emit = text_to_emit[:cut]
            chunk = {
                "text": text_to_emit,
                "heading_path": current_heading or fallback_heading,
                "page": current_page,
                "block_start": current_start,
                "block_end": current_end,
                "anchor": (current_heading or fallback_heading),
            }
            chunks.append(chunk)
            remaining = joined[len(text_to_emit):]
            pending_texts = [remaining[max(0, len(remaining) - OVERLAP_CHARS):]] if remaining else []
            current_start = current_end

    flush()
    return chunks


def chunk_blocks_with_index(
    blocks: list[dict[str, Any]],
    fallback_heading: str = "",
) -> list[dict[str, Any]]:
    """为每个 chunk 附加自增 chunk_index（0 起）"""
    chunks = chunk_blocks(blocks, fallback_heading=fallback_heading)
    for i, c in enumerate(chunks):
        c["chunk_index"] = i
    return chunks
