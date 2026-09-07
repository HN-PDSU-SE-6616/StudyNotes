"""权限中间层：RBAC（组织/项目级）+ ABAC（笔记属性与 ACL）

统一语义：
- 组织/项目访问均需是组织成员；非成员一律按 404 处理（不泄露资源存在性）。
- 笔记读取：公开(is_public) 或 项目可读 或 owner 或 ACL(read/write/delete)。
- 笔记写入：owner 或 项目可写角色 或 ACL(write/delete)。
- 笔记删除：owner 或 ACL(delete) 或 项目 Owner/Admin。
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_session
from app.models.note import Note, NoteAcl
from app.models.org import OrganizationMember, OrgRole, ROLE_RANK
from app.models.project import (
    PROJECT_ADMIN_ROLES,
    PROJECT_READ_ROLES,
    PROJECT_WRITE_ROLES,
    Project,
    ProjectMember,
)
from app.models.user import User

HTTP_404 = status.HTTP_404_NOT_FOUND
HTTP_403 = status.HTTP_403_FORBIDDEN


def role_meets(role: Optional[str], min_role: str) -> bool:
    """判断 role 是否达到 min_role 门槛"""
    if not role:
        return False
    return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(min_role, 0)


def permission_meets(permission: Optional[str], min_permission: str) -> bool:
    """ACL 权限比较：read < write < delete"""
    rank = {"read": 1, "write": 2, "delete": 3}
    if not permission:
        return False
    return rank.get(permission, 0) >= rank.get(min_permission, 0)


class PermissionChecker:
    """会话级权限校验器（依赖注入）"""

    def __init__(self, current_user: User, session: AsyncSession):
        self.user = current_user
        self.session = session

    # ---------- 组织 ----------

    async def get_org_member(self, org_id: str) -> Optional[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember).where(
                OrganizationMember.organization_id == org_id,
                OrganizationMember.user_id == self.user.id,
            )
        )
        return result.scalar_one_or_none()

    async def require_org_role(self, org_id: str, min_role: str = OrgRole.REPORTER.value) -> str:
        """要求用户是组织成员且角色 >= min_role；返回角色值"""
        member = await self.get_org_member(org_id)
        if not member:
            raise HTTPException(status_code=HTTP_404, detail="组织不存在或无权访问")
        if not role_meets(member.role, min_role):
            raise HTTPException(status_code=HTTP_403, detail="权限不足")
        return member.role

    async def get_org_ids(self) -> list[str]:
        """当前用户所属的全部组织 id"""
        result = await self.session.execute(
            select(OrganizationMember.organization_id).where(OrganizationMember.user_id == self.user.id)
        )
        return list(result.scalars().all())

    # ---------- 项目 ----------

    async def get_project(self, project_id: str) -> Optional[Project]:
        return await self.session.get(Project, project_id)

    async def effective_project_role(self, project: Project) -> Optional[str]:
        """项目内生效角色：项目级覆盖 > 组织角色继承"""
        if not project:
            return None
        # 项目级显式角色
        pm = await self.session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == self.user.id,
            )
        )
        project_member = pm.scalar_one_or_none()
        if project_member and project_member.role:
            return project_member.role
        # 继承组织角色
        org_role = await self.get_org_role(project.organization_id)
        return org_role

    async def get_org_role(self, org_id: str) -> Optional[str]:
        member = await self.get_org_member(org_id)
        return member.role if member else None

    async def require_project_role(
        self, project_id: str, min_role: str = OrgRole.REPORTER.value
    ) -> tuple[Project, str]:
        """要求对项目拥有 >= min_role 的生效角色；返回 (project, effective_role)"""
        project = await self.session.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=HTTP_404, detail="项目不存在或无权访问")
        role = await self.effective_project_role(project)
        if not role:
            # 非组织成员且无显式项目角色：统一 404，避免资源存在性泄露
            raise HTTPException(status_code=HTTP_404, detail="项目不存在或无权访问")
        if not role_meets(role, min_role):
            raise HTTPException(status_code=HTTP_403, detail="权限不足")
        return project, role

    async def get_accessible_project_ids(
        self, include_read: bool = True, org_id: Optional[str] = None
    ) -> list[str]:
        """返回当前用户可读的全部项目 id（或限定某组织下）"""
        # 1) 用户所在组织列表
        org_cond = [OrganizationMember.user_id == self.user.id]
        if org_id:
            org_cond.append(OrganizationMember.organization_id == org_id)
        org_stmt = select(OrganizationMember.organization_id).where(*org_cond)
        org_ids = list((await self.session.execute(org_stmt)).scalars().all())

        # 2) 组织内全部项目（组织成员即具备读权限）
        project_ids: set[str] = set()
        if org_ids:
            proj_stmt = select(Project.id).where(Project.organization_id.in_(org_ids))
            project_ids.update((await self.session.execute(proj_stmt)).scalars().all())

        # 3) 显式项目成员（设置了项目级角色）——即使非组织成员也可访问
        if include_read:
            pm_stmt = select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == self.user.id,
                ProjectMember.role.is_not(None),
            )
            for pid, role in (await self.session.execute(pm_stmt)).all():
                if role in PROJECT_READ_ROLES:
                    project_ids.add(pid)

        return list(project_ids)

    # ---------- 笔记（ABAC） ----------

    async def get_note(self, note_id: str) -> Optional[Note]:
        return await self.session.get(Note, note_id)

    async def get_note_acl(self, note_id: str) -> Optional[NoteAcl]:
        result = await self.session.execute(
            select(NoteAcl).where(NoteAcl.note_id == note_id, NoteAcl.user_id == self.user.id)
        )
        return result.scalar_one_or_none()

    async def require_note(self, note_id: str, permission: str = "read") -> tuple[Note, Optional[str]]:
        """
        校验对 note 的访问权限。
        返回 (note, 生效角色) 或抛 404/403；permission: read/write/delete。
        """
        note = await self.session.get(Note, note_id)
        if not note:
            raise HTTPException(status_code=HTTP_404, detail="笔记不存在或无权访问")

        # owner 全权
        if note.owner_id == self.user.id:
            return note, OrgRole.OWNER.value

        # ABAC 属性 + ACL
        acl = await self.get_note_acl(note.id)
        if acl and permission_meets(acl.permission, permission):
            return note, None
        if note.is_public and permission == "read":
            return note, None

        # RBAC 项目继承
        project = await self.session.get(Project, note.project_id)
        if not project:
            raise HTTPException(status_code=HTTP_404, detail="笔记不存在或无权访问")
        role = await self.effective_project_role(project)
        if not role:
            raise HTTPException(status_code=HTTP_404, detail="笔记不存在或无权访问")

        if permission == "read" and role in PROJECT_READ_ROLES:
            return note, role
        if permission == "write" and role in PROJECT_WRITE_ROLES:
            return note, role
        if permission == "delete" and (role in PROJECT_ADMIN_ROLES or role == OrgRole.OWNER.value):
            return note, role

        raise HTTPException(status_code=HTTP_403, detail="权限不足")


def get_permission_checker(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> PermissionChecker:
    return PermissionChecker(current_user, session)
