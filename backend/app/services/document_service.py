"""Document service — ES search + MySQL detail for attachments."""

import asyncio
import re
from datetime import datetime
from typing import Any, Optional

from elasticsearch import Elasticsearch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.models.page import Page
from app.models.query_log import QueryLog
from app.schemas.document import (
    DocumentDetail,
    DocumentDetailResponse,
    DocumentSearchItem,
    DocumentSearchParams,
    DocumentSearchResponse,
)
from app.search.query_builder import DOCUMENTS_INDEX

_STRIP_HTML_RE = re.compile(r"<(?!\s*/?\s*em\b)[^>]*>", re.IGNORECASE)


def _sanitise_highlight(text: str) -> str:
    return _STRIP_HTML_RE.sub("", text)


# ── Highlight config borrowed from query_builder ──────────────
DOCUMENTS_HIGHLIGHT: dict[str, Any] = {
    "fields": {
        "file_name": {
            "number_of_fragments": 0,
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
        },
        "file_text": {
            "fragment_size": 150,
            "number_of_fragments": 3,
            "no_match_size": 100,
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
        },
    },
}


# ── Helpers ───────────────────────────────────────────────────

def _parse_document_hit(hit: dict[str, Any]) -> DocumentSearchItem:
    """Convert an ES document hit into a DocumentSearchItem."""
    src: dict[str, Any] = hit.get("_source", {})
    hl: dict[str, list[str]] = hit.get("highlight", {})

    file_name_hls = hl.get("file_name", [])
    raw_name = file_name_hls[0] if file_name_hls else src.get("file_name", "")
    display_name = _sanitise_highlight(raw_name)

    snippet = ""
    text_hls = hl.get("file_text", [])
    if text_hls:
        snippet = " ... ".join(_sanitise_highlight(h) for h in text_hls)

    return DocumentSearchItem(
        attachment_id=src.get("attachment_id", 0),
        file_name=display_name,
        file_type=src.get("file_type", ""),
        file_url=src.get("file_url", ""),
        parent_title=src.get("parent_title", ""),
        parent_url=src.get("parent_url", ""),
        parent_page_id=src.get("parent_page_id"),
        snippet=snippet,
        crawl_time=src.get("crawl_time"),
        score=hit.get("_score"),
        highlight=hl if hl else None,
    )


async def _log_query(
    db: AsyncSession,
    query_text: str,
    query_type: str,
    result_count: int,
    filters: Optional[dict[str, Any]] = None,
) -> None:
    log = QueryLog(
        query_text=query_text,
        query_type=query_type,
        result_count=result_count,
        filters=filters,
    )
    db.add(log)
    await db.commit()


# ── Service functions ─────────────────────────────────────────

async def search_documents(
    es: Elasticsearch,
    db: AsyncSession,
    params: DocumentSearchParams,
) -> DocumentSearchResponse:
    """Full-text search across ``nku_documents_v1``."""
    from_ = (params.page - 1) * params.page_size

    must_clauses: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": params.q,
                "fields": ["file_name^3", "file_text^1", "parent_title^2"],
                "type": "best_fields",
            }
        }
    ]
    filter_clauses: list[dict[str, Any]] = []
    if params.file_type:
        filter_clauses.append({"term": {"file_type": params.file_type}})

    body: dict[str, Any] = {
        "query": {
            "bool": {
                "must": must_clauses,
            }
        },
        "highlight": DOCUMENTS_HIGHLIGHT,
        "from": from_,
        "size": params.page_size,
        "_source": [
            "attachment_id", "file_url", "file_name", "file_type",
            "parent_page_id", "parent_title", "parent_url", "crawl_time",
        ],
    }
    if filter_clauses:
        body["query"]["bool"]["filter"] = filter_clauses

    result = await asyncio.to_thread(es.search, index=DOCUMENTS_INDEX, body=body)

    total: int = (
        result["hits"]["total"]["value"]
        if isinstance(result["hits"]["total"], dict)
        else result["hits"]["total"]  # type: ignore[index]
    )
    items = [_parse_document_hit(h) for h in result["hits"]["hits"]]

    filters_log: Optional[dict[str, Any]] = None
    if params.file_type:
        filters_log = {"file_type": params.file_type}
    await _log_query(db, params.q, "document", total, filters_log)

    return DocumentSearchResponse(
        data=items,
        total=total,
        page=params.page,
        page_size=params.page_size,
    )


async def get_document_detail(
    es: Elasticsearch,
    db: AsyncSession,
    document_id: int,
) -> DocumentDetailResponse:
    """Return full metadata for a single attachment by DB id."""
    # ── MySQL lookup ──────────────────────────────────────────
    result = await db.execute(
        select(Attachment).where(Attachment.id == document_id)
    )
    attachment = result.scalar_one_or_none()

    if attachment is None:
        return DocumentDetailResponse(code=404, message="Document not found")

    # ── Parent page title ─────────────────────────────────────
    parent_title = ""
    if attachment.parent_page_id:
        page_result = await db.execute(
            select(Page.title).where(Page.id == attachment.parent_page_id)
        )
        pt = page_result.scalar_one_or_none()
        if pt:
            parent_title = pt

    # ── Text preview from ES ──────────────────────────────────
    text_preview = ""
    text_total_length = 0
    try:
        es_result = await asyncio.to_thread(
            es.search,
            index=DOCUMENTS_INDEX,
            body={
                "query": {"term": {"attachment_id": document_id}},
                "_source": ["file_text"],
                "size": 1,
            },
        )
        hits = es_result["hits"]["hits"]
        if hits:
            full_text: str = hits[0]["_source"].get("file_text", "") or ""
            text_total_length = len(full_text)
            text_preview = full_text[:2000]  # first 2000 chars
    except Exception:
        pass

    detail = DocumentDetail(
        id=attachment.id,
        file_name=attachment.file_name,
        file_type=attachment.file_type,
        file_url=attachment.file_url,
        local_path=attachment.local_path,
        parent_page_id=attachment.parent_page_id,
        parent_url=attachment.parent_url,
        parent_title=parent_title,
        parse_status=attachment.parse_status,
        crawl_time=attachment.crawl_time.isoformat() if attachment.crawl_time else None,
        created_at=attachment.created_at.isoformat() if attachment.created_at else None,
        text_preview=text_preview,
        text_total_length=text_total_length,
    )

    return DocumentDetailResponse(data=detail)
