"""Auth API — user registration, login, and profile."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.schemas.user import (
    ApiResponse,
    LoginRequest,
    RegisterRequest,
)
from app.services.auth_service import (
    get_current_user,
    login,
    register,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ── Dependency: extract current user from Bearer token ───────

async def get_token_payload(
    authorization: Optional[str] = Header(None),
) -> dict:
    """Extract and validate JWT from the ``Authorization: Bearer <token>`` header.

    Raises ``HTTPException(401)`` if missing or invalid.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="请先登录")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="认证格式错误")

    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return payload


# ── POST /api/auth/register ──────────────────────────────────

@router.post("/register", response_model=ApiResponse)
async def auth_register(
    req: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """注册新用户。

    - **role** 可选值: undergraduate, graduate, teacher, job_seeker, visitor
    - **interests** 为 JSON 字符串数组，如 ``["AI","计算机"]``
    """
    return await register(db, req)


# ── POST /api/auth/login ─────────────────────────────────────

@router.post("/login", response_model=ApiResponse)
async def auth_login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """用户登录，返回 JWT access_token 和用户信息。

    后续请求在 ``Authorization`` header 中携带
    ``Bearer <access_token>`` 即可认证。
    """
    return await login(db, req)


# ── GET /api/auth/me ─────────────────────────────────────────

@router.get("/me", response_model=ApiResponse)
async def auth_me(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """获取当前登录用户信息（需 Authorization header）。"""
    return await get_current_user(db, payload)
