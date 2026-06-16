"""页面与 Block 模型"""
import secrets
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from sqlmodel import Field, SQLModel, Column, JSON


def _gen_slug() -> str:
    """生成16位随机唯一标识符 (a-zA-Z0-9)"""
    return secrets.token_urlsafe(12)[:16]


class BlockType(str, Enum):
    """Block 类型枚举"""
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    CODE = "code"
    QUOTE = "quote"
    LIST = "list"
    IMAGE = "image"
    CHART = "chart"
    DIVIDER = "divider"
    PAGE_LINK = "page_link"
    TABLE = "table"
    CALLOUT = "callout"


class PageCategory(str, Enum):
    """页面分类（侧边栏分组）"""
    QUICK_START = "quick_start"
    DOC = "doc"
    PROJECT = "project"
    WEBSITE = "website"
    TEAM = "team"
    CUSTOM = "custom"


class Workspace(SQLModel, table=True):
    """用户工作区"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="我的工作区")
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Page(SQLModel, table=True):
    """笔记页面"""
    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="workspace.id", index=True)
    slug: str = Field(default_factory=_gen_slug, unique=True, index=True, max_length=16)
    title: str = Field(index=True)
    icon: Optional[str] = Field(default="📄")
    category: str = Field(default=PageCategory.CUSTOM.value)
    parent_id: Optional[int] = Field(default=None, foreign_key="page.id")
    sort_order: int = Field(default=0)
    is_pinned: bool = Field(default=False)
    creator_id: Optional[int] = Field(default=None, foreign_key="user.id")
    last_editor_id: Optional[int] = Field(default=None, foreign_key="user.id")
    view_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Block(SQLModel, table=True):
    """页面内容块"""
    id: Optional[int] = Field(default=None, primary_key=True)
    page_id: int = Field(foreign_key="page.id", index=True)
    type: str = Field(default=BlockType.PARAGRAPH.value)
    content: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PageLink(SQLModel, table=True):
    """页面间链接关系（用于侧边栏下拉与关系图）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    source_page_id: int = Field(foreign_key="page.id", index=True)
    target_page_id: int = Field(foreign_key="page.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Schemas ----------

class PageCreate(SQLModel):
    title: str
    icon: Optional[str] = "📄"
    category: str = PageCategory.CUSTOM.value
    parent_id: Optional[int] = None


class PageUpdate(SQLModel):
    title: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_pinned: Optional[bool] = None


class PageRead(SQLModel):
    id: int
    workspace_id: int
    slug: str
    title: str
    icon: Optional[str]
    category: str
    parent_id: Optional[int]
    sort_order: int
    is_pinned: bool
    creator_id: Optional[int] = None
    last_editor_id: Optional[int] = None
    view_count: int = 0
    created_at: datetime
    updated_at: datetime


class PageTreeNode(PageRead):
    slug: str
    children: list["PageTreeNode"] = []
    linked_children: list["PageTreeNode"] = []


class BlockCreate(SQLModel):
    type: str = BlockType.PARAGRAPH.value
    content: dict[str, Any] = {}
    sort_order: int = 0


class BlockUpdate(SQLModel):
    type: Optional[str] = None
    content: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None


class BlockRead(SQLModel):
    id: int
    page_id: int
    type: str
    content: dict[str, Any]
    sort_order: int
    created_at: datetime
    updated_at: datetime


class PageDetail(PageRead):
    blocks: list[BlockRead] = []


class PageGraphNode(SQLModel):
    id: int
    title: str
    icon: Optional[str]


class PageGraphEdge(SQLModel):
    source: int
    target: int


class PageGraph(SQLModel):
    nodes: list[PageGraphNode]
    edges: list[PageGraphEdge]


class PageStats(SQLModel):
    """页面统计信息"""
    total_words: int = 0          # 总字数
    block_count: int = 0            # 块个数
    view_count: int = 0             # 页面总浏览量
    created_at: datetime            # 创建时间
    creator_name: Optional[str] = None  # 创建者
    updated_at: datetime            # 最后编辑时间
    last_editor_name: Optional[str] = None  # 最后编辑者
