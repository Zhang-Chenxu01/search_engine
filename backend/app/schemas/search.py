"""Pydantic schemas for search requests and responses."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────

class PagesSearchParams(BaseModel):
    """Query parameters for general page search."""
    q: str = Field(..., min_length=1, description="Search query string")
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(10, ge=1, le=100, description="Results per page")
    source_site: Optional[str] = Field(None, description="Filter by source site")
    category: Optional[str] = Field(None, description="Filter by category")


class PhraseSearchParams(BaseModel):
    """Query parameters for exact phrase match search."""
    q: str = Field(..., min_length=1, description="Exact phrase to match")
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    source_site: Optional[str] = Field(None)
    category: Optional[str] = Field(None)


class WildcardSearchParams(BaseModel):
    """Query parameters for wildcard search."""
    q: str = Field(..., min_length=1, description="Wildcard pattern (* or ?)")
    field: str = Field("title", description="Field: title or url")
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)
    source_site: Optional[str] = Field(None)
    category: Optional[str] = Field(None)
    regex_filter: Optional[str] = Field(None, description="Optional Python regex post-filter")


class DocumentSearchParams(BaseModel):
    """Query parameters for document search."""
    q: str = Field(..., min_length=1)
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


# ── Response items ───────────────────────────────────────────

class SearchResultItem(BaseModel):
    """A single search result from the pages index."""
    page_id: int
    url: str
    title: str
    snippet: str = ""
    source_site: str = ""
    category: str = ""
    publish_time: Optional[str] = None
    snapshot_path: str = ""
    # Decomposed scores
    bm25_score: Optional[float] = None       # ES BM25 relevance
    vsm_score: float = 0.0                    # TF-IDF cosine similarity
    pagerank_score: float = 0.0               # link analysis (reserved)
    personalization_score: float = 0.0         # user preference boost
    final_score: Optional[float] = None        # 0.60*BM25 + 0.20*VSM + 0.15*PR + 0.05*PERS
    highlight: Optional[dict[str, list[str]]] = None


class DocumentResultItem(BaseModel):
    """A single search result from the documents index."""
    attachment_id: int
    file_url: str
    file_name: str
    file_type: str = ""
    parent_page_id: Optional[int] = None
    parent_title: str = ""
    parent_url: str = ""
    crawl_time: Optional[str] = None
    score: Optional[float] = None
    highlight: Optional[dict[str, list[str]]] = None


# ── Unified response wrapper ─────────────────────────────────

class SearchResponse(BaseModel):
    """Unified API response format."""
    code: int = 0
    data: Any = None
    message: str = "ok"
    total: int = 0
    page: int = 1
    page_size: int = 10
