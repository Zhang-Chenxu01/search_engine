"""Search service — orchestrate ES queries, DB logging, and personalization.

Route handlers delegate here; no raw ES DSL in the API layer.
"""

import asyncio
import logging
import re
from typing import Any, Optional

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError, ConnectionError as ESConnectionError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query_log import QueryLog
from app.schemas.search import (
    DocumentResultItem,
    PagesSearchParams,
    PhraseSearchParams,
    SearchResponse,
    SearchResultItem,
    WildcardSearchParams,
    DocumentSearchParams,
)
from app.search.query_builder import (
    PAGES_INDEX,
    DOCUMENTS_INDEX,
    build_multi_match_query,
    build_match_phrase_query,
    build_wildcard_query,
    build_document_query,
)
from app.services.personalization_service import (
    UserProfile,
    compute_preference_score,
)
from app.services.vsm_reranker import VSMReranker

logger = logging.getLogger(__name__)

# ── Score weights for the final ranking formula ───────────────
W_BM25   = 0.60
W_VSM    = 0.20
W_PR     = 0.15   # PageRank (reserved)
W_PERS   = 0.05   # Personalization

_vsm = VSMReranker()

# Regex to strip HTML tags except <em> (used in ES highlights)
_STRIP_HTML_RE = re.compile(r"<(?!\s*/?\s*em\b)[^>]*>", re.IGNORECASE)


def _sanitise_highlight(text: str) -> str:
    """Remove all HTML tags from *text* except ``<em>`` and ``</em>``."""
    return _STRIP_HTML_RE.sub("", text)


def _parse_page_hit(hit: dict[str, Any]) -> SearchResultItem:
    """Convert an ES page hit into a SearchResultItem, including highlight."""
    src: dict[str, Any] = hit.get("_source", {})
    highlight: dict[str, list[str]] = hit.get("highlight", {})

    # Build snippet from highlight or first 150 chars of content
    snippet = ""
    content_hls = highlight.get("content", [])
    if content_hls:
        snippet = " ... ".join(_sanitise_highlight(h) for h in content_hls)
    else:
        # No highlight returned; we don't store content in _source for brevity
        # but we can show the first highlight from title or just leave empty
        pass

    # Highlighted title (use highlighted version if available)
    title_hls = highlight.get("title", [])
    raw_title = title_hls[0] if title_hls else src.get("title", "")
    display_title = _sanitise_highlight(raw_title)

    return SearchResultItem(
        page_id=src.get("page_id", 0),
        url=src.get("url", ""),
        title=display_title,
        snippet=snippet,
        source_site=src.get("source_site", ""),
        category=src.get("category", ""),
        publish_time=src.get("publish_time"),
        snapshot_path=src.get("snapshot_path", ""),
        bm25_score=hit.get("_score"),
        highlight=highlight if highlight else None,
    )


def _parse_document_hit(hit: dict[str, Any]) -> DocumentResultItem:
    """Convert an ES document hit into a DocumentResultItem."""
    src: dict[str, Any] = hit.get("_source", {})
    highlight: dict[str, list[str]] = hit.get("highlight", {})

    file_name_hls = highlight.get("file_name", [])
    display_name = file_name_hls[0] if file_name_hls else src.get("file_name", "")

    return DocumentResultItem(
        attachment_id=src.get("attachment_id", 0),
        file_url=src.get("file_url", ""),
        file_name=display_name,
        file_type=src.get("file_type", ""),
        parent_page_id=src.get("parent_page_id"),
        parent_title=src.get("parent_title", ""),
        parent_url=src.get("parent_url", ""),
        crawl_time=src.get("crawl_time"),
        bm25_score=hit.get("_score"),
        highlight=highlight if highlight else None,
    )


async def _safe_log(
    db: AsyncSession,
    query_text: str,
    query_type: str,
    result_count: int,
    filters: Optional[dict[str, Any]] = None,
) -> None:
    """Persist a search query to the query_logs table (best-effort)."""
    try:
        log = QueryLog(
            query_text=query_text,
            query_type=query_type,
            result_count=result_count,
            filters=filters,
        )
        db.add(log)
        await db.commit()
    except Exception:
        logger.warning("Failed to write query log for [%s] %s", query_type, query_text,
                       exc_info=True)


class SearchService:
    """Encapsulates search logic; instantiated with an ES client."""

    def __init__(self, es_client: Elasticsearch) -> None:
        self.es = es_client

    # ── Scoring helpers ─────────────────────────────────────────

    def _fetch_content_for_vsm(self, items: list[SearchResultItem]) -> list[dict[str, str]]:
        """Fetch ``content`` and ``anchor_text`` from ES for VSM scoring.

        These fields are NOT in ``_source`` by default (to keep responses small),
        so we do a lightweight multi-get against the pages index.
        """
        if not items:
            return []
        docs = []
        try:
            result = self.es.mget(
                index=PAGES_INDEX,
                body={"ids": [str(it.page_id) for it in items]},
                _source=["content", "anchor_text"],
            )
            for doc in result.get("docs", []):
                src = doc.get("_source", {}) if doc.get("found") else {}
                docs.append({
                    "title": src.get("title", ""),
                    "content": src.get("content", ""),
                    "anchor_text": src.get("anchor_text", ""),
                })
        except Exception as exc:
            logger.warning("VSM mget failed, using empty content: %s", exc)
            docs = [{"title": "", "content": "", "anchor_text": ""} for _ in items]
        return docs

    def _apply_ranking_formula(
        self,
        items: list[SearchResultItem],
        vsm_scores: list[float],
        profile: Optional[UserProfile],
    ) -> list[SearchResultItem]:
        """Compute final_score for each item using the weighted formula.

        final = 0.60·BM25 + 0.20·VSM + 0.15·PageRank + 0.05·Personalization
        """
        for i, it in enumerate(items):
            bm25 = it.bm25_score or 0.0
            vsm = vsm_scores[i] if i < len(vsm_scores) else 0.0
            pr = it.pagerank_score or 0.0
            pers = compute_preference_score(it, profile) if profile else 0.0

            it.vsm_score = round(vsm, 4)
            it.personalization_score = round(pers, 4)
            it.final_score = round(
                W_BM25 * bm25 + W_VSM * vsm + W_PR * pr + W_PERS * pers,
                4,
            )

        # Sort descending by final_score, then bm25_score as tie-breaker
        items.sort(key=lambda x: (x.final_score or 0, x.bm25_score or 0), reverse=True)
        return items

    # ── Pages search (multi_match) ─────────────────────────────

    async def search_pages(
        self,
        db: AsyncSession,
        params: PagesSearchParams,
        profile: Optional[UserProfile] = None,
    ) -> SearchResponse:
        """Full-text search with BM25 + VSM + personalised re-ranking.

        1. ES BM25 recall (top-k)
        2. TF-IDF cosine similarity (VSM) on title/content/anchor
        3. Weighted formula: 0.60·BM25 + 0.20·VSM + 0.15·PR + 0.05·PERS
        """
        from_ = (params.page - 1) * params.page_size
        body = build_multi_match_query(
            q=params.q,
            source_site=params.source_site,
            category=params.category,
            from_=from_,
            size=params.page_size,
        )

        try:
            result = await asyncio.to_thread(
                self.es.search, index=PAGES_INDEX, body=body
            )
        except (ApiError, ESConnectionError) as exc:
            logger.error("ES search_pages failed: %s", exc)
            return SearchResponse(data=[], total=0, page=params.page, page_size=params.page_size)

        total: int = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]  # type: ignore[index]
        items = [_parse_page_hit(h) for h in result["hits"]["hits"]]

        # ── VSM reranking ─────────────────────────────────────
        vsm_docs = self._fetch_content_for_vsm(items)
        vsm_scores = _vsm.rerank(params.q, vsm_docs)

        # ── Apply ranking formula ─────────────────────────────
        items = self._apply_ranking_formula(items, vsm_scores, profile)

        filters_log: Optional[dict[str, Any]] = None
        if params.source_site or params.category:
            filters_log = {"source_site": params.source_site, "category": params.category}
        await _safe_log(db, params.q, "fulltext", total, filters_log)

        return SearchResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ── Phrase search ──────────────────────────────────────────

    async def search_phrase(
        self,
        db: AsyncSession,
        params: PhraseSearchParams,
        profile: Optional[UserProfile] = None,
    ) -> SearchResponse:
        """Exact phrase match search, with optional personalization."""
        from_ = (params.page - 1) * params.page_size
        body = build_match_phrase_query(
            q=params.q,
            source_site=params.source_site,
            category=params.category,
            from_=from_,
            size=params.page_size,
        )

        try:
            result = await asyncio.to_thread(
                self.es.search, index=PAGES_INDEX, body=body
            )
        except (ApiError, ESConnectionError) as exc:
            logger.error("ES search_phrase failed: %s", exc)
            return SearchResponse(data=[], total=0, page=params.page, page_size=params.page_size)

        total: int = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]  # type: ignore[index]
        items = [_parse_page_hit(h) for h in result["hits"]["hits"]]

        vsm_docs = self._fetch_content_for_vsm(items)
        vsm_scores = _vsm.rerank(params.q, vsm_docs)
        items = self._apply_ranking_formula(items, vsm_scores, profile)

        filters_log: Optional[dict[str, Any]] = None
        if params.source_site or params.category:
            filters_log = {"source_site": params.source_site, "category": params.category}
        await _safe_log(db, params.q, "phrase", total, filters_log)

        return SearchResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ── Wildcard search ────────────────────────────────────────

    async def search_wildcard(
        self,
        db: AsyncSession,
        params: WildcardSearchParams,
        profile: Optional[UserProfile] = None,
    ) -> SearchResponse:
        """Wildcard / pattern search with optional regex post-filter and personalization."""
        from_ = (params.page - 1) * params.page_size
        body = build_wildcard_query(
            q=params.q,
            field=params.field,
            source_site=params.source_site,
            category=params.category,
            from_=from_,
            size=params.page_size,
        )

        try:
            result = await asyncio.to_thread(
                self.es.search, index=PAGES_INDEX, body=body
            )
        except (ApiError, ESConnectionError) as exc:
            logger.error("ES search_wildcard failed: %s", exc)
            return SearchResponse(data=[], total=0, page=params.page, page_size=params.page_size)

        total: int = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]  # type: ignore[index]
        items = [_parse_page_hit(h) for h in result["hits"]["hits"]]

        # Optional Python regex post-filter
        if params.regex_filter:
            try:
                pattern = re.compile(params.regex_filter)
            except re.error:
                pattern = re.compile(re.escape(params.regex_filter))
            if params.field == "title":
                items = [it for it in items if pattern.search(it.title)]
            elif params.field == "url":
                items = [it for it in items if pattern.search(it.url)]
            total = len(items)

        vsm_docs = self._fetch_content_for_vsm(items)
        vsm_scores = _vsm.rerank(params.q, vsm_docs)
        items = self._apply_ranking_formula(items, vsm_scores, profile)

        filters_log: Optional[dict[str, Any]] = {
            "field": params.field,
            "regex_filter": params.regex_filter,
        }
        if params.source_site or params.category:
            filters_log["source_site"] = params.source_site
            filters_log["category"] = params.category
        await _safe_log(db, params.q, "wildcard", total, filters_log)

        return SearchResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ── Document search ────────────────────────────────────────

    async def search_documents(
        self,
        db: AsyncSession,
        params: DocumentSearchParams,
        profile: Optional[UserProfile] = None,
    ) -> SearchResponse:
        """Search across indexed documents.  Personalization is not applied
        to document search (documents lack the category/snippet fields)."""
        from_ = (params.page - 1) * params.page_size
        body = build_document_query(
            q=params.q,
            from_=from_,
            size=params.page_size,
        )

        try:
            result = await asyncio.to_thread(
                self.es.search, index=DOCUMENTS_INDEX, body=body
            )
        except (ApiError, ESConnectionError) as exc:
            logger.error("ES search_documents failed: %s", exc)
            return SearchResponse(data=[], total=0, page=params.page, page_size=params.page_size)

        total: int = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]  # type: ignore[index]
        items = [_parse_document_hit(h) for h in result["hits"]["hits"]]

        await _safe_log(db, params.q, "document", total)

        return SearchResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )

    # ── Document search ────────────────────────────────────────

    async def search_documents(
        self,
        db: AsyncSession,
        params: DocumentSearchParams,
        profile: Optional[UserProfile] = None,
    ) -> SearchResponse:
        """Search across indexed documents.  Personalization is not applied
        to document search (documents lack the category/snippet fields)."""
        from_ = (params.page - 1) * params.page_size
        body = build_document_query(
            q=params.q,
            from_=from_,
            size=params.page_size,
        )

        result = await asyncio.to_thread(
            self.es.search, index=DOCUMENTS_INDEX, body=body
        )

        total: int = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]  # type: ignore[index]
        items = [_parse_document_hit(h) for h in result["hits"]["hits"]]

        await _log_query(db, params.q, "document", total)

        return SearchResponse(
            data=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
        )
