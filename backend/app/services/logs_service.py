"""Log statistics service — aggregate queries against query_logs table."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_log import QueryLog
from app.models.user import User
from app.schemas.logs import (
    DailyTrendItem,
    HotQueryItem,
    LogStats,
    RecentQueryItem,
    TypeDistribution,
)


async def get_stats(db: AsyncSession) -> LogStats:
    """Aggregate statistics for the dashboard."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Total queries
    total_r = await db.execute(select(func.count(QueryLog.id)))
    total = total_r.scalar_one()

    # Today queries
    today_r = await db.execute(
        select(func.count(QueryLog.id)).where(QueryLog.created_at >= today_start)
    )
    today = today_r.scalar_one()

    # User count
    user_r = await db.execute(select(func.count(User.id)))
    users = user_r.scalar_one()

    # Per-type counts
    def _count(qtype: str) -> int:
        return 0  # placeholder — real counts below

    type_counts: dict[str, int] = {}
    for qtype in ("fulltext", "document", "phrase", "wildcard"):
        r = await db.execute(
            select(func.count(QueryLog.id)).where(QueryLog.query_type == qtype)
        )
        type_counts[qtype] = r.scalar_one()

    return LogStats(
        total_queries=total,
        today_queries=today,
        user_count=users,
        fulltext_queries=type_counts.get("fulltext", 0),
        document_queries=type_counts.get("document", 0),
        phrase_queries=type_counts.get("phrase", 0),
        wildcard_queries=type_counts.get("wildcard", 0),
    )


async def get_hot_queries(db: AsyncSession, limit: int = 10) -> list[HotQueryItem]:
    """Top-N queries by frequency (fulltext + phrase only)."""
    r = await db.execute(
        select(QueryLog.query_text, func.count(QueryLog.id).label("cnt"))
        .where(QueryLog.query_type.in_(["fulltext", "phrase"]))
        .group_by(QueryLog.query_text)
        .order_by(text("cnt DESC"))
        .limit(limit)
    )
    rows = r.all()
    return [HotQueryItem(query=row.query_text, count=row.cnt) for row in rows]  # type: ignore[union-attr]


async def get_recent(db: AsyncSession, limit: int = 20) -> tuple[list[RecentQueryItem], int]:
    """Most recent query log entries."""
    total_r = await db.execute(select(func.count(QueryLog.id)))
    total = total_r.scalar_one()

    r = await db.execute(
        select(QueryLog)
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
    )
    rows = r.scalars().all()

    items = [
        RecentQueryItem(
            id=log.id,
            query_text=log.query_text,
            query_type=log.query_type,
            user_id=log.user_id,
            result_count=log.result_count,
            created_at=log.created_at.isoformat() if log.created_at else None,
        )
        for log in rows
    ]
    return items, total


async def get_type_distribution(db: AsyncSession) -> TypeDistribution:
    """Count of each query_type."""
    r = await db.execute(
        select(QueryLog.query_type, func.count(QueryLog.id).label("cnt"))
        .group_by(QueryLog.query_type)
    )
    dist: dict[str, int] = {"fulltext": 0, "document": 0, "phrase": 0, "wildcard": 0}
    for row in r.all():
        dist[row.query_type] = row.cnt  # type: ignore[index]
    return TypeDistribution(**dist)


async def get_daily_trend(db: AsyncSession, days: int = 7) -> list[DailyTrendItem]:
    """Query counts grouped by day for the last *days* days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    r = await db.execute(
        select(
            func.date(QueryLog.created_at).label("d"),
            func.count(QueryLog.id).label("cnt"),
        )
        .where(QueryLog.created_at >= since)
        .group_by(text("d"))
        .order_by(text("d ASC"))
    )
    rows = r.all()
    return [DailyTrendItem(date=str(row.d), count=row.cnt) for row in rows]  # type: ignore[union-attr]
