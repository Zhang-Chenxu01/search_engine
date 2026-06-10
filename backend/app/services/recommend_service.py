"""Recommendation service — query suggestions, related content, and hot queries.

All algorithms are intentionally simple so results are explainable.
Extension points (e.g. ``more_like_this``) are marked with ``FUTURE:``.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from elasticsearch import Elasticsearch
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_log import QueryLog
from app.schemas.search import SearchResultItem
from app.services.personalization_service import UserProfile, re_rank
from app.search.query_builder import PAGES_INDEX


# ── Helper types ──────────────────────────────────────────────

class SuggestItem(dict):
    """Query suggestion item — behaves like ``{"query":..., "count":...}``."""
    def __init__(self, query: str, count: int) -> None:
        super().__init__(query=query, count=count)


class HotItem(dict):
    """Hot trend item."""
    def __init__(self, query: str, count: int) -> None:
        super().__init__(query=query, count=count)


# ── Suggestion: prefix search in query_logs ──────────────────

async def get_suggestions(
    db: AsyncSession,
    q: str,
    limit: int = 10,
) -> list[SuggestItem]:
    """Return up to *limit* query suggestions by prefix-matching *q*
    in historical ``query_logs``, ranked by frequency descending."""
    prefix = q.strip()
    if not prefix:
        return []

    stmt = (
        select(QueryLog.query_text, func.count(QueryLog.id).label("cnt"))
        .where(QueryLog.query_text.like(f"{prefix}%"))
        .group_by(QueryLog.query_text)
        .order_by(desc("cnt"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [SuggestItem(query=row.query_text, count=row.cnt) for row in rows]  # type: ignore[union-attr]


# ── Related pages ─────────────────────────────────────────────

async def get_related_pages(
    es: Elasticsearch,
    db: AsyncSession,
    q: str,
    profile: Optional[UserProfile] = None,
    limit: int = 5,
) -> list[SearchResultItem]:
    """Return up to *limit* pages related to *q*.

    Uses a simple ``multi_match`` on title/content; when a *profile* is
    supplied the results are re-ranked with personalised preferences.

    FUTURE: replace with ``more_like_this`` query on indexed document
    vectors for semantic similarity.
    """
    body = {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["title^3", "content^1", "anchor_text^2"],
                "type": "best_fields",
            }
        },
        "size": limit,
        "_source": [
            "page_id", "url", "title", "source_site", "category",
            "publish_time", "snapshot_path",
        ],
    }

    result = await asyncio.to_thread(es.search, index=PAGES_INDEX, body=body)

    items: list[SearchResultItem] = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        items.append(SearchResultItem(
            page_id=src.get("page_id", 0),
            url=src.get("url", ""),
            title=src.get("title", ""),
            source_site=src.get("source_site", ""),
            category=src.get("category", ""),
            publish_time=src.get("publish_time"),
            snapshot_path=src.get("snapshot_path", ""),
            es_score=hit.get("_score"),
        ))

    # Personalize if user profile is available
    items = re_rank(items, profile)

    return items


# ── Hot queries ───────────────────────────────────────────────

async def get_hot_queries(
    db: AsyncSession,
    hours: int = 24,
    limit: int = 10,
) -> list[HotItem]:
    """Return the most frequent queries from the last *hours*.

    Only ``fulltext`` and ``phrase`` type queries are counted;
    ``wildcard`` and ``document`` are excluded because they tend
    to be technical patterns rather than natural-language queries.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    stmt = (
        select(QueryLog.query_text, func.count(QueryLog.id).label("cnt"))
        .where(
            QueryLog.created_at >= since,
            QueryLog.query_type.in_(["fulltext", "phrase"]),
        )
        .group_by(QueryLog.query_text)
        .order_by(desc("cnt"))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [HotItem(query=row.query_text, count=row.cnt) for row in rows]  # type: ignore[union-attr]
