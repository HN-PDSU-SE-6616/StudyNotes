"""组织路由：CRUD + 成员邀请/角色分配（RBAC 组织级）"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_user
from app.core.permissions import PermissionChecker, get_permission_checker
from app.database import get_session
from app.models.org import (
    MemberAddRequest,
    MemberRoleUpdate,
    OrgCreate,
    OrgMemberRead,
    OrgRead,
    OrgReadWithRole,
    OrgRole,
    OrgUpdate,
    Organization,
    OrganizationMember,
    ROLE_RANK,
)
from app.models.user import User

router = APIRouter(prefix="/orgs", tags=["组织"])

_ROLE_NAMES = {r.value for r in OrgRole}


def _validate_role(role: str) -> str:
    if role not in _ROLE_NAMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"非法角色: {role}")
    return role


@router.get("/", response_model=list[OrgReadWithRole], summary="我的组织列表")
async def list_orgs(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(OrganizationMember, Organization)
        .join(Organization, Organization.id == OrganizationMember.organization_id)
        .where(OrganizationMember.user_id == current_user.id)
    )
    items = []
    for member, org in result.all():
        items.append(
            OrgReadWithRole(
                **OrgRead.model_validate(org).model_dump(),
                my_role=member.role,
            )
        )
    return items


@router.post("/", response_model=OrgRead, summary="创建组织")
async def create_org(
    body: OrgCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    org = Organization(
        name=body.name,
        slug=body.slug,
        icon=body.icon,
        description=body.description,
        owner_id=current_user.id,
    )
    session.add(org)
    await session.flush()
    session.add(
        OrganizationMember(organization_id=org.id, user_id=current_user.id, role=OrgRole.OWNER.value)
    )
    await session.commit()
    await session.refresh(org)
    return OrgRead.model_validate(org)


@router.get("/by-slug/{slug}", response_model=OrgReadWithRole, summary="按 slug 获取组织")
async def get_org_by_slug(
    slug: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    result = await perm.session.execute(
        select(Organization).where(Organization.slug == slug)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织不存在或无权访问")
    role = await perm.require_org_role(org.id, OrgRole.REPORTER.value)
    return OrgReadWithRole(**OrgRead.model_validate(org).model_dump(), my_role=role)


@router.get("/{org_id}", response_model=OrgReadWithRole, summary="组织详情")
async def get_org(
    org_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    role = await perm.require_org_role(org_id, OrgRole.REPORTER.value)
    org = await perm.session.get(Organization, org_id)
    return OrgReadWithRole(**OrgRead.model_validate(org).model_dump(), my_role=role)


@router.patch("/{org_id}", response_model=OrgRead, summary="更新组织")
async def update_org(
    org_id: str,
    body: OrgUpdate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_org_role(org_id, OrgRole.ADMIN.value)
    org = await perm.session.get(Organization, org_id)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(org, key, value)
    from datetime import datetime

    org.updated_at = datetime.utcnow()
    perm.session.add(org)
    await perm.session.commit()
    await perm.session.refresh(org)
    return OrgRead.model_validate(org)


@router.delete("/{org_id}", summary="删除组织")
async def delete_org(
    org_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_org_role(org_id, OrgRole.OWNER.value)
    org = await perm.session.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="组织不存在")

    from app.models.file import FileMetadata
    from app.models.note import Note, NoteBlock, NoteLink, NoteViewLog
    from app.models.project import Project, ProjectMember

    # 级联清理：项目→笔记→块/日志/链接→成员→文件
    project_ids = list((await perm.session.execute(
        select(Project.id).where(Project.organization_id == org_id)
    )).scalars().all())
    note_ids: list[str] = []
    if project_ids:
        note_ids = list((await perm.session.execute(
            select(Note.id).where(Note.project_id.in_(project_ids))
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

    if project_ids:
        rows = (await perm.session.execute(
            select(ProjectMember).where(ProjectMember.project_id.in_(project_ids))
        )).scalars().all()
        for r in rows:
            await perm.session.delete(r)
        projects = (await perm.session.execute(
            select(Project).where(Project.id.in_(project_ids))
        )).scalars().all()
        for p in projects:
            await perm.session.delete(p)

    file_rows = (await perm.session.execute(
        select(FileMetadata).where(FileMetadata.organization_id == org_id)
    )).scalars().all()
    for f in file_rows:
        await perm.session.delete(f)
    members = (await perm.session.execute(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    )).scalars().all()
    for m in members:
        await perm.session.delete(m)
    await perm.session.delete(org)
    await perm.session.commit()
    return {"message": "组织已删除"}


@router.get("/{org_id}/members", response_model=list[OrgMemberRead], summary="成员列表")
async def list_members(
    org_id: str,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    await perm.require_org_role(org_id, OrgRole.REPORTER.value)
    result = await perm.session.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.created_at)
    )
    items = []
    for member, user in result.all():
        items.append(OrgMemberRead(
            user_id=user.id,
            username=user.username,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=member.role,
            created_at=member.created_at,
        ))
    return items


@router.post("/{org_id}/members", response_model=OrgMemberRead, summary="添加成员（按用户名）")
async def add_member(
    org_id: str,
    body: MemberAddRequest,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    caller_role = await perm.require_org_role(org_id, OrgRole.ADMIN.value)
    role = _validate_role(body.role)
    if role == OrgRole.OWNER.value and caller_role != OrgRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅 Owner 可授予 Owner")

    user_result = await perm.session.execute(select(User).where(User.username == body.username))
    target = user_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    existing = await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == target.id,
        )
    )
    member = existing.scalar_one_or_none()
    if member:
        member.role = role
        perm.session.add(member)
    else:
        member = OrganizationMember(organization_id=org_id, user_id=target.id, role=role)
        perm.session.add(member)
    await perm.session.commit()
    await perm.session.refresh(member)

    return OrgMemberRead(
        user_id=target.id,
        username=target.username,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        role=member.role,
        created_at=member.created_at,
    )


@router.patch("/{org_id}/members/{user_id}", response_model=OrgMemberRead, summary="调整角色")
async def update_member_role(
    org_id: str,
    user_id: int,
    body: MemberRoleUpdate,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    caller_role = await perm.require_org_role(org_id, OrgRole.ADMIN.value)
    role = _validate_role(body.role)
    result = await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    # 仅 Owner 能改 Owner/Admin 的权限；Owner 本人不可被降级（简易约束）
    if member.role == OrgRole.OWNER.value and caller_role != OrgRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅 Owner 可管理 Owner")
    if user_id == perm.user.id and role != OrgRole.OWNER.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能降级自己")

    member.role = role
    perm.session.add(member)
    await perm.session.commit()
    await perm.session.refresh(member)
    target = await perm.session.get(User, user_id)
    return OrgMemberRead(
        user_id=target.id,
        username=target.username,
        display_name=target.display_name,
        avatar_url=target.avatar_url,
        role=member.role,
        created_at=member.created_at,
    )


@router.delete("/{org_id}/members/{user_id}", summary="移除成员")
async def remove_member(
    org_id: str,
    user_id: int,
    perm: PermissionChecker = Depends(get_permission_checker),
):
    caller_role = await perm.require_org_role(org_id, OrgRole.ADMIN.value)
    result = await perm.session.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="成员不存在")
    if member.role == OrgRole.OWNER.value or user_id == perm.user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner 不可被移除，请先转让")
    await perm.session.delete(member)
    await perm.session.commit()
    return {"message": "成员已移除"}
