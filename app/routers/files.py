"""文件路由：上传（存储 + 元数据 + 异步解析触发）与内容访问

- purpose=document → 异步解析为笔记（parse_document 任务）
- purpose=asset   → 仅存储供内容引用（图片/代码等）
- /files/mine/*   → 用户级媒体（头像/AI 小助手图标与背景），无需 project_id

存储：新文件按 用户/文件类型 分类落盘（storage.build_key），存量 key 不变。
媒体鉴权：GET content 支持 Authorization 头或 ?access_token=（<img> 等媒体标签
无法携带请求头，前端渲染时统一在 URL 上附带 token）。
"""
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.deps import bearer_scheme, get_current_user, get_session
from app.core.permissions import PermissionChecker, get_permission_checker
from app.core.security import decode_token
from app.models.file import FileCategory, FileMetadata, FilePurpose, FileRead, FileStatus
from app.models.org import OrgRole
from app.models.project import Project
from app.models.user import User
from app.services.parser import get_file_type
from app.services.storage import get_storage
from app.tasks.parse import parse_document

router = APIRouter(prefix="/files", tags=["文件"])

_ALLOWED = set(settings.allowed_doc_extensions)
_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
_IMG_RE = re.compile(r"\.(png|jpe?g|gif|webp|svg|bmp|ico)$", re.I)

# 项目级文件分类（需 project_id 与 RBAC）
_PROJECT_CATEGORIES = {
    FilePurpose.DOCUMENT.value,
    FileCategory.NOTE_IMAGE.value,
    FileCategory.NOTE_ASSET.value,
}
# 用户级媒体分类（/files/mine，仅本人可见）
_USER_CATEGORIES = {
    FileCategory.USER_AVATAR.value,
    FileCategory.ASSISTANT_ICON.value,
    FileCategory.ASSISTANT_BG.value,
    FileCategory.ASSISTANT_MEDIA.value,
}


def _default_category(purpose: str, ext: str) -> str:
    """未显式传 category 时按 purpose + 扩展名推导"""
    if purpose == FilePurpose.DOCUMENT.value:
        return FilePurpose.DOCUMENT.value
    return FileCategory.NOTE_IMAGE.value if ext in _IMAGE_EXTS else FileCategory.NOTE_ASSET.value


def _check_ext(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的扩展名: {ext or '(无)'}",
        )
    return ext


async def _media_user(
    session: AsyncSession = Depends(get_session),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_token: Optional[str] = Query(default=None),
) -> Optional[User]:
    """媒体访问者解析：优先请求头 Bearer，其次 ?access_token=（供 <img> 使用）"""
    token = ""
    if credentials and credentials.credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    try:
        uid = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        return None
    result = await session.execute(select(User).where(User.id == uid, User.is_active.is_(True)))
    return result.scalar_one_or_none()


async def _file_media_response(file_meta: FileMetadata) -> Response:
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


# ---------- 用户级媒体（头像 / 小助手图标 / 背景） ----------

@router.post("/mine", response_model=FileRead, summary="上传用户级媒体（头像/小助手图标背景等）")
async def upload_mine(
    file: UploadFile = File(...),
    category: str = Form(FileCategory.USER_AVATAR.value),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if category not in _USER_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"category 需为: {', '.join(sorted(_USER_CATEGORIES))}")
    filename = file.filename or "unknown"
    ext = _check_ext(filename)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件内容为空")
    max_bytes = 5 * 1024 * 1024  # 用户媒体（图标/背景）上限 5MB
    if len(content) > max_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="文件超过大小限制 5MB")

    file_meta = FileMetadata(
        organization_id=None, project_id=None,
        owner_id=current_user.id,
        original_name=filename,
        storage_key="",
        size=len(content),
        purpose=FilePurpose.ASSET.value,
        category=category,
        status=FileStatus.COMPLETED.value,
        parser_type="user_media",
        mime_type=file.content_type or "application/octet-stream",
    )
    session.add(file_meta)
    await session.flush()

    storage = get_storage()
    key = storage.build_key(current_user.id, category, file_meta.id, ext)
    await storage.put(key, content)
    file_meta.storage_key = key
    await session.commit()
    await session.refresh(file_meta)
    return FileRead.model_validate(file_meta)


@router.get("/mine", response_model=list[FileRead], summary="我的媒体文件列表")
async def list_mine(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(FileMetadata)
        .where(FileMetadata.owner_id == current_user.id,
               FileMetadata.category.in_(sorted(_USER_CATEGORIES)))
        .order_by(FileMetadata.created_at.desc()).limit(50)
    )
    return [FileRead.model_validate(f) for f in result.scalars().all()]


@router.get("/mine/{file_id}/content", summary="访问我的媒体文件内容（可带 ?access_token=）")
async def mine_file_content(
    file_id: str,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(_media_user),
):
    file_meta = await session.get(FileMetadata, file_id)
    if not file_meta or file_meta.project_id is not None or file_meta.category not in _USER_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    if user is None or file_meta.owner_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    return await _file_media_response(file_meta)


@router.delete("/mine/{file_id}", summary="删除我的媒体文件")
async def delete_mine(
    file_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    file_meta = await session.get(FileMetadata, file_id)
    if not file_meta or file_meta.owner_id != current_user.id or file_meta.category not in _USER_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    storage = get_storage()
    await storage.delete(file_meta.storage_key)
    await session.delete(file_meta)
    await session.commit()
    return {"message": "文件已删除"}


# ---------- 项目文件 ----------

@router.post("/upload", response_model=FileRead, summary="上传文件（文档/附件，可指定分类）")
async def upload_file(
    file: UploadFile = File(...),
    project_id: str = Form(...),
    purpose: str = Form(FilePurpose.DOCUMENT.value),
    category: str = Form(""),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    """上传到 StorageProvider → 记录 file_metadata →（文档）触发异步解析"""
    if purpose not in (FilePurpose.DOCUMENT.value, FilePurpose.ASSET.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="purpose 需为 document 或 asset")

    project, _ = await perm.require_project_role(project_id, OrgRole.MAINTAINER.value)
    filename = file.filename or "unknown"
    ext = _check_ext(filename)

    cat = (category or "").strip()
    if not cat:
        cat = _default_category(purpose, ext)
    elif cat not in _PROJECT_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"category 需为: {', '.join(sorted(_PROJECT_CATEGORIES))}")
    elif (purpose == FilePurpose.DOCUMENT.value) != (cat == FilePurpose.DOCUMENT.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="purpose=document 时 category 必须为 document，反之亦然")

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
        category=cat,
        status=FileStatus.PENDING.value,
    )
    perm.session.add(file_meta)
    await perm.session.flush()

    storage = get_storage()
    key = storage.build_key(perm.user.id, cat, file_meta.id, ext)
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


@router.get("/{file_id}/content", summary="访问文件内容（可带 ?access_token=）")
async def file_content(
    file_id: str,
    session: AsyncSession = Depends(get_session),
    user: Optional[User] = Depends(_media_user),
):
    file_meta = await session.get(FileMetadata, file_id)
    if not file_meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    await _ensure_file_accessible(file_meta, user, session)
    return await _file_media_response(file_meta)


@router.get("/list/{project_id}", response_model=list[FileRead], summary="项目文件列表")
async def list_files(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_project_role(project_id, OrgRole.REPORTER.value)

    result = await perm.session.execute(
        select(FileMetadata).where(FileMetadata.project_id == project_id)
        .order_by(FileMetadata.created_at.desc()).limit(100)
    )
    return [FileRead.model_validate(f) for f in result.scalars().all()]


async def _ensure_file_accessible(file_meta: FileMetadata, user: Optional[User],
                                  session: AsyncSession) -> None:
    """文件访问控制：本人 / 项目读角色；未登录一律 404（媒体 URL 需带 access_token）"""
    if user is not None and file_meta.owner_id == user.id:
        return
    if file_meta.category in _USER_CATEGORIES or not file_meta.project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    project = await session.get(Project, file_meta.project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在或无权访问")
    perm = PermissionChecker(user, session)
    await perm.require_project_role(project.id, OrgRole.REPORTER.value)
