"""引导服务：注册/首次登录时为用户创建个人组织与默认项目"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.org import Organization, OrganizationMember, OrgRole
from app.models.project import Project
from app.models.user import User

DEFAULT_ORG_SUFFIX = "的组织"
DEFAULT_PROJECT_NAME = "我的项目"


async def create_personal_org(
    session: AsyncSession, user: User, org_name: Optional[str] = None
) -> tuple[Organization, Project]:
    """为用户创建个人组织 + 默认项目（Owner），返回 (org, project)"""
    name = org_name or f"{user.display_name or user.username}{DEFAULT_ORG_SUFFIX}"
    org = Organization(name=name, owner_id=user.id)
    session.add(org)
    await session.flush()

    session.add(
        OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.OWNER.value)
    )

    project = Project(
        organization_id=org.id,
        name=DEFAULT_PROJECT_NAME,
        icon="📚",
        creator_id=user.id,
    )
    session.add(project)
    await session.commit()
    await session.refresh(org)
    await session.refresh(project)
    return org, project


async def get_or_create_personal_org(
    session: AsyncSession, user: User
) -> tuple[Organization, Project]:
    """获取用户第一个组织（不存在则创建），兼容历史无组织账号"""
    result = await session.execute(
        select(OrganizationMember)
        .where(OrganizationMember.user_id == user.id, OrganizationMember.role == OrgRole.OWNER.value)
        .order_by(OrganizationMember.created_at)
    )
    member = result.scalars().first()
    if member:
        org = await session.get(Organization, member.organization_id)
        if org:
            proj_result = await session.execute(
                select(Project).where(Project.organization_id == org.id).order_by(Project.created_at)
            )
            project = proj_result.scalars().first()
            if project:
                return org, project
    return await create_personal_org(session, user)
