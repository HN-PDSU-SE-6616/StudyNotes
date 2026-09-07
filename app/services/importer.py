"""目录/多文件 → Note 树 导入服务（对照 v2 语义，落 v3 模型）

核心规则：
- 文件相对路径 = 树层级：当前层级的 .md/.html/.txt/代码等解析为该层笔记的块；
  普通子目录递归为子笔记（目录=子笔记）。
- 路径任意层级出现 image/media/img/images/assets/css/js/fonts 资源目录时，
  该文件整体作为静态资源上传（StorageProvider + file_metadata purpose=asset），
  md/html 图片块按文档所在目录解析相对引用并改写为资源 URL。
- Markdown 跨文档链接 [text](相对路径) 二次修复：命中路径映射则替换为
  [/notes/{slug}] 跳转链接（渲染层可点击）。
- 标题：默认标题时由首个 H1 同步；无 H1 用源文件名。
- 幂等：note.source_path 存根相对路径；重复导入（根签名/目录路径相同）
  overwrite=true 清空重建、false 跳过（记入 skipped）。
"""
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.file import FileMetadata, FileStatus
from app.models.note import Note, NoteBlock
from app.models.project import Project
from app.models.user import User
from app.services import parser as parser_service
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

RESOURCE_DIRS = {"css", "media", "fonts", "js", "image", "img", "images", "assets"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif"}
TEXT_DOC_EXTS = {".md", ".markdown", ".html", ".htm"}
ROOT_PREFIX = "__root__:"


@dataclass
class ImportResult:
    """导入结果摘要"""

    root_note_id: Optional[str] = None
    created: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    assets: int = 0

    @property
    def all_notes(self) -> list[str]:
        return self.created + self.reused


def _norm(rel: str) -> str:
    p = rel.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = re.sub(r"/+", "/", p)
    return p.strip("/")


def _resolve_ref(base_dir: str, ref: str) -> Optional[str]:
    """文档内相对引用解析为导入根下的规范路径（越出根返回 None）"""
    if not ref or re.match(r"^(https?://|data:|/|#)", ref, re.I):
        return None
    joined = os.path.normpath(os.path.join(base_dir or "", ref)).replace("\\", "/")
    joined = _norm(joined)
    if joined.startswith(".."):
        return None
    return joined or None


def _is_asset_rel(rel: str) -> bool:
    parts = rel.split("/")
    return any(p.lower() in RESOURCE_DIRS for p in parts)


async def _purge_note_tree(session: AsyncSession, note_id: str) -> None:
    """递归删除笔记及其子孙（块/链接/ACL/浏览日志同步清理）"""
    from app.models.note import NoteAcl, NoteLink, NoteViewLog

    to_delete: list[str] = []
    stack = [note_id]
    while stack:
        nid = stack.pop()
        to_delete.append(nid)
        rows = await session.execute(select(Note).where(Note.parent_id == nid))
        for child in rows.scalars().all():
            stack.append(child.id)

    if to_delete:
        rows = await session.execute(select(NoteBlock).where(NoteBlock.note_id.in_(to_delete)))
        for b in rows.scalars().all():
            await session.delete(b)
        for model, col in ((NoteAcl, "note_id"), (NoteViewLog, "note_id")):
            rows = await session.execute(select(model).where(getattr(model, col).in_(to_delete)))
            for r in rows.scalars().all():
                await session.delete(r)
        rows = await session.execute(
            select(NoteLink).where(
                (NoteLink.source_note_id.in_(to_delete)) | (NoteLink.target_note_id.in_(to_delete))
            )
        )
        for r in rows.scalars().all():
            await session.delete(r)
        await session.flush()
    # 叶子优先逐层删除并立即 flush，规避 note 自引用外键在批量 flush 时的顺序问题
    for nid in reversed(to_delete):
        note = await session.get(Note, nid)
        if note:
            await session.delete(note)
            await session.flush()
    await session.commit()


async def _upload_asset(
    session: AsyncSession,
    project: Project,
    user: User,
    rel: str,
    data: bytes,
) -> Optional[str]:
    try:
        storage = get_storage()
        filename = os.path.basename(rel)
        ext = os.path.splitext(filename)[1].lower()
        meta = FileMetadata(
            organization_id=project.organization_id,
            project_id=project.id,
            owner_id=user.id,
            original_name=filename,
            storage_key="",
            size=len(data),
            purpose="asset",
            status=FileStatus.COMPLETED.value,
            parser_type="asset",
            mime_type="application/octet-stream",
        )
        session.add(meta)
        await session.flush()
        key = storage.build_key(project.organization_id, meta.id, ext)
        await storage.put(key, data)
        meta.storage_key = key
        await session.commit()
        await session.refresh(meta)
        return f"/api/v1/files/{meta.id}/content"
    except Exception:  # noqa: BLE001
        logger.exception("资源上传失败 rel=%s", rel)
        return None


def _sync_title_from_blocks(note: Note, blocks: list[dict[str, Any]], fallback: str) -> None:
    if note.title and note.title not in ("导入的笔记", "未命名笔记"):
        return
    for b in blocks:
        if b["type"] == "heading" and (b.get("content") or {}).get("level") == 1:
            text = str((b.get("content") or {}).get("text") or "").strip()
            if text:
                note.title = text[:200]
                return
    note.title = fallback[:200] or "导入的笔记"


class _TreeImporter:
    def __init__(self, session: AsyncSession, project: Project, user: User, overwrite: bool):
        self.session = session
        self.project = project
        self.user = user
        self.overwrite = overwrite
        self.result = ImportResult()
        self.asset_map: dict[str, str] = {}
        self.path_to_note: dict[str, Note] = {}

    # ---------- 基础 ----------
    async def _make_note(self, title: str, parent: Optional[Note], source_path: Optional[str]) -> Note:
        note = Note(
            project_id=self.project.id,
            title=title,
            icon="📄",
            parent_id=parent.id if parent else None,
            source_path=source_path,
            owner_id=self.user.id,
            creator_id=self.user.id,
            last_editor_id=self.user.id,
        )
        self.session.add(note)
        await self.session.flush()
        return note

    async def _find_dup(self, parent: Optional[Note], source_path: Optional[str]) -> Optional[Note]:
        if not source_path:
            return None
        cond = [Note.source_path == source_path, Note.project_id == self.project.id]
        cond.append(Note.parent_id == parent.id if parent else Note.parent_id.is_(None))
        rows = await self.session.execute(select(Note).where(*cond).limit(2))
        return rows.scalars().first()

    def _base_name(self, rel: str) -> str:
        return os.path.splitext(os.path.basename(rel))[0] or "导入文档"

    # ---------- 入口 ----------
    async def import_root(self, file_map: dict[str, bytes],
                          target_note: Optional[Note] = None) -> ImportResult:
        cleaned: dict[str, bytes] = {}
        for k, v in file_map.items():
            nk = _norm(k)
            if nk:
                cleaned[nk] = v
        if not cleaned:
            return self.result

        asset_keys = sorted(r for r in cleaned if _is_asset_rel(r))
        docs = {r: cleaned[r] for r in sorted(cleaned) if r not in asset_keys}

        # 2) 根笔记（幂等：源内容签名，先判定再干活避免重复上传/建树）
        root_note: Optional[Note] = None
        if target_note is not None:
            root_note = target_note
            if self.overwrite:
                await _purge_note_tree(self.session, root_note.id)
                self.result.reused.append(root_note.id)
            else:
                self.result.created.append(root_note.id)
        else:
            sig = ROOT_PREFIX + hashlib.sha1("\n".join(sorted(cleaned)).encode("utf-8")).hexdigest()[:24]
            dup = await self._find_dup(None, sig)
            if dup is not None and not self.overwrite:
                for r in sorted(docs):
                    self.result.skipped.append(r)
                return self.result
            if dup is not None:  # overwrite：清空重建
                await _purge_note_tree(self.session, dup.id)
            root_note = await self._make_note("导入的笔记", None, source_path=sig)
            self.result.created.append(root_note.id)
            self.path_to_note[sig.lower()] = root_note

        # 1) 上传静态资源（映射键 = 相对导入根的完整路径）
        for rel in asset_keys:
            url = await _upload_asset(self.session, self.project, self.user, rel, cleaned[rel])
            if url:
                self.asset_map[rel] = url
                self.asset_map[os.path.basename(rel)] = url
                self.result.assets += 1

        if not docs:
            await self.session.commit()
            self.result.root_note_id = root_note.id
            return self.result  # 全为资源：仅建根笔记

        # 3) 树构建
        await self._fill_level(root_note, prefix="", entries=docs)
        await self.session.commit()

        # 4) 跨文档链接修复（针对本次创建的笔记）
        await self._fix_links()
        await self.session.refresh(root_note)
        self.result.root_note_id = root_note.id
        return self.result

    # ---------- 递归填充 ----------
    async def _fill_level(self, note: Note, prefix: str, entries: dict[str, bytes]) -> None:
        direct: dict[str, bytes] = {}
        children: dict[str, dict[str, bytes]] = {}
        for rel, data in entries.items():
            rest = rel[len(prefix) + 1:] if prefix else rel
            if "/" in rest:
                seg = rest.split("/", 1)[0]
                children.setdefault(seg, {})[rel] = data
            else:
                direct[rel] = data
        if direct:
            await self._inject_docs(note, direct)
        if children:
            for seg in sorted(children):
                source_path = f"{prefix}/{seg}".strip("/")
                child = await self._ensure_child_dir(note, source_path, seg)
                if child is None:
                    continue
                await self._fill_level(child, prefix=source_path, entries=children[seg])

    # ---------- 文档注入 ----------
    async def _inject_docs(self, note: Note, files: dict[str, bytes]) -> None:
        order = 0
        rows = await self.session.execute(
            select(NoteBlock).where(NoteBlock.note_id == note.id)
        )
        existing = rows.scalars().all()
        if existing:
            order = max(b.sort_order for b in existing) + 1
        all_parsed: list[dict[str, Any]] = []
        fallback_title = None
        for rel in sorted(files, key=lambda x: x.lower()):
            blocks = await self._parse_doc(note, rel, files[rel])
            for b in blocks:
                self.session.add(NoteBlock(
                    note_id=note.id,
                    type=b["type"],
                    content=b.get("content") or {},
                    sort_order=order,
                ))
                order += 1
            all_parsed.extend(blocks)
            if fallback_title is None:
                fallback_title = self._base_name(rel)
        if all_parsed:
            _sync_title_from_blocks(note, all_parsed, fallback_title or "导入的笔记")
            await self.session.flush()
            note.last_editor_id = self.user.id
            self.session.add(note)
            # 记录文档映射供链接修复
            for rel in sorted(files):
                self.path_to_note.setdefault(rel.lower(), note)

    async def _parse_doc(self, note: Note, rel: str, data: bytes) -> list[dict[str, Any]]:
        filename = os.path.basename(rel)
        blocks = parser_service.parse_document(filename, data, "")
        base_dir = os.path.dirname(rel) or ""
        for b in blocks:
            if b["type"] == "image":
                content = dict(b.get("content") or {})
                url = content.get("url")
                resolved = _resolve_ref(base_dir, url) if isinstance(url, str) else None
                if resolved and resolved in self.asset_map:
                    content["url"] = self.asset_map[resolved]
                    b["content"] = content
        return blocks

    # ---------- 子目录 ----------
    async def _ensure_child_dir(self, parent: Note, source_path: str, seg: str) -> Optional[Note]:
        dup = await self._find_dup(parent, source_path)
        if dup is not None and not self.overwrite:
            return None
        if dup is not None:
            await _purge_note_tree(self.session, dup.id)
        child = await self._make_note(seg, parent, source_path=source_path)
        self.result.created.append(child.id)
        self.path_to_note.setdefault(source_path.lower(), child)
        return child

    # ---------- 链接修复 ----------
    async def _fix_links(self) -> None:
        affected_ids = {n.id for n in self.path_to_note.values()}
        for note_id in affected_ids:
            rows = await self.session.execute(
                select(NoteBlock).where(NoteBlock.note_id == note_id).order_by(NoteBlock.sort_order)
            )
            changed = False
            for b in rows.scalars().all():
                c = b.content or {}
                if b.type in ("paragraph", "quote") and isinstance(c.get("text"), str):
                    new_text, made = self._rewrite_text_links(c["text"])
                    if made:
                        b.content = {**c, "text": new_text}
                        changed = True
                elif b.type == "list":
                    items = c.get("items")
                    if isinstance(items, list):
                        mutated = False
                        for item in items:
                            if isinstance(item, dict) and isinstance(item.get("text"), str):
                                new_text, made = self._rewrite_text_links(item["text"])
                                if made:
                                    item["text"] = new_text
                                    mutated = True
                        if mutated:
                            b.content = {**c, "items": items}
                            changed = True
                if changed:
                    self.session.add(b)
            if changed:
                await self.session.commit()

    def _rewrite_text_links(self, text: str) -> tuple[str, bool]:
        pattern = re.compile(r"\[([^\]]+)\]\(([^)#]+)(#[^)]*)?\)")

        def repl(m: re.Match) -> str:
            target = m.group(2).strip()
            note = self._resolve_note(target)
            if note is None or not note.slug:
                return m.group(0)
            return f"[{m.group(1)}](/notes/{note.slug})"

        new_text, count = pattern.subn(repl, text)
        return new_text, count > 0

    def _resolve_note(self, target: str) -> Optional[Note]:
        key = _norm(target).lower()
        if key in self.path_to_note:
            return self.path_to_note[key]
        no_ext = re.sub(r"\.(md|html|htm)$", "", key)
        if no_ext in self.path_to_note:
            return self.path_to_note[no_ext]
        base = os.path.basename(key).lower()
        base_no_ext = re.sub(r"\.(md|html|htm)$", "", base)
        for k, n in self.path_to_note.items():
            kb = os.path.basename(k).lower()
            if kb == base or kb == base_no_ext or k == base or k == base_no_ext:
                return n
        return None


async def import_files_into_project(
    session: AsyncSession,
    project: Project,
    user: User,
    file_map: dict[str, bytes],
    target_note: Optional[Note] = None,
    overwrite: bool = False,
) -> ImportResult:
    importer = _TreeImporter(session, project, user, overwrite=overwrite)
    return await importer.import_root(file_map, target_note=target_note)
