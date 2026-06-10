"""Pydantic schemas for user registration, login, and profile."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

VALID_ROLES = {"undergraduate", "graduate", "teacher", "job_seeker", "visitor"}


# ── Request schemas ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Payload for POST /api/auth/register."""
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role: str = Field("visitor", description=f"角色: {', '.join(sorted(VALID_ROLES))}")
    college: str = Field("", max_length=128, description="学院")
    interests: list[str] = Field(default_factory=list, description="兴趣标签列表")


class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


# ── Response schemas ──────────────────────────────────────────

class UserInfo(BaseModel):
    """Public user profile."""
    id: int
    username: str
    role: str
    college: str = ""
    interests: list = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """Returned on successful login."""
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


# ── Generic wrappers ──────────────────────────────────────────

class ApiResponse(BaseModel):
    """Thin wrapper matching project convention ``code / data / message``."""
    code: int = 0
    data: Optional[object] = None
    message: str = "ok"
