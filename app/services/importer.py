"""目录/文件 → Note 树 导入服务（对照 v2 语义 + 验收规则，落 v3 模型）

导入编排严格两阶段（问题 #3）：
  阶段一 plan：先递归创建/复用整棵 note 节点并把「源文档相对路径 → 目标 note」
              完整注册（含目录/容器/宿主别名），不做任何内容写入；
  阶段二 fill：再按稳定顺序逐文档解析并追加到归属 note——此时任意文档间链接
              的目标节点均已存在，可稳定命中（相对链接按“源文档所在目录”解析）。

同名合并规则（问题 #1，用户已确认）：
- 目标为“当前选中页 P”时，匹配导入目录根层文档中 basename(去扩展名)==P.title：
  命中 → 内容追加到 P；未命中 → P 不写入（保持原状）。前端导入前提示规则、
  导入后提示结果（matched_target / container_note_id）。
- P.title == 目录名 → P 充当目录宿主（不套壳）：同名文档进 P，其它根层文档各自
  成 P 的子页（title=文件名），子目录为 P 子页。
- 否则在 P 下建「与目录同名」的目录容器页：容器承载根层其它文档（merge），
  子目录为容器子页；若另有同名文档仍会追加到 P。
- 追加防重：note.imported_digests 记录每源文档 sha1，重复导入跳过并计入 skipped。

资源：路径任一层含 image/media/img/images/assets/css/js/fonts 的文件上传为 asset
（StorageProvider + file_metadata），md/html 图片相对引用按文档目录改写为资源 URL。
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
from app.services.note_service import purge_note_tree
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

RESOURCE_DIRS = {"css", "media", "fonts", "js", "image", "img", "images", "assets"}
TEXT_DOC_EXTS = {".md", ".markdown", ".html", ".htm"}
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)#]+)(#[^)]*)?\)")


@dataclass
class ImportResult:
    root_note_id: Optional[str] = None
    created: list[str] = field(default_factory=list)
    reused: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    assets: int = 0
    matched_target: bool = False
    matched_doc: Optional[str] = None
    container_note_id: Optional[str] = None

    @property
    def all_notes(self) -> list[str]:
        return self.created + self.reused


def _norm(rel: str) -> str:
    p = rel.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    p = re.sub(r"/+", "/", p)
    return p.strip("/")


def _stem(name: str) -> str:
    return os.path.splitext(os.path.basename(name))[0]


def _resolve_ref(base_dir: str, ref: str) -> Optional[str]:
    if not ref or re.match(r"^(https?://|data:|/|#)", ref, re.I):
        return None
    joined = os.path.normpath(os.path.join(base_dir or "", ref)).replace("\\", "/")
    joined = _norm(joined)
    if joined.startswith(".."):
        return None
    return joined or None


def _is_asset_rel(rel: str) -> bool:
    return any(p.lower() in RESOURCE_DIRS for p in rel.split("/"))


def _digest(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _rewrite_links(text: str, base_dir: str, resolve_note) -> str:
    def repl(m: "re.Match") -> str:
        target = m.group(2).strip()
        resolved = _resolve_ref(base_dir, target)
        note = resolve_note(resolved or target)
        if note is not None and note.slug:
            return f"[{m.group(1)}](/notes/{note.slug})"
        return m.group(0)

    new_text, _ = _LINK_RE.subn(repl, text)
    return new_text


class _TreeImporter:
    def __init__(self, session: AsyncSession, project: Project, user: User, overwrite: bool):
        self.session = session
        self.project = project
        self.user = user
        self.overwrite = overwrite
        self.result = ImportResult()
        self.asset_map: dict[str, str] = {}
        self.path_to_note: dict[str, Note] = {}
        # plan 阶段收集的填充任务：(doc_rel, bytes)
        self._assignments: dict[str, bytes] = {}

    # ---------- 基础 ----------
    async def _make_note(self, title: str, parent: Optional[Note],
                         source_path: Optional[str], icon: str = "📄") -> Note:
        note = Note(
            project_id=self.project.id, title=title, icon=icon,
            parent_id=parent.id if parent else None, source_path=source_path,
            owner_id=self.user.id, creator_id=self.user.id, last_editor_id=self.user.id,
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

    async def _ensure_note(self, title: str, parent: Optional[Note], source_path: str,
                           icon: str = "📄") -> Optional[Note]:
        dup = await self._find_dup(parent, source_path)
        if dup is not None:
            if not self.overwrite:
                return None
            await purge_note_tree(self.session, dup.id)
        note = await self._make_note(title, parent, source_path=source_path, icon=icon)
        self.result.created.append(note.id)
        return note

    def _register(self, rel: str, note: Note) -> None:
        key = _norm(rel).lower()
        if not key:
            return
        self.path_to_note.setdefault(key, note)
        no_ext = re.sub(r"\.(md|html|htm)$", "", key)
        if no_ext != key:
            self.path_to_note.setdefault(no_ext, note)

    def _resolve_note(self, target: str) -> Optional[Note]:
        key = _norm(target).lower()
        if key in self.path_to_note:
            return self.path_to_note[key]
        base = os.path.basename(key).lower()
        base_no_ext = _stem(base)
        for k, n in self.path_to_note.items():
            kb = os.path.basename(k).lower()
            if kb == base or kb == base_no_ext:
                return n
        return None

    # ---------- 资源 ----------
    async def _upload_assets(self, cleaned: dict[str, bytes]) -> None:
        for rel in sorted(r for r in cleaned if _is_asset_rel(r)):
            data = cleaned[rel]
            try:
                storage = get_storage()
                filename = os.path.basename(rel)
                ext = os.path.splitext(filename)[1].lower()
                meta = FileMetadata(
                    organization_id=self.project.organization_id,
                    project_id=self.project.id, owner_id=self.user.id,
                    original_name=filename, storage_key="", size=len(data),
                    purpose="asset", status=FileStatus.COMPLETED.value,
                    parser_type="asset", mime_type="application/octet-stream",
                )
                self.session.add(meta)
                await self.session.flush()
                key = storage.build_key(self.project.organization_id, meta.id, ext)
                await storage.put(key, data)
                meta.storage_key = key
                await self.session.commit()
                await self.session.refresh(meta)
                url = f"/api/v1/files/{meta.id}/content"
                self.asset_map[rel] = url
                self.asset_map[os.path.basename(rel)] = url
                self.result.assets += 1
            except Exception:  # noqa: BLE001
                logger.exception("资源上传失败 rel=%s", rel)

    # ---------- plan：建节点/注册（不含内容） ----------
    async def _plan_level(self, note: Note, prefix: str, entries: dict[str, bytes]) -> None:
        """把 entries（prefix 目录内）计划到 note：根层文档注册到 note，子目录递归建节点。"""
        direct: dict[str, bytes] = {}
        dirs: dict[str, dict[str, bytes]] = {}
        for rel, data in entries.items():
            rest = rel[len(prefix) + 1:] if prefix else rel
            if rest and "/" in rest:
                seg = rest.split("/", 1)[0]
                dirs.setdefault(seg, {})[rel] = data
            elif rest:
                direct[rel] = data
        for rel in sorted(direct):
            self._register(rel, note)
            self._assignments[rel] = direct[rel]
        for seg in sorted(dirs):
            sp = f"{prefix}/{seg}".strip("/")
            child = await self._ensure_note(seg, note, sp)
            if child is None:
                continue
            self._register(sp, child)
            await self._plan_level(child, sp, dirs[seg])

    # ---------- fill：逐文档写入（第二阶段） ----------
    async def _fill_all(self) -> None:
        for rel in sorted(self._assignments):
            owner = self.path_to_note.get(_norm(rel).lower()) or self.path_to_note.get(
                re.sub(r"\.(md|html|htm)$", "", _norm(rel).lower()))
            if owner is None:
                continue
            data = self._assignments[rel]
            digest = _digest(data)
            digests = [str(d) for d in (owner.imported_digests or [])]
            if digest in digests:
                self.result.skipped.append(rel)
                continue
            filename = os.path.basename(rel)
            base_dir = os.path.dirname(rel) or ""
            blocks = parser_service.parse_document(filename, data, "")
            # 图片：按文档目录解析相对引用 → 资源 URL
            for b in blocks:
                if b["type"] == "image":
                    c = dict(b.get("content") or {})
                    url = c.get("url")
                    resolved = _resolve_ref(base_dir, url) if isinstance(url, str) else None
                    if resolved and resolved in self.asset_map:
                        c["url"] = self.asset_map[resolved]
                        b["content"] = c
            # 跨文档链接：path_to_note 已完整，命中即改写为 /notes/{slug}
            for b in blocks:
                c = b.get("content") or {}
                if b["type"] in ("paragraph", "quote") and isinstance(c.get("text"), str):
                    c["text"] = _rewrite_links(c["text"], base_dir, self._resolve_note)
                elif b["type"] == "list":
                    items = c.get("items")
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict) and isinstance(item.get("text"), str):
                                item["text"] = _rewrite_links(item["text"], base_dir, self._resolve_note)

            # 默认标题（“导入的笔记”）由首个 H1 同步
            if (owner.title or "") == "导入的笔记":
                for b in blocks:
                    if b["type"] == "heading" and (b.get("content") or {}).get("level") == 1:
                        h1 = str((b.get("content") or {}).get("text") or "").strip()
                        if h1:
                            owner.title = h1[:200]
                            self.session.add(owner)
                        break

            rows = await self.session.execute(
                select(NoteBlock).where(NoteBlock.note_id == owner.id)
                .order_by(NoteBlock.sort_order.desc()).limit(1)
            )
            last = rows.scalar_one_or_none()
            order = (last.sort_order if last else -1) + 1
            if not blocks:
                blocks = [{"type": "paragraph", "content": {"text": "（空内容）"}}]
            for block in blocks:
                self.session.add(NoteBlock(
                    note_id=owner.id, type=block["type"],
                    content=block.get("content") or {}, sort_order=order,
                ))
                order += 1
            owner.imported_digests = digests + [digest]
            owner.last_editor_id = self.user.id
            self.session.add(owner)

    # ---------- 目录模式（folder_mode） ----------
    async def _plan_folder(self, target: Optional[Note], folder: str,
                           docs: dict[str, bytes]) -> None:
        root_files: dict[str, bytes] = {}
        subtree: dict[str, bytes] = {}
        for rel, data in docs.items():
            rest = rel[len(folder) + 1:] if rel.startswith(folder + "/") else rel
            if "/" in rest:
                subtree[rel] = data
            else:
                root_files[rel] = data

        target_title = (target.title or "").strip() if target else None
        matched_key: Optional[str] = None
        if target is not None:
            for rel in sorted(root_files):
                if _stem(rel) == target_title:
                    matched_key = rel
                    break
        if matched_key:
            self.result.matched_target = True
            self.result.matched_doc = matched_key

        host_is_target = target is not None and target_title == folder
        if target is not None and host_is_target:
            # 选中页即目录宿主：不套壳；同名文档计划到 P，其余根层文档各自成 P 子页
            if matched_key:
                self._register(matched_key, target)
                self._assignments[matched_key] = root_files.pop(matched_key)
            for rel in sorted(root_files):
                child = await self._make_note(_stem(rel), target, source_path=rel)
                self.result.created.append(child.id)
                self._register(rel, child)
                self._assignments[rel] = root_files[rel]
            if subtree:
                await self._plan_level(target, folder, subtree)
            return

        # 建「与目录同名」的容器页（parent = 选中页 或 项目根）
        container = await self._ensure_note(folder, target, folder, icon="📁")
        if container is None:
            for rel in sorted(root_files) + sorted(subtree):
                self.result.skipped.append(rel)
            return
        self.result.container_note_id = container.id
        self._register(folder, container)
        # 同名文档仍追加到选中页（非同宿主场景）
        if matched_key and target is not None:
            self._register(matched_key, target)
            self._assignments[matched_key] = root_files.pop(matched_key)
        # 其余根层文档合入容器页
        for rel in sorted(root_files):
            self._register(rel, container)
            self._assignments[rel] = root_files[rel]
        if subtree:
            await self._plan_level(container, folder, subtree)

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

        await self._upload_assets(cleaned)
        docs = {r: cleaned[r] for r in sorted(cleaned) if not _is_asset_rel(r)}
        if not docs:
            await self.session.commit()
            return self.result

        first = [r.split("/", 1)[0] for r in docs]
        folder_mode = all("/" in r for r in docs) and len(set(first)) == 1
        folder = first[0] if folder_mode else None

        if folder_mode:
            if target_note is None:
                # 项目根导入：目录名=根容器
                container = await self._ensure_note(folder, None, folder, icon="📁")
                if container is None:
                    for r in docs:
                        self.result.skipped.append(r)
                    await self.session.commit()
                    return self.result
                self.result.root_note_id = container.id
                self._register(folder, container)
                await self._plan_level(container, folder, docs)
            else:
                await self._plan_folder(target_note, folder, docs)
                self.result.root_note_id = target_note.id
        else:
            await self._plan_flat(target_note, docs)

        await self._fill_all()
        await self.session.commit()
        return self.result

    # ---------- 扁平 / 混合模式 ----------
    async def _plan_flat(self, target: Optional[Note], docs: dict[str, bytes]) -> None:
        if target is None:
            sig = "__flat__:" + hashlib.sha1("\n".join(sorted(docs)).encode("utf-8")).hexdigest()[:24]
            dup = await self._find_dup(None, sig)
            if dup is not None and not self.overwrite:
                for r in docs:
                    self.result.skipped.append(r)
                return
            if dup is not None:
                await purge_note_tree(self.session, dup.id)
            root = await self._make_note("导入的笔记", None, source_path=sig)
            self.result.created.append(root.id)
            self.result.root_note_id = root.id
            await self._plan_level(root, "", docs)
            return

        # 有目标：顶层文件与选中页同名 → 追加到 P
        target_title = (target.title or "").strip()
        matched: Optional[str] = None
        for rel in sorted(docs):
            if "/" not in rel and _stem(rel) == target_title:
                matched = rel
                break
        if matched:
            self.result.matched_target = True
            self.result.matched_doc = matched
            self._register(matched, target)
            self._assignments[matched] = docs.pop(matched)
        direct: dict[str, bytes] = {}
        nested: dict[str, bytes] = {}
        for rel, data in docs.items():
            if "/" in rel:
                nested[rel] = data
            else:
                direct[rel] = data
        for rel in sorted(direct):
            child = await self._make_note(_stem(rel), target, source_path=rel)
            self.result.created.append(child.id)
            self._register(rel, child)
            self._assignments[rel] = direct[rel]
        if nested:
            await self._plan_level(target, "", nested)


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
