"""Recommendation API — query suggestions, related pages, and hot trends."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_user_profile
from app.schemas.search import SearchResponse
from app.search.es_client import get_es_client
from app.services.personalization_service import UserProfile
from app.services.recommend_service import (
    get_hot_queries,
    get_related_pages,
    get_suggestions,
)

router = APIRouter(prefix="/api/recommend", tags=["recommend"])


# ── GET /api/recommend/suggest ────────────────────────────────

@router.get("/suggest")
async def suggest(
    q: str = Query(..., min_length=1, description="查询前缀"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """查询建议 —— 基于历史查询日志的前缀匹配。

    返回最多 10 个建议词，按查询次数降序。
    """
    items = await get_suggestions(db, q)
    return {
        "code": 0,
        "data": items,
        "message": "ok",
    }


# ── GET /api/recommend/related ────────────────────────────────

@router.get("/related", response_model=SearchResponse)
async def related(
    q: str = Query(..., min_length=1, description="当前查询词"),
    db: AsyncSession = Depends(get_db),
    profile: Optional[UserProfile] = Depends(get_user_profile),
) -> SearchResponse:
    """相关内容推荐 —— 在 ES 中检索与 *q* 相关的页面。

    若用户已登录，结果会根据用户画像进行个性化加权。

    FUTURE: 可切换为 ``more_like_this`` 查询实现语义相似推荐。
    """
    es = get_es_client()
    items = await get_related_pages(es, db, q, profile=profile)
    return SearchResponse(
        data=items,
        total=len(items),
        page=1,
        page_size=len(items),
    )


# ── GET /api/recommend/hot ────────────────────────────────────

@router.get("/hot")
async def hot(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """热门查询 —— 返回最近 24 小时内的热门搜索词，按查询次数降序。"""
    items = await get_hot_queries(db, hours=24, limit=10)
    return {
        "code": 0,
        "data": items,
        "message": "ok",
    }
