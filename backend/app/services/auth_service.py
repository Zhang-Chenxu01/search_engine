"""Auth service — registration, login, and user-profile retrieval."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    ApiResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
    VALID_ROLES,
)


async def register(db: AsyncSession, req: RegisterRequest) -> ApiResponse:
    """Register a new user.

    Returns ``ApiResponse`` with code=0 on success, or code=1 with error message.
    """
    # ── Validate role ─────────────────────────────────────────
    if req.role not in VALID_ROLES:
        return ApiResponse(
            code=1,
            message=f"无效的角色。可选值: {', '.join(sorted(VALID_ROLES))}",
        )

    # ── Check duplicate ───────────────────────────────────────
    existing = await db.execute(
        select(func.count(User.id)).where(User.username == req.username)
    )
    count = existing.scalar_one()
    if count > 0:
        return ApiResponse(code=1, message="用户名已被注册")

    # ── Create user ───────────────────────────────────────────
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role=req.role,
        college=req.college,
        interests=req.interests,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # fetch server-generated defaults (created_at, id)

    return ApiResponse(
        data=UserInfo.model_validate(user),
        message="注册成功",
    )


async def login(db: AsyncSession, req: LoginRequest) -> ApiResponse:
    """Authenticate a user and return a JWT token.

    Returns ``ApiResponse`` with ``TokenResponse`` in ``data`` on success.
    """
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user: Optional[User] = result.scalar_one_or_none()

    if user is None:
        return ApiResponse(code=1, message="用户名或密码错误")

    if not verify_password(req.password, user.password_hash):
        return ApiResponse(code=1, message="用户名或密码错误")

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
    )

    return ApiResponse(
        data=TokenResponse(
            access_token=token,
            user=UserInfo.model_validate(user),
        ),
        message="登录成功",
    )


async def get_current_user(
    db: AsyncSession,
    token_payload: dict,
) -> ApiResponse:
    """Return user info for the validated JWT payload."""
    user_id = int(token_payload.get("sub", 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        return ApiResponse(code=1, message="用户不存在")

    return ApiResponse(
        data=UserInfo.model_validate(user),
    )
