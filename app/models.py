# app/models.py — 兼容旧导入路径
from app.models.legacy import Note, NoteCreate, NoteRead, NoteUpdate

__all__ = ["Note", "NoteCreate", "NoteRead", "NoteUpdate"]
