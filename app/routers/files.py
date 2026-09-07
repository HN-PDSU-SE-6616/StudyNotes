"""文件路由：上传（存储 + 元数据 + 异步解析触发）与内容访问

- purpose=document：异步解析为笔记（parse_document 任务）
- purpose=asset：仅存储供内容引用（图片/代码等）
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response

from app.core.config import settings
from app.core.deps import get_current_user
from app.core.permissions import PermissionChecker, get_permission_checker
from app.models.file import FileMetadata, FilePurpose, FileRead, FileStatus
from app.models.org import OrgRole
from app.models.project import Project
from app.services.parser import get_file_type
from app.services.storage import get_storage
from app.tasks.parse import parse_document

router = APIRouter(prefix="/files", tags=["文件"])

_ALLOWED = set(settings.allowed_doc_extensions)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}


def _check_ext(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的扩展名: {ext or '(无)'}",
        )
    return ext


@router.post("/upload", response_model=FileRead, summary="上传文件（文档/附件）")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    purpose: str = Form(FilePurpose.DOCUMENT.value),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    """上传到 StorageProvider → 记录 file_metadata →（文档）触发异步解析"""
    if purpose not in (FilePurpose.DOCUMENT.value, FilePurpose.ASSET.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="purpose 需为 document 或 asset")

    project, _ = await perm.require_project_role(project_id, OrgRole.MAINTAINER.value)
    filename = file.filename or "unknown"
    ext = _check_ext(filename)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空")
    max_bytes = settings.parse_max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件超过大小限制 {settings.parse_max_file_size_mb}MB",
        )

    file_meta = FileMetadata(
        organization_id=project.organization_id,
        project_id=project.id,
        owner_id=perm.user.id,
        original_name=filename,
        storage_key="",  # 占位，落盘后回填
        size=len(content),
        purpose=purpose,
        status=FileStatus.PENDING.value,
    )
    perm.session.add(file_meta)
    await perm.session.flush()

    storage = get_storage()
    key = storage.build_key(project.organization_id, file_meta.id, ext)
    await storage.put(key, content)
    file_meta.storage_key = key
    file_meta.mime_type = file.content_type or "application/octet-stream"

    if purpose == FilePurpose.ASSET.value:
        file_meta.status = FileStatus.COMPLETED.value
        file_meta.parser_type = "asset"
    else:
        file_meta.parser_type = get_file_type(filename)
        file_meta.status = FileStatus.PENDING.value

    await perm.session.commit()
    await perm.session.refresh(file_meta)

    if purpose == FilePurpose.DOCUMENT.value:
        try:
            # 优先入队（异步解析）；队列不可用时同步降级（同一事件循环内执行）
            parse_document.delay(file_meta.id)
        except Exception:  # noqa: BLE001
            from app.tasks.parse import parse_file_now

            await parse_file_now(file_meta.id, perm.session)

    return FileRead.model_validate(file_meta)


@router.get("/{file_id}/content", summary="访问文件内容")
async def file_content(
    file_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    file_meta = await perm.session.get(FileMetadata, file_id)
    if not file_meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    await _ensure_file_accessible(file_meta, perm)

    try:
        storage = get_storage()
        data = await storage.get(file_meta.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件实体缺失")
    return Response(
        content=data,
        media_type=file_meta.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{file_meta.original_name}"'},
    )


@router.get("/list/{project_id}", response_model=list[FileRead], summary="项目文件列表")
async def list_files(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    from sqlmodel import select

    result = await perm.session.execute(
        select(FileMetadata).where(FileMetadata.project_id == project_id)
        .order_by(FileMetadata.created_at.desc()).limit(100)
    )
    return [FileRead.model_validate(f) for f in result.scalars().all()]


async def _ensure_file_accessible(file_meta: FileMetadata, perm: PermissionChecker) -> None:
    """文件访问控制：owner 或 项目读角色"""
    if file_meta.owner_id == perm.user.id:
        return
    if not file_meta.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    project = await perm.session.get(Project, file_meta.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    role = await perm.effective_project_role(project)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    if role not in ("owner", "admin", "maintainer", "reporter"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
