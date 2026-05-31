# app/models.py
from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship


class NoteBase(SQLModel):
    title: str = Field(index=True, description="笔记标题")
    parent_id: Optional[int] = Field(default=None, foreign_key="note.id")
    content_type: str = Field(default="db", description="笔记存储类型")  # "db" 或 "file"
    content_path: Optional[str] = Field(default=None, description="文件路径")
    content_db: Optional[str] = Field(default=None, description="HTML 内容")


class Note(NoteBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    children: List["Note"] = Relationship(back_populates="parent")
    parent: Optional["Note"] = Relationship(back_populates="children",
                                            sa_relationship_kwargs={"remote_side": "Note.id"})
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NoteCreate(NoteBase):
    pass


class NoteUpdate(SQLModel):
    title: Optional[str] = None
    parent_id: Optional[int] = None
    content_type: str = None
    content_path: Optional[str] = None
    content_db: Optional[str] = None


class NoteRead(NoteBase):
    id: int
    created_at: datetime
    updated_at: datetime
