"""项目模型：project + 项目成员（RBAC 项目级角色，未指定则继承组织角色）"""
import secrets
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.models.org import OrgRole, gen_uuid as _gen_uuid


def _gen_project_slug() -> str:
    return secrets.token_urlsafe(8)[:12]


class Project(SQLModel, table=True):
    """项目（知识库容器，替代旧 Workspace；一个组织下可有多个项目）"""

    __tablename__ = "project"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_project_org_slug"),)

    id: Optional[str] = Field(default_factory=_gen_uuid, primary_key=True)
    organization_id: str = Field(foreign_key="organization.id", index=True)
    name: str = Field(index=True)
    slug: str = Field(default_factory=_gen_project_slug, max_length=64)
    icon: Optional[str] = Field(default="📚")
    description: Optional[str] = Field(default=None)
    is_archived: bool = Field(default=False)
    creator_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ProjectMember(SQLModel, table=True):
    """项目成员；role 为空表示继承组织角色"""

    __tablename__ = "project_member"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id: Optional[str] = Field(default_factory=_gen_uuid, primary_key=True)
    project_id: str = Field(foreign_key="project.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: Optional[str] = Field(default=None, max_length=20)  # 覆盖组织角色
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- Schemas ----------

class ProjectCreate(SQLModel):
    name: str
    slug: Optional[str] = None
    icon: Optional[str] = "📚"
    description: Optional[str] = None


class ProjectUpdate(SQLModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    icon: Optional[str] = None
    description: Optional[str] = None
    is_archived: Optional[bool] = None


class ProjectRead(SQLModel):
    id: str
    organization_id: str
    name: str
    slug: str
    icon: Optional[str]
    description: Optional[str]
    is_archived: bool
    creator_id: int
    created_at: datetime
    updated_at: datetime


class ProjectReadWithRole(ProjectRead):
    """项目 + 当前用户生效角色（含继承）"""
    my_role: str


class ProjectMemberRead(SQLModel):
    user_id: int
    username: str
    display_name: str
    avatar_url: Optional[str]
    role: Optional[str]  # None = 继承组织角色
    effective_role: str  # 最终生效角色
    created_at: datetime


class ProjectMemberRoleUpdate(SQLModel):
    role: Optional[str] = None  # None 恢复继承


class ProjectMemberAddRequest(SQLModel):
    username: str
    role: Optional[str] = None


# 项目可写的角色门槛（维护者/管理员/所有者）
PROJECT_WRITE_ROLES = {OrgRole.OWNER.value, OrgRole.ADMIN.value, OrgRole.MAINTAINER.value}
# 项目可读的角色门槛
PROJECT_READ_ROLES = PROJECT_WRITE_ROLES | {OrgRole.REPORTER.value}
# 项目管理（成员/删除等）角色门槛
PROJECT_ADMIN_ROLES = {OrgRole.OWNER.value, OrgRole.ADMIN.value}
