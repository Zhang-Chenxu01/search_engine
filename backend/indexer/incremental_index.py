"""Incremental index — import JSONL into MySQL + ES with change detection.

Contrast with ``import_pages.py`` (bulk first-time import), this script:

* Compares ``content_hash`` — skips unchanged pages / attachments.
* Processes attachment items alongside pages, writing to ``attachments``
  table and ``nku_documents_v1`` index.
* Supports ``--force`` to bypass hash checks, ``--limit`` for test runs.

Usage::

    cd backend

    # Dry-run — validate only
    python -m indexer.incremental_index --input data/jsonl/pages.jsonl --dry-run

    # Incremental (skip unchanged)
    python -m indexer.incremental_index --batch-size 50

    # Force reindex everything
    python -m indexer.incremental_index --force

    # Test first 10 items
    python -m indexer.incremental_index --limit 10
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Any, Iterator, Optional

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk as es_bulk
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.page import Page
from app.search.es_client import get_es_client

logger = logging.getLogger(__name__)

PAGES_INDEX = "nku_pages_v1"
DOCUMENTS_INDEX = "nku_documents_v1"
DEFAULT_INPUT = "data/jsonl/pages.jsonl"
DEFAULT_BATCH_SIZE = 50

# ── Date helpers ──────────────────────────────────────────────

def _to_es_date(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(raw, str):
        return raw[:19].replace("T", " ")
    return str(raw)


def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                     "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw[:26], fmt)
            except ValueError:
                continue
    return None


# ── JSONL reader ──────────────────────────────────────────────

def _iter_jsonl(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: invalid JSON, skipped (%s)", line_no, exc)


# ═══════════════════════════════════════════════════════════════
#  Page processing
# ═══════════════════════════════════════════════════════════════

def _page_decision(
    session: Session,
    item: dict,
    force: bool = False,
) -> tuple[Optional[int], str]:
    """Decide what to do with a page item.

    Returns ``(page_id, action)`` where action is one of
    ``"insert"``, ``"update"``, ``"skip"``, or ``"skip_invalid"``.
    Returns ``(None, "skip_invalid")`` when the item is malformed.
    """
    normalized_url = (item.get("normalized_url") or "").strip()
    if not normalized_url:
        logger.warning("Skipping item without normalized_url: %s", item.get("url"))
        return None, "skip_invalid"

    new_hash = item.get("content_hash", "")

    existing: Optional[Page] = session.execute(
        select(Page).where(Page.normalized_url == normalized_url)
    ).scalar_one_or_none()

    if existing is None:
        return None, "insert"

    # Exists — check whether content changed
    if not force and existing.content_hash == new_hash:
        return existing.id, "skip"

    return existing.id, "update"


def _insert_page(session: Session, item: dict) -> int:
    """Insert a new Page row. Returns the new ``page_id``."""
    page = Page(
        url=item.get("url", ""),
        normalized_url=(item.get("normalized_url") or "").strip(),
        title=item.get("title", ""),
        source_site=item.get("source_site", ""),
        category=item.get("category", ""),
        publish_time=_parse_dt(item.get("publish_time")),
        crawl_time=_parse_dt(item.get("crawl_time")) or datetime.now(),
        content_hash=item.get("content_hash", ""),
        snapshot_path=item.get("snapshot_path", ""),
        status_code=item.get("status_code"),
    )
    session.add(page)
    session.flush()
    return page.id


def _update_page(session: Session, page_id: int, item: dict) -> None:
    """Update an existing Page row in-place."""
    page = session.get(Page, page_id)
    if page is None:
        return
    page.url = item.get("url", page.url)
    page.title = item.get("title", page.title)
    page.source_site = item.get("source_site", page.source_site)
    page.category = item.get("category", page.category)
    page.content_hash = item.get("content_hash", page.content_hash)
    page.snapshot_path = item.get("snapshot_path", page.snapshot_path)
    page.status_code = item.get("status_code", page.status_code)
    ct = _parse_dt(item.get("crawl_time"))
    if ct:
        page.crawl_time = ct
    pt = _parse_dt(item.get("publish_time"))
    if pt:
        page.publish_time = pt


def _build_page_es_action(page_id: int, item: dict) -> dict[str, Any]:
    """Build an ES bulk-index action for ``nku_pages_v1``."""
    anchor_texts: list[str] = item.get("anchor_texts", [])
    anchor_text: str = " ".join(anchor_texts) if anchor_texts else ""

    return {
        "_op_type": "index",
        "_index": PAGES_INDEX,
        "_id": str(page_id),
        "_source": {
            "page_id": page_id,
            "url": item.get("url", ""),
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "source_site": item.get("source_site", ""),
            "category": item.get("category", ""),
            "publish_time": _to_es_date(item.get("publish_time")),
            "crawl_time": _to_es_date(item.get("crawl_time")),
            "anchor_text": anchor_text,
            "snapshot_path": item.get("snapshot_path", ""),
        },
    }


# ═══════════════════════════════════════════════════════════════
#  Attachment processing
# ═══════════════════════════════════════════════════════════════

def _attachment_decision(
    session: Session,
    att: dict,
    force: bool = False,
) -> tuple[Optional[int], str]:
    """Decide what to do with one attachment dict."""
    normalized = (att.get("normalized_file_url") or att.get("file_url") or "").strip()
    if not normalized:
        return None, "skip_invalid"

    new_hash = att.get("content_hash", "")

    existing: Optional[Attachment] = session.execute(
        select(Attachment).where(Attachment.normalized_file_url == normalized)
    ).scalar_one_or_none()

    if existing is None:
        return None, "insert"

    if not force and existing.content_hash == new_hash:
        return existing.id, "skip"

    return existing.id, "update"


def _insert_attachment(session: Session, att: dict) -> int:
    """Insert an Attachment row. Returns the new ``attachment_id``."""
    a = Attachment(
        file_url=att.get("file_url", ""),
        normalized_file_url=(att.get("normalized_file_url") or att.get("file_url") or "").strip(),
        file_name=att.get("file_name", ""),
        file_type=att.get("file_type", ""),
        local_path=att.get("local_path"),
        parent_page_id=att.get("parent_page_id"),
        parent_url=att.get("parent_url", ""),
        content_hash=att.get("content_hash", ""),
        parse_status=att.get("parse_status", "pending"),
        crawl_time=_parse_dt(att.get("crawl_time")) or datetime.now(),
    )
    session.add(a)
    session.flush()
    return a.id


def _update_attachment(session: Session, attachment_id: int, att: dict) -> None:
    """Update an existing Attachment row."""
    a = session.get(Attachment, attachment_id)
    if a is None:
        return
    a.file_url = att.get("file_url", a.file_url)
    a.file_name = att.get("file_name", a.file_name)
    a.file_type = att.get("file_type", a.file_type)
    a.local_path = att.get("local_path", a.local_path)
    a.parent_page_id = att.get("parent_page_id", a.parent_page_id)
    a.parent_url = att.get("parent_url", a.parent_url)
    a.content_hash = att.get("content_hash", a.content_hash)
    a.parse_status = att.get("parse_status", a.parse_status)
    ct = _parse_dt(att.get("crawl_time"))
    if ct:
        a.crawl_time = ct


def _build_attachment_es_action(attachment_id: int, att: dict) -> dict[str, Any]:
    """Build an ES bulk-index action for ``nku_documents_v1``."""
    return {
        "_op_type": "index",
        "_index": DOCUMENTS_INDEX,
        "_id": str(attachment_id),
        "_source": {
            "attachment_id": attachment_id,
            "file_url": att.get("file_url", ""),
            "file_name": att.get("file_name", ""),
            "file_type": att.get("file_type", ""),
            "file_text": att.get("file_text", att.get("content", "")),
            "parent_page_id": att.get("parent_page_id"),
            "parent_title": att.get("parent_title", ""),
            "parent_url": att.get("parent_url", ""),
            "crawl_time": _to_es_date(att.get("crawl_time")),
        },
    }


# ═══════════════════════════════════════════════════════════════
#  Batch processor
# ═══════════════════════════════════════════════════════════════

def _set_es_doc_ids(session: Session, actions: list[dict[str, Any]]) -> None:
    """Write ES doc IDs back to MySQL (page or attachment)."""
    for action in actions:
        doc_id = action["_id"]
        index = action["_index"]
        try:
            pk = int(doc_id)
        except ValueError:
            continue
        if index == PAGES_INDEX:
            p = session.get(Page, pk)
            if p:
                p.es_doc_id = doc_id
        elif index == DOCUMENTS_INDEX:
            a = session.get(Attachment, pk)
            if a:
                a.es_doc_id = doc_id


# ── Stats container ───────────────────────────────────────────

class Stats:
    def __init__(self) -> None:
        self.page_insert = 0
        self.page_update = 0
        self.page_skip = 0
        self.page_fail = 0
        self.att_insert = 0
        self.att_update = 0
        self.att_skip = 0
        self.att_fail = 0

    def summary(self) -> str:
        lines = [
            "Pages  — "
            f"insert: {self.page_insert}, "
            f"update: {self.page_update}, "
            f"skip: {self.page_skip}, "
            f"fail: {self.page_fail}",
            "Attach — "
            f"insert: {self.att_insert}, "
            f"update: {self.att_update}, "
            f"skip: {self.att_skip}, "
            f"fail: {self.att_fail}",
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  Main pipeline
# ═══════════════════════════════════════════════════════════════

def run_incremental(
    input_path: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
    force: bool = False,
    limit: int = 0,
) -> Stats:
    """Execute incremental import.

    Returns a ``Stats`` object summarising what was done.
    """
    stats = Stats()

    # ── MySQL engine (sync) ────────────────────────────────────
    db_url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(db_url, echo=False)

    # ── ES client ──────────────────────────────────────────────
    es: Optional[Elasticsearch] = None
    if not dry_run:
        es = get_es_client()
        if not es.ping():
            logger.error("Cannot connect to Elasticsearch at %s", settings.ELASTICSEARCH_URL)
            sys.exit(1)
        logger.info("Elasticsearch connected: %s", es.info()["cluster_name"])

    batch: list[dict] = []
    session: Optional[Session] = None if dry_run else Session(engine)
    processed = 0

    def flush() -> None:
        nonlocal session
        if not batch:
            return
        if dry_run:
            for item in batch:
                _, _, _, _ = _process_one_page(None, item, stats, force, dry_run)
                for att in item.get("attachments", []) or []:
                    _process_one_attachment(None, att, stats, force, dry_run)
            batch.clear()
            return

        if session is None:
            session = Session(engine)

        page_actions: list[dict[str, Any]] = []
        att_actions: list[dict[str, Any]] = []

        for item in batch:
            page_id, page_action, _, _ = _process_one_page(session, item, stats, force, dry_run)
            if page_action in ("insert", "update") and page_id is not None:
                page_actions.append(_build_page_es_action(page_id, item))

            for att in (item.get("attachments") or []):
                att_id, att_action = _process_one_attachment(session, att, stats, force, dry_run)
                if att_action in ("insert", "update") and att_id is not None:
                    text = att.get("file_text") or att.get("content") or ""
                    if text.strip():
                        att_actions.append(_build_attachment_es_action(att_id, att))

        # MySQL commit
        if session:
            try:
                session.commit()
            except Exception:
                logger.exception("MySQL commit failed — rolling back batch")
                session.rollback()
                batch.clear()
                return

        # ES bulk write for pages
        if page_actions and es:
            try:
                ok, errs = es_bulk(es, page_actions, raise_on_error=False, refresh=False)
                if errs:
                    logger.warning("ES page bulk: %d errors", len(errs))
                    stats.page_fail += len(errs)
                if session:
                    _set_es_doc_ids(session, page_actions)
                    session.commit()
            except Exception:
                logger.exception("ES page bulk write failed")
                stats.page_fail += len(page_actions)

        # ES bulk write for attachments
        if att_actions and es:
            try:
                ok, errs = es_bulk(es, att_actions, raise_on_error=False, refresh=False)
                if errs:
                    logger.warning("ES attachment bulk: %d errors", len(errs))
                    stats.att_fail += len(errs)
                if session:
                    _set_es_doc_ids(session, att_actions)
                    session.commit()
            except Exception:
                logger.exception("ES attachment bulk write failed")
                stats.att_fail += len(att_actions)

        batch.clear()

    # ── Main loop ──────────────────────────────────────────────
    for item in _iter_jsonl(input_path):
        batch.append(item)
        processed += 1
        if len(batch) >= batch_size:
            flush()
        if limit > 0 and processed >= limit:
            break

    flush()

    if session:
        session.close()

    return stats


def _process_one_page(
    session: Optional[Session],
    item: dict,
    stats: Stats,
    force: bool,
    dry_run: bool,
) -> tuple[Optional[int], str, Optional[int], Optional[str]]:
    """Process a single page item.

    Returns ``(page_id, action, http_status, error)``.
    """
    try:
        if dry_run:
            normalized_url = (item.get("normalized_url") or "").strip()
            if not normalized_url:
                stats.page_fail += 1
                return None, "skip_invalid", None, "missing normalized_url"
            stats.page_insert += 1
            return 0, "insert", 200, None

        assert session is not None
        page_id, action = _page_decision(session, item, force)

        if action == "skip_invalid":
            stats.page_fail += 1
            return None, action, None, "invalid"

        if action == "skip":
            stats.page_skip += 1
            return page_id, action, None, None

        if action == "insert":
            page_id = _insert_page(session, item)
            stats.page_insert += 1
        elif action == "update":
            assert page_id is not None
            _update_page(session, page_id, item)
            stats.page_update += 1

        return page_id, action, None, None
    except Exception:
        logger.exception("Page processing failed: %s", item.get("url", "?"))
        try:
            if session:
                session.rollback()
        except Exception:
            pass
        stats.page_fail += 1
        return None, "skip_invalid", None, "exception"


def _process_one_attachment(
    session: Optional[Session],
    att: dict,
    stats: Stats,
    force: bool,
    dry_run: bool,
) -> tuple[Optional[int], str]:
    """Process a single attachment dict.  Returns ``(att_id, action)``."""
    try:
        if dry_run:
            normalized = (att.get("normalized_file_url") or att.get("file_url") or "").strip()
            if not normalized:
                stats.att_fail += 1
                return None, "skip_invalid"
            stats.att_insert += 1
            return 0, "insert"

        assert session is not None
        att_id, action = _attachment_decision(session, att, force)

        if action == "skip_invalid":
            stats.att_fail += 1
            return None, action

        if action == "skip":
            stats.att_skip += 1
            return att_id, action

        if action == "insert":
            att_id = _insert_attachment(session, att)
            stats.att_insert += 1
        elif action == "update":
            assert att_id is not None
            _update_attachment(session, att_id, att)
            stats.att_update += 1

        return att_id, action
    except Exception:
        logger.exception("Attachment processing failed: %s",
                         att.get("file_url", "?"))
        try:
            if session:
                session.rollback()
        except Exception:
            pass
        stats.att_fail += 1
        return None, "skip_invalid"


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Incremental index — import JSONL into MySQL + ES with change detection.",
    )
    parser.add_argument("--input", default=DEFAULT_INPUT,
                        help=f"JSONL file path (default: {DEFAULT_INPUT})")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"Items per batch (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate JSONL, print stats, no writes")
    parser.add_argument("--force", action="store_true",
                        help="Re-index even when content_hash is unchanged")
    parser.add_argument("--limit", type=int, default=0,
                        help="Only process the first N items (0 = unlimited)")
    args = parser.parse_args()

    logger.info(
        "Incremental import — input=%s batch=%d dry_run=%s force=%s limit=%s",
        args.input, args.batch_size, args.dry_run, args.force,
        args.limit if args.limit else "unlimited",
    )

    stats = run_incremental(
        input_path=args.input,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        force=args.force,
        limit=args.limit,
    )

    logger.info("Incremental import complete.\n%s", stats.summary())


if __name__ == "__main__":
    main()
