"""项目路由：项目 CRUD + 项目成员/角色（RBAC 项目级覆盖）"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_user
from app.core.permissions import PermissionChecker, get_permission_checker
from app.database import get_session
from app.models.note import Note, NoteBlock, NoteLink, NoteViewLog
from app.models.org import OrgRole
from app.models.project import (
    PROJECT_ADMIN_ROLES,
    Project,
    ProjectCreate,
    ProjectMember,
    ProjectMemberAddRequest,
    ProjectMemberRead,
    ProjectMemberRoleUpdate,
    ProjectRead,
    ProjectReadWithRole,
    ProjectUpdate,
)
from app.models.user import User
from app.services.note_service import build_note_tree, get_project_notes
from app.tasks.index import queue_delete_note_index

collection = APIRouter(prefix="/orgs/{org_id}/projects", tags=["项目"])
items = APIRouter(prefix="/projects", tags=["项目"])

_ORG_ROLES = {r.value for r in OrgRole}


def _validate_role(role: str) -> str:
    if role not in _ORG_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"非法角色: {role}")
    return role


# ========== 组织下的项目集合 ==========

@collection.get("/", response_model=list[ProjectReadWithRole], summary="项目列表")
async def list_projects(
    org_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    """列出当前用户在该组织内可读的项目（含生效角色）"""
    await perm.require_org_role(org_id, OrgRole.REPORTER.value)
    result = await perm.session.execute(
        select(Project).where(Project.organization_id == org_id).order_by(Project.created_at)
    )
    items = []
    for project in result.scalars().all():
        role = await perm.effective_project_role(project)
        if not role:
            continue
        items.append(
            ProjectReadWithRole(
                **ProjectRead.model_validate(project).model_dump(),
                my_role=role,
            )
        )
    return items


@collection.get("/by-slug/{slug}", response_model=ProjectReadWithRole, summary="按 slug 获取项目")
async def get_project_by_slug(
    org_id: str,
    slug: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_org_role(org_id, OrgRole.REPORTER.value)
    result = await perm.session.execute(
        select(Project).where(Project.organization_id == org_id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权访问")
    role = await perm.effective_project_role(project)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权访问")
    return ProjectReadWithRole(**ProjectRead.model_validate(project).model_dump(), my_role=role)


@collection.post("/", response_model=ProjectRead, summary="创建项目")
async def create_project(
    org_id: str,
    body: ProjectCreate,
    current_user: User = Depends(get_current_user),
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_org_role(org_id, OrgRole.ADMIN.value)
    project = Project(
        organization_id=org_id,
        name=body.name,
        slug=body.slug,
        icon=body.icon,
        description=body.description,
        creator_id=current_user.id,
    )
    perm.session.add(project)
    # 创建者默认加入（角色继承组织角色，不写 project_member）
    await perm.session.commit()
    await perm.session.refresh(project)
    return ProjectRead.model_validate(project)


# ========== 项目条目 ==========

@items.get("/{project_id}", response_model=ProjectReadWithRole, summary="项目详情")
async def get_project(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, role = await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    return ProjectReadWithRole(**ProjectRead.model_validate(project).model_dump(), my_role=role)


@items.patch("/{project_id}", response_model=ProjectRead, summary="更新项目")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.ADMIN.value)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    from datetime import datetime

    project.updated_at = datetime.utcnow()
    perm.session.add(project)
    await perm.session.commit()
    await perm.session.refresh(project)
    return ProjectRead.model_validate(project)


@items.delete("/{project_id}", summary="删除项目")
async def delete_project(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.ADMIN.value)

    note_ids = list((await perm.session.execute(
        select(Note.id).where(Note.project_id == project_id)
    )).scalars().all())
    if note_ids:
        for model, col in [
            (NoteBlock, "note_id"),
            (NoteLink, "source_note_id"),
            (NoteViewLog, "note_id"),
        ]:
            rows = (await perm.session.execute(
                select(model).where(getattr(model, col).in_(note_ids))
            )).scalars().all()
            for r in rows:
                await perm.session.delete(r)
        notes = (await perm.session.execute(
            select(Note).where(Note.id.in_(note_ids))
        )).scalars().all()
        for n in notes:
            await perm.session.delete(n)
            queue_delete_note_index(n.id)

    pm_rows = (await perm.session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    )).scalars().all()
    for r in pm_rows:
        await perm.session.delete(r)
    await perm.session.delete(project)
    await perm.session.commit()
    return {"message": "项目已删除"}


# ========== 项目成员 ==========

@items.get("/{project_id}/members", response_model=list[ProjectMemberRead], summary="项目成员")
async def list_project_members(
    project_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.REPORTER.value)
    # 项目内可访问成员 = 项目显式成员 ∪ 组织成员
    result = await perm.session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id)
    )
    explicit: dict[int, ProjectMember] = {}
    for pm, user in result.all():
        explicit[user.id] = pm

    from app.models.org import OrganizationMember

    org_result = await perm.session.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == project.organization_id)
    )
    items: list[ProjectMemberRead] = []
    for om, user in org_result.all():
        project_member = explicit.get(user.id)
        effective = project_member.role if project_member and project_member.role else om.role
        items.append(ProjectMemberRead(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=project_member.role if project_member else None,
            effective_role=effective,
            created_at=(project_member.created_at if project_member else om.created_at),
        ))
    return items


@items.post("/{project_id}/members", response_model=ProjectMemberRead, summary="添加项目成员")
async def add_project_member(
    project_id: str,
    body: ProjectMemberAddRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, caller_role = await perm.require_project_role(project_id, OrgRole.ADMIN.value)
    if caller_role not in PROJECT_ADMIN_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    role = _validate_role(body.role) if body.role else None
    # 目标用户必须是组织成员
    from app.models.org import OrganizationMember

    target_result = await perm.session.execute(select(User).where(User.username == body.username))
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    om = await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == target.id,
        )
    )
    if not om.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="目标用户不是本组织成员")

    existing = await perm.session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == target.id,
        )
    )
    pm = existing.scalar_one_or_none()
    if pm:
        pm.role = role
        perm.session.add(pm)
    else:
        pm = ProjectMember(project_id=project_id, user_id=target.id, role=role)
        perm.session.add(pm)
    await perm.session.commit()
    await perm.session.refresh(pm)

    org_om = (await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == target.id,
        )
    )).scalar_one()
    effective = pm.role or org_om.role
    return ProjectMemberRead(
        user_id=target.id,
        username=target.username,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        role=pm.role,
        effective_role=effective,
        created_at=pm.created_at,
    )


@items.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberRead, summary="调整项目角色")
async def update_project_member_role(
    project_id: str,
    user_id: int,
    body: ProjectMemberRoleUpdate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.ADMIN.value)
    role = _validate_role(body.role) if body.role else None

    from app.models.org import OrganizationMember

    org_om = (await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == project.organization_id,
            OrganizationMember.user_id == user_id,
        )
    )).scalar_one_or_none()
    if not org_om:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")

    existing = await perm.session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    pm = existing.scalar_one_or_none()
    if role is None:
        # 恢复继承：删除显式项目角色
        if pm:
            await perm.session.delete(pm)
            await perm.session.commit()
        target = await perm.session.get(User, user_id)
        return ProjectMemberRead(
            user_id=user_id,
            username=target.username if target else "",
            display_name=target.display_name if target else "",
            avatar_url=target.avatar_url if target else None,
            role=None,
            effective_role=org_om.role,
            created_at=org_om.created_at,
        )
    if pm:
        pm.role = role
        perm.session.add(pm)
    else:
        pm = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        perm.session.add(pm)
    await perm.session.commit()
    await perm.session.refresh(pm)

    target = await perm.session.get(User, user_id)
    return ProjectMemberRead(
        user_id=target.id,
        username=target.username,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        role=pm.role,
        effective_role=role,
        created_at=pm.created_at,
    )


@items.delete("/{project_id}/members/{user_id}", summary="移除项目成员")
async def remove_project_member(
    project_id: str,
    user_id: int,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    project, _ = await perm.require_project_role(project_id, OrgRole.ADMIN.value)
    existing = await perm.session.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    pm = existing.scalar_one_or_none()
    if not pm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目成员不存在")
    await perm.session.delete(pm)
    await perm.session.commit()
    return {"message": "项目成员已移除（组织角色仍生效）"}
