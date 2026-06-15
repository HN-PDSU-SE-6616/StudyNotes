"""静态文件管理 - 上传、存储、提供访问"""
import os
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/files", tags=["文件管理"])

# 统一静态文件存储根目录
UPLOAD_ROOT = Path("static/uploads")

# 允许的静态文件扩展名
ALLOWED_EXTENSIONS = {
    # 图片
    '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico',
    # 字体
    '.woff', '.woff2', '.ttf', '.eot', '.otf',
    # 样式/脚本
    '.css', '.js',
    # 文档
    '.pdf', '.md', '.txt',
}


def _get_user_dir(user_id: int) -> Path:
    """获取用户上传目录"""
    d = UPLOAD_ROOT / str(user_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(original: str) -> str:
    """生成安全的唯一文件名，保留扩展名"""
    ext = os.path.splitext(original)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = '.bin'
    return f"{uuid.uuid4().hex}{ext}"


@router.post("/upload", summary="上传单个静态文件")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """上传静态文件，返回可访问的 URL 路径"""
    user_dir = _get_user_dir(current_user.id)
    safe_name = _safe_filename(file.filename or "unknown")
    dest = user_dir / safe_name

    content = await file.read()
    dest.write_bytes(content)

    url = f"/static/uploads/{current_user.id}/{safe_name}"
    return {
        "url": url,
        "filename": file.filename,
        "size": len(content),
    }


@router.post("/upload-batch", summary="批量上传静态文件")
async def upload_files_batch(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """批量上传静态文件，保留相对目录结构"""
    user_dir = _get_user_dir(current_user.id)
    results: list[dict] = []

    for file in files:
        if not file.filename:
            continue
        safe_name = _safe_filename(os.path.basename(file.filename))
        dest = user_dir / safe_name

        content = await file.read()
        dest.write_bytes(content)

        results.append({
            "original": file.filename,
            "url": f"/static/uploads/{current_user.id}/{safe_name}",
            "size": len(content),
        })

    return {"files": results, "count": len(results)}


@router.post("/upload-with-path", summary="按目录结构批量上传")
async def upload_with_path(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    保留原始相对路径的批量上传。
    前端使用 webkitRelativePath 传入目录结构。
    """
    user_dir = _get_user_dir(current_user.id)
    path_map: dict[str, str] = {}  # original_path -> url

    for file in files:
        if not file.filename:
            continue
        # webkitRelativePath: "folder/sub/file.png"
        relative_path = file.filename.replace("\\", "/")

        # 保留目录结构
        safe_name = f"{uuid.uuid4().hex[:8]}/{os.path.basename(relative_path)}"
        dest = user_dir / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)

        content = await file.read()
        dest.write_bytes(content)

        url = f"/static/uploads/{current_user.id}/{safe_name}"
        path_map[relative_path] = url

    return {"path_map": path_map, "count": len(path_map)}


@router.get("/serve/{user_id}/{file_path:path}", summary="提供静态文件访问")
async def serve_file(user_id: int, file_path: str):
    """直接提供上传文件访问（用于 nginx 不可用时）"""
    full_path = UPLOAD_ROOT / str(user_id) / file_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(full_path)
