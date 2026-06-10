"""Build Elasticsearch query DSL for various search types.

Each function returns a complete ES search body dict (query + highlight + from/size).
"""

from typing import Any, Optional

PAGES_INDEX = "nku_pages_v1"
DOCUMENTS_INDEX = "nku_documents_v1"

# Highlight configuration shared across page searches
PAGES_HIGHLIGHT: dict[str, Any] = {
    "fields": {
        "title": {
            "number_of_fragments": 0,          # return entire field, highlighted
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
        },
        "content": {
            "fragment_size": 150,
            "number_of_fragments": 3,
            "no_match_size": 100,
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
        },
        "anchor_text": {
            "number_of_fragments": 1,
            "fragment_size": 100,
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
        },
    },
}

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


def _build_filters(
    source_site: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Build term-filter clauses for source_site and category."""
    filters: list[dict[str, Any]] = []
    if source_site:
        filters.append({"term": {"source_site": source_site}})
    if category:
        filters.append({"term": {"category": category}})
    return filters


# ── Page queries ──────────────────────────────────────────────

def build_multi_match_query(
    q: str,
    source_site: Optional[str] = None,
    category: Optional[str] = None,
    from_: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """Multi-match across title (^4), anchor_text (^2), content (^1)."""
    filters = _build_filters(source_site, category)
    query: dict[str, Any] = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": q,
                        "fields": ["title^4", "anchor_text^2", "content^1"],
                        "type": "best_fields",
                    }
                }
            ]
        }
    }
    if filters:
        query["bool"]["filter"] = filters

    return {
        "query": query,
        "highlight": PAGES_HIGHLIGHT,
        "from": from_,
        "size": size,
        "_source": [
            "page_id", "url", "title", "source_site", "category",
            "publish_time", "snapshot_path",
        ],
    }


def build_match_phrase_query(
    q: str,
    source_site: Optional[str] = None,
    category: Optional[str] = None,
    from_: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """Exact phrase match on title and content."""
    filters = _build_filters(source_site, category)
    query: dict[str, Any] = {
        "bool": {
            "should": [
                {"match_phrase": {"title": {"query": q, "boost": 4.0}}},
                {"match_phrase": {"content": {"query": q, "boost": 1.0}}},
            ],
            "minimum_should_match": 1,
        }
    }
    if filters:
        query["bool"]["filter"] = filters

    return {
        "query": query,
        "highlight": PAGES_HIGHLIGHT,
        "from": from_,
        "size": size,
        "_source": [
            "page_id", "url", "title", "source_site", "category",
            "publish_time", "snapshot_path",
        ],
    }


def build_wildcard_query(
    q: str,
    field: str = "title",
    source_site: Optional[str] = None,
    category: Optional[str] = None,
    from_: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """Wildcard query on title (text tokens) or url (keyword) field.

    ``field`` must be ``"title"`` or ``"url"``.
    Note: wildcard on ``title`` matches against IK-analyzed tokens, not the
    raw string.  For exact substring matching on the full title, add a
    ``title.keyword`` sub-field to the index mapping.
    """
    # Map logical field names to ES field paths
    field_map: dict[str, str] = {
        "title": "title",
        "url": "url",
    }
    es_field = field_map.get(field, "title")

    filters = _build_filters(source_site, category)
    query: dict[str, Any] = {
        "bool": {
            "must": [
                {"wildcard": {es_field: q}}
            ]
        }
    }
    if filters:
        query["bool"]["filter"] = filters

    return {
        "query": query,
        "from": from_,
        "size": size,
        "_source": [
            "page_id", "url", "title", "source_site", "category",
            "publish_time", "snapshot_path",
        ],
    }


# ── Document query ────────────────────────────────────────────

def build_document_query(
    q: str,
    from_: int = 0,
    size: int = 10,
) -> dict[str, Any]:
    """Multi-match across file_name, file_text, parent_title."""
    return {
        "query": {
            "multi_match": {
                "query": q,
                "fields": ["file_name^3", "file_text^1", "parent_title^2"],
                "type": "best_fields",
            }
        },
        "highlight": DOCUMENTS_HIGHLIGHT,
        "from": from_,
        "size": size,
        "_source": [
            "attachment_id", "file_url", "file_name", "file_type",
            "parent_page_id", "parent_title", "parent_url", "crawl_time",
        ],
    }
