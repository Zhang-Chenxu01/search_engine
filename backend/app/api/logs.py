"""Query log statistics API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.logs import (
    DailyTrendResponse,
    HotQueriesResponse,
    LogStatsResponse,
    RecentQueriesResponse,
    TypeDistributionResponse,
)
from app.services.logs_service import (
    get_daily_trend,
    get_hot_queries,
    get_recent,
    get_stats,
    get_type_distribution,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("/stats", response_model=LogStatsResponse)
async def log_stats(
    db: AsyncSession = Depends(get_db),
) -> LogStatsResponse:
    """Dashboard 统计概览：总查询数、今日查询数、用户数、各类型查询数。"""
    data = await get_stats(db)
    return LogStatsResponse(data=data)


@router.get("/hot-queries", response_model=HotQueriesResponse)
async def log_hot_queries(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> HotQueriesResponse:
    """热门查询词 Top-N。"""
    data = await get_hot_queries(db, limit)
    return HotQueriesResponse(data=data)


@router.get("/recent", response_model=RecentQueriesResponse)
async def log_recent(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> RecentQueriesResponse:
    """最近查询记录。"""
    items, total = await get_recent(db, limit)
    return RecentQueriesResponse(data=items, total=total)


@router.get("/query-type-distribution", response_model=TypeDistributionResponse)
async def log_type_distribution(
    db: AsyncSession = Depends(get_db),
) -> TypeDistributionResponse:
    """查询类型分布。"""
    data = await get_type_distribution(db)
    return TypeDistributionResponse(data=data)


@router.get("/daily-trend", response_model=DailyTrendResponse)
async def log_daily_trend(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> DailyTrendResponse:
    """最近 N 天的每日查询趋势。"""
    data = await get_daily_trend(db, days)
    return DailyTrendResponse(data=data)
