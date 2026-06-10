"""Search API endpoints.

All search routes live under ``/api/search``.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies.auth import get_user_profile
from app.schemas.search import (
    DocumentSearchParams,
    PagesSearchParams,
    PhraseSearchParams,
    SearchResponse,
    WildcardSearchParams,
)
from app.search.es_client import get_es_client
from app.services.personalization_service import UserProfile
from app.services.search_service import SearchService

router = APIRouter(prefix="/api/search", tags=["search"])


def _get_search_service() -> SearchService:
    """Provide a SearchService instance (singleton ES client)."""
    return SearchService(get_es_client())


# ── GET /api/search/pages ──────────────────────────────────────

@router.get("/pages", response_model=SearchResponse)
async def search_pages(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    source_site: str | None = Query(None, description="来源站点筛选"),
    category: str | None = Query(None, description="分类筛选"),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_get_search_service),
    profile: Optional[UserProfile] = Depends(get_user_profile),
) -> SearchResponse:
    """通用全文搜索 —— multi_match 跨 title/锚文本/正文。

    如果请求携带 ``Authorization: Bearer <token>``，结果将根据用户画像
    （角色、学院、兴趣）进行个性化加权排序。
    """
    params = PagesSearchParams(
        q=q,
        page=page,
        page_size=page_size,
        source_site=source_site,
        category=category,
    )
    return await svc.search_pages(db, params, profile=profile)


# ── GET /api/search/phrase ─────────────────────────────────────

@router.get("/phrase", response_model=SearchResponse)
async def search_phrase(
    q: str = Query(..., min_length=1, description="精确短语"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    source_site: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_get_search_service),
    profile: Optional[UserProfile] = Depends(get_user_profile),
) -> SearchResponse:
    """精确短语匹配 —— match_phrase 查询 title 和 content，支持个性化排序."""
    params = PhraseSearchParams(
        q=q,
        page=page,
        page_size=page_size,
        source_site=source_site,
        category=category,
    )
    return await svc.search_phrase(db, params, profile=profile)


# ── GET /api/search/wildcard ───────────────────────────────────

@router.get("/wildcard", response_model=SearchResponse)
async def search_wildcard(
    q: str = Query(..., min_length=1, description="通配符模式（支持 * 和 ?）"),
    field: str = Query("title", description="搜索字段: title 或 url"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    source_site: str | None = Query(None),
    category: str | None = Query(None),
    regex_filter: str | None = Query(None, description="可选 Python 正则后过滤"),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_get_search_service),
    profile: Optional[UserProfile] = Depends(get_user_profile),
) -> SearchResponse:
    """通配符搜索 —— 对 title 或 url 做 wildcard 查询，支持个性化排序和正则后过滤."""
    params = WildcardSearchParams(
        q=q,
        field=field,
        page=page,
        page_size=page_size,
        source_site=source_site,
        category=category,
        regex_filter=regex_filter,
    )
    return await svc.search_wildcard(db, params, profile=profile)


# ── GET /api/search/documents ──────────────────────────────────

@router.get("/documents", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    svc: SearchService = Depends(_get_search_service),
) -> SearchResponse:
    """文档搜索 —— 查询 nku_documents_v1 索引."""
    params = DocumentSearchParams(
        q=q,
        page=page,
        page_size=page_size,
    )
    return await svc.search_documents(db, params)
