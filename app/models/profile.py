"""用户兴趣画像：新用户 onboarding 选择的职业 + 技术栈（推荐冷启动输入）"""
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# JSON 列：PG 使用 JSONB，其他方言（如 SQLite 测试）回退 JSON
JSONB_COLUMN = JSON().with_variant(JSONB, "postgresql")


class UserProfile(SQLModel, table=True):
    """用户画像（一对一到 user）

    job_role: careers.CAREER_OPTIONS 的 key 或空；自定义职业填 custom + job_role_custom。
    tech_tags: 技术栈多选（含用户自定义词）。
    """

    __tablename__ = "user_profile"

    user_id: Optional[int] = Field(default=None, primary_key=True, foreign_key="user.id")
    job_role: Optional[str] = Field(default=None, max_length=60)
    job_role_custom: Optional[str] = Field(default=None, max_length=120)
    tech_tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB_COLUMN, nullable=True))
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProfileRead(SQLModel):
    user_id: int
    job_role: Optional[str] = None
    job_role_custom: Optional[str] = None
    tech_tags: list[str] = []
    updated_at: Optional[datetime] = None


class ProfileUpdate(SQLModel):
    job_role: Optional[str] = None
    job_role_custom: Optional[str] = None
    tech_tags: Optional[list[str]] = None
