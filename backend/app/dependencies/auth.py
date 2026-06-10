"""Shared FastAPI dependencies for authentication."""

from typing import Optional

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.personalization_service import UserProfile


async def get_user_profile(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserProfile]:
    """Extract a ``UserProfile`` from the Bearer token if present.

    Returns ``None`` for anonymous users — downstream services will
    skip personalization in that case.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[len("Bearer "):].strip()
    payload = decode_access_token(token)
    if payload is None:
        return None

    user_id = int(payload.get("sub", 0))
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return None

    return UserProfile(
        role=user.role,
        college=user.college or "",
        interests=user.interests if isinstance(user.interests, list) else [],
    )
