"""文件元数据模型：file_metadata（上传流水线状态机）"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def gen_uuid() -> str:
    return str(uuid.uuid4())


class FileStatus(str, Enum):
    """解析流水线状态"""

    PENDING = "PENDING"
    PARSING = "PARSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FilePurpose(str, Enum):
    """文件用途：
    - document: 文档导入（异步解析为 note 树）
    - asset: 内容附件（图片/代码等，仅存储供引用，不建笔记）
    """

    DOCUMENT = "document"
    ASSET = "asset"


class FileMetadata(SQLModel, table=True):
    """上传文件元数据（文件实体本身存于 StorageProvider）"""

    __tablename__ = "file_metadata"

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    organization_id: str = Field(foreign_key="organization.id", index=True)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id", index=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    original_name: str = Field(max_length=512)
    storage_key: str = Field(max_length=1024, index=True)  # StorageProvider 内的唯一 key
    mime_type: str = Field(default="application/octet-stream", max_length=200)
    size: int = Field(default=0)
    purpose: str = Field(default=FilePurpose.DOCUMENT.value, max_length=20)
    status: str = Field(default=FileStatus.PENDING.value, max_length=20, index=True)
    parser_type: Optional[str] = Field(default=None, max_length=50)  # md/html/pdf/xlsx/...
    chunk_count: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Schemas ----------

class FileRead(SQLModel):
    id: str
    organization_id: str
    project_id: Optional[str]
    owner_id: int
    original_name: str
    storage_key: str
    mime_type: str
    size: int
    purpose: str
    status: str
    parser_type: Optional[str]
    chunk_count: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
