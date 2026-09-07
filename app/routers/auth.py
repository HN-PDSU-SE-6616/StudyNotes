"""认证路由（注册时自动创建个人组织 + 默认项目）"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel, select

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.database import get_session
from app.models.user import (
    TokenResponse,
    User,
    UserLogin,
    UserRead,
    UserRegister,
    UserUpdate,
)
from app.services.bootstrap import create_personal_org

router = APIRouter(prefix="/auth", tags=["认证"])


async def _build_token(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user=UserRead.model_validate(user),
    )


@router.post("/register", response_model=TokenResponse, summary="用户注册")
async def register(body: UserRegister, session: AsyncSession = Depends(get_session)):
    """注册新用户：创建账号 + 个人组织与默认项目"""
    existing = await session.execute(
        select(User).where((User.username == body.username) | (User.email == body.email))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或邮箱已存在")

    user = User(
        username=body.username,
        email=body.email,
        display_name=body.display_name or body.username,
        hashed_password=hash_password(body.password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # 个人组织 + 默认项目（等价旧 Workspace）
    await create_personal_org(session, user)

    return await _build_token(user)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
async def login(body: UserLogin, session: AsyncSession = Depends(get_session)):
    """用户名密码登录"""
    result = await session.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账户已禁用")
    return await _build_token(user)


class RefreshTokenRequest(SQLModel):
    refresh_token: str


@router.post("/refresh", response_model=TokenResponse, summary="刷新令牌")
async def refresh(body: RefreshTokenRequest, session: AsyncSession = Depends(get_session)):
    """使用 refresh token 换取新的 access token"""
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的刷新令牌")

    result = await session.execute(select(User).where(User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return await _build_token(user)


@router.get("/me", response_model=UserRead, summary="获取当前用户")
async def get_me(current_user: User = Depends(get_current_user)):
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead, summary="更新个人资料")
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(current_user, key, value)
    current_user.updated_at = datetime.utcnow()
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return UserRead.model_validate(current_user)
