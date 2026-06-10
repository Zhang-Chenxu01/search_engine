"""Pydantic schemas for document search and detail endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────

class DocumentSearchParams(BaseModel):
    """Query parameters for document search."""
    q: str = Field(..., min_length=1, description="Search query")
    file_type: Optional[str] = Field(None, description="Filter by type: pdf, docx, xlsx…")
    page: int = Field(1, ge=1)
    page_size: int = Field(10, ge=1, le=100)


# ── Response items ───────────────────────────────────────────

class DocumentSearchItem(BaseModel):
    """A single document search result."""
    attachment_id: int
    file_name: str
    file_type: str = ""
    file_url: str = ""
    parent_title: str = ""
    parent_url: str = ""
    parent_page_id: Optional[int] = None
    snippet: str = ""
    crawl_time: Optional[str] = None
    score: Optional[float] = None
    highlight: Optional[dict[str, list[str]]] = None


class DocumentDetail(BaseModel):
    """Full metadata for a single attachment."""
    id: int
    file_name: str
    file_type: str = ""
    file_url: str = ""
    local_path: Optional[str] = None
    parent_page_id: Optional[int] = None
    parent_url: str = ""
    parent_title: str = ""
    parse_status: str = "pending"
    crawl_time: Optional[str] = None
    created_at: Optional[str] = None
    text_preview: str = ""
    text_total_length: int = 0


# ── Unified response wrapper ─────────────────────────────────

class DocumentSearchResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: list[DocumentSearchItem] = []
    total: int = 0
    page: int = 1
    page_size: int = 10


class DocumentDetailResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[DocumentDetail] = None
