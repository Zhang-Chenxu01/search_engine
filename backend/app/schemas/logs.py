"""Pydantic schemas for query log statistics API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


# ── Stats ────────────────────────────────────────────────────

class LogStats(BaseModel):
    total_queries: int = 0
    today_queries: int = 0
    user_count: int = 0
    fulltext_queries: int = 0
    document_queries: int = 0
    phrase_queries: int = 0
    wildcard_queries: int = 0


class LogStatsResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[LogStats] = None


# ── Hot queries ──────────────────────────────────────────────

class HotQueryItem(BaseModel):
    query: str
    count: int


class HotQueriesResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: list[HotQueryItem] = []


# ── Recent queries ──────────────────────────────────────────

class RecentQueryItem(BaseModel):
    id: int
    query_text: str
    query_type: str
    user_id: Optional[int] = None
    result_count: int = 0
    created_at: Optional[str] = None


class RecentQueriesResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: list[RecentQueryItem] = []
    total: int = 0


# ── Query type distribution ─────────────────────────────────

class TypeDistribution(BaseModel):
    fulltext: int = 0
    document: int = 0
    phrase: int = 0
    wildcard: int = 0


class TypeDistributionResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[TypeDistribution] = None


# ── Daily trend ─────────────────────────────────────────────

class DailyTrendItem(BaseModel):
    date: str
    count: int


class DailyTrendResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: list[DailyTrendItem] = []
