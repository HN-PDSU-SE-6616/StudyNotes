"""组织模型：organization + 成员关系（RBAC 组织级角色）"""
import secrets
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def gen_uuid() -> str:
    """生成 UUID 字符串主键"""
    return str(uuid.uuid4())


def _gen_slug() -> str:
    return secrets.token_urlsafe(10)[:14]


class OrgRole(str, Enum):
    """组织/项目级 RBAC 角色，权限从高到低"""

    OWNER = "owner"
    ADMIN = "admin"
    MAINTAINER = "maintainer"
    REPORTER = "reporter"
    GUEST = "guest"


# 角色等级映射，用于比较
ROLE_RANK: dict[str, int] = {
    OrgRole.OWNER.value: 100,
    OrgRole.ADMIN.value: 80,
    OrgRole.MAINTAINER.value: 60,
    OrgRole.REPORTER.value: 40,
    OrgRole.GUEST.value: 20,
}


class Organization(SQLModel, table=True):
    """组织（租户顶层单元）"""

    __tablename__ = "organization"

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    name: str = Field(index=True)
    slug: str = Field(default_factory=_gen_slug, unique=True, index=True, max_length=64)
    owner_id: int = Field(foreign_key="user.id", index=True)
    icon: Optional[str] = Field(default="🏢")
    description: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrganizationMember(SQLModel, table=True):
    """组织成员（RBAC 组织级）"""

    __tablename__ = "organization_member"
    __table_args__ = (UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

    id: Optional[str] = Field(default_factory=gen_uuid, primary_key=True)
    organization_id: str = Field(foreign_key="organization.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = Field(default=OrgRole.REPORTER.value, max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Schemas ----------

class OrgCreate(SQLModel):
    name: str
    slug: Optional[str] = None
    icon: Optional[str] = "🏢"
    description: Optional[str] = None


class OrgUpdate(SQLModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None


class OrgRead(SQLModel):
    id: str
    name: str
    slug: str
    icon: Optional[str]
    description: Optional[str]
    owner_id: int
    created_at: datetime


class OrgReadWithRole(OrgRead):
    """组织 + 当前用户在其中的角色"""
    my_role: str


class OrgMemberRead(SQLModel):
    user_id: int
    username: str
    display_name: str
    avatar_url: Optional[str]
    role: str
    created_at: datetime


class MemberAddRequest(SQLModel):
    username: str
    role: str = OrgRole.REPORTER.value


class MemberRoleUpdate(SQLModel):
    role: str
