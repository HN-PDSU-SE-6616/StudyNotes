"""用户模型（沿用原认证结构，表保持不变）"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=100)
    display_name: str = Field(default="", max_length=100)
    avatar_url: Optional[str] = Field(default=None)


class User(UserBase, table=True):
    __tablename__ = "user"

    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserRegister(SQLModel):
    username: str
    email: str
    password: str
    display_name: str = ""


class UserLogin(SQLModel):
    username: str
    password: str


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime


class UserUpdate(SQLModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead
