"""用户画像路由：读取/更新职业 + 技术栈（新用户 onboarding）"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import get_current_user
from app.database import get_session
from app.models.profile import ProfileRead, ProfileUpdate, UserProfile
from app.models.user import User
from app.services.careers import CAREER_OPTIONS

router = APIRouter(prefix="/users/me/profile", tags=["画像"])

_TAG_LIMIT = 20
_LEN_LIMIT = {"job_role": 60, "job_role_custom": 120}


async def _load(session: AsyncSession, user_id: int) -> UserProfile:
    result = await session.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


@router.get("/options", summary="职业/技术栈预设")
async def profile_options():
    return {"options": CAREER_OPTIONS}


@router.get("", response_model=ProfileRead, summary="我的画像")
async def get_profile(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    profile = await _load(session, current_user.id)
    return ProfileRead.model_validate(profile, from_attributes=True)


@router.put("", response_model=ProfileRead, summary="保存画像")
async def update_profile(
    body: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if body.job_role is not None and len(body.job_role) > _LEN_LIMIT["job_role"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="职业标识过长")
    if body.job_role_custom is not None and len(body.job_role_custom) > _LEN_LIMIT["job_role_custom"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="自定义职业过长")
    tags = body.tech_tags
    if tags is not None:
        if len(tags) > _TAG_LIMIT:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"技术栈最多选择 {_TAG_LIMIT} 项")
        tags = [str(t).strip()[:50] for t in tags if str(t).strip()]
    profile = await _load(session, current_user.id)
    if body.job_role is not None:
        profile.job_role = body.job_role or None
    if body.job_role_custom is not None:
        profile.job_role_custom = body.job_role_custom or None
    if tags is not None:
        profile.tech_tags = tags
    profile.updated_at = datetime.utcnow()
    session.add(profile)
    await session.commit()
    await session.refresh(profile)

    # 立即刷新该用户推荐（Embedding 不可用时任务层静默跳过）
    try:
        from app.tasks.recommend import refresh_user_now

        refresh_user_now.delay(current_user.id)
    except Exception:  # noqa: BLE001
        pass

    return ProfileRead.model_validate(profile, from_attributes=True)
