"""笔记模型：note / note_block / note_link / note_acl（ABAC 属性与 ACL）"""
import secrets
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def gen_uuid() -> str:
    return str(uuid.uuid4())


def _gen_slug() -> str:
    return secrets.token_urlsafe(8)[:12]


# JSON 列：PG 使用 JSONB，其他方言（如 SQLite 测试）回退 JSON
JSONB_COLUMN = JSON().with_variant(JSONB, "postgresql")


class NoteBlockType(str, Enum):
    """Block 类型（沿用旧编辑器 BlockType）"""

    PARAGRAPH = "paragraph"
    HEADING = "heading"
    CODE = "code"
    QUOTE = "quote"
    LIST = "list"
    IMAGE = "image"
    CHART = "chart"
    DIVIDER = "divider"
    NOTE_LINK = "note_link"
    TABLE = "table"
    CALLOUT = "callout"
    FILE = "file"


class Note(SQLModel, table=True):
    """笔记（知识库页面；替代旧 Page，归属于 project）"""

    __tablename__ = "note"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_note_project_slug"),)

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    slug: str = Field(default_factory=_gen_slug, max_length=64)
    title: str = Field(index=True)
    icon: Optional[str] = Field(default="doc")
    parent_id: Optional[str] = Field(default=None, foreign_key="note.id", index=True)
    sort_order: int = Field(default=0)
    is_pinned: bool = Field(default=False)
    # ABAC 属性
    is_public: bool = Field(default=False, index=True)
    owner_id: int = Field(foreign_key="user.id", index=True)
    creator_id: Optional[int] = Field(default=None, foreign_key="user.id")
    last_editor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # 来源文件（经文件流水线导入时记录）
    source_file_id: Optional[str] = Field(default=None, foreign_key="file_metadata.id")
    # 目录/文件导入时记录的源相对路径（重导幂等判定依据；文件流水线置 None）
    source_path: Optional[str] = Field(default=None, index=True, max_length=500)
    view_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NoteBlock(SQLModel, table=True):
    """笔记内容块（替代旧 Block；JSONB content）"""

    __tablename__ = "note_block"

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    note_id: str = Field(foreign_key="note.id", index=True)
    type: str = Field(default=NoteBlockType.PARAGRAPH.value)
    content: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB_COLUMN))
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NoteLink(SQLModel, table=True):
    """笔记间链接关系（侧边栏下拉与关系图）"""

    __tablename__ = "note_link"

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    source_note_id: str = Field(foreign_key="note.id", index=True)
    target_note_id: str = Field(foreign_key="note.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NoteAcl(SQLModel, table=True):
    """笔记级显式授权（ABAC ACL）：精确指定用户对单篇笔记的权限"""

    __tablename__ = "note_acl"
    __table_args__ = (UniqueConstraint("note_id", "user_id", name="uq_note_acl"),)

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    note_id: str = Field(foreign_key="note.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    permission: str = Field(default="read", max_length=20)  # read / write / delete
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NoteViewLog(SQLModel, table=True):
    """笔记浏览记录（推荐引擎输入）"""

    __tablename__ = "note_view_log"

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    note_id: str = Field(foreign_key="note.id", index=True)
    viewed_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Schemas ----------

class NoteCreate(SQLModel):
    title: str
    icon: Optional[str] = "doc"
    parent_id: Optional[str] = None
    sort_order: int = 0


class NoteUpdate(SQLModel):
    title: Optional[str] = None
    icon: Optional[str] = None
    parent_id: Optional[str] = None
    sort_order: Optional[int] = None
    is_pinned: Optional[bool] = None
    is_public: Optional[bool] = None


class NoteRead(SQLModel):
    id: str
    project_id: str
    slug: str
    title: str
    icon: Optional[str]
    parent_id: Optional[str]
    sort_order: int
    is_pinned: bool
    is_public: bool
    owner_id: int
    creator_id: Optional[int] = None
    last_editor_id: Optional[int] = None
    view_count: int = 0
    created_at: datetime
    updated_at: datetime


class NoteTreeNode(NoteRead):
    children: list["NoteTreeNode"] = []
    linked_children: list["NoteTreeNode"] = []


class NoteBlockCreate(SQLModel):
    type: str = NoteBlockType.PARAGRAPH.value
    content: dict[str, Any] = {}
    sort_order: int = 0


class NoteBlockUpdate(SQLModel):
    type: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None


class NoteBlockRead(SQLModel):
    id: str
    note_id: str
    type: str
    content: dict[str, Any]
    sort_order: int
    created_at: datetime
    updated_at: datetime


class NoteDetail(NoteRead):
    blocks: list[NoteBlockRead] = []


class NoteStats(SQLModel):
    total_words: int = 0
    block_count: int = 0
    view_count: int = 0
    created_at: datetime
    creator_name: Optional[str] = None
    updated_at: datetime
    last_editor_name: Optional[str] = None
