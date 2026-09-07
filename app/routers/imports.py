"""目录/多文件批量导入端点（对应 v2 /pages/import）

POST /api/v1/projects/{project_id}/import
multipart 字段：
- files: 一个或多个文件，filename 为 webkitRelativePath（保留目录结构）
- target_note_id: 可选，指定导入目标笔记（顶层文档合并进该笔记，子目录在其下）
- overwrite: 可选，重复内容是否重建（默认 false=跳过）
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import PermissionChecker, get_permission_checker
from app.database import get_session
from app.models.note import Note
from app.models.org import OrgRole
from app.models.project import Project
from app.services.importer import ImportResult, import_files_into_project

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["导入"])

# 单次导入总大小上限（60MB），防止内存被打满
MAX_TOTAL_BYTES = 60 * 1024 * 1024


@router.post("/{project_id}/import", summary="批量导入目录/文件 → Note 树")
async def import_into_project(
    project_id: str,
    files: list[UploadFile] = File(...),
    target_note_id: str = Form(None),
    overwrite: bool = Form(False),
    perm: PermissionChecker = Depends(get_permission_checker),
    session: AsyncSession = Depends(get_session),
):
    project, role = await perm.require_project_role(project_id, OrgRole.MAINTAINER.value)

    target_note: Note | None = None
    if target_note_id:
        note = await session.get(Note, target_note_id)
        if not note or note.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="目标笔记不存在")
        note, _ = await perm.require_note(note.id, "write")
        target_note = note

    file_map: dict[str, bytes] = {}
    total = 0
    for f in files:
        if not f.filename:
            continue
        content = await f.read()
        if not content:
            continue
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                detail=f"单次导入总大小超过 {MAX_TOTAL_BYTES // (1024 * 1024)}MB")
        file_map[f.filename] = content

    if not file_map:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可导入的文件")

    result: ImportResult = await import_files_into_project(
        session, project, perm.user, file_map,
        target_note=target_note, overwrite=overwrite,
    )

    # 触发向量索引（无 Embedding 环境会被 worker 静默跳过）
    from app.tasks.index import index_note

    for note_id in result.all_notes:
        try:
            index_note.delay(note_id)
        except Exception:  # noqa: BLE001
            logger.warning("下发索引任务失败 note=%s", note_id)

    created_notes = []
    for nid in result.all_notes:
        note = await session.get(Note, nid)
        if note:
            created_notes.append({
                "id": note.id,
                "title": note.title,
                "slug": note.slug,
                "parent_id": note.parent_id,
                "source_path": note.source_path,
            })

    return {
        "root_note_id": result.root_note_id,
        "created": result.created,
        "reused": result.reused,
        "skipped": result.skipped,
        "assets": result.assets,
        "matched_target": result.matched_target,
        "matched_doc": result.matched_doc,
        "container_note_id": result.container_note_id,
        "notes": created_notes,
    }
