"""Import Scrapy JSONL output into MySQL and Elasticsearch.

Usage:
    python -m indexer.import_pages                          # default input, batch-size 50
    python -m indexer.import_pages --input data/jsonl/news.jsonl
    python -m indexer.import_pages --batch-size 100
    python -m indexer.import_pages --dry-run                # validate only, no writes

Requires the ``backend/`` directory on PYTHONPATH::

    cd backend && python -m indexer.import_pages ...
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
from app.models.page import Page
from app.search.es_client import get_es_client

logger = logging.getLogger(__name__)

PAGES_INDEX = "nku_pages_v1"
DEFAULT_INPUT = "../data/jsonl/pages.jsonl"
DEFAULT_BATCH_SIZE = 50

# ── ES action builder ──────────────────────────────────────────

def _build_es_action(page_id: int, item: dict) -> dict[str, Any]:
    """Convert a JSONL row + MySQL page_id into an ES bulk-index action."""
    anchor_texts: list[str] = item.get("anchor_texts", [])
    anchor_text: str = " ".join(anchor_texts) if anchor_texts else ""

    publish_time_raw = item.get("publish_time")
    crawl_time_raw = item.get("crawl_time")

    source: dict[str, Any] = {
        "page_id":       page_id,
        "url":           item.get("url", ""),
        "title":         item.get("title", ""),
        "content":       item.get("content", ""),
        "source_site":   item.get("source_site", ""),
        "category":      item.get("category", ""),
        "publish_time":  _to_es_date(publish_time_raw),
        "crawl_time":    _to_es_date(crawl_time_raw),
        "anchor_text":   anchor_text,
        "snapshot_path": item.get("snapshot_path", ""),
    }

    return {
        "_op_type": "index",
        "_index":   PAGES_INDEX,
        "_id":      str(page_id),
        "_source":  source,
    }


def _to_es_date(raw: Any) -> Optional[str]:
    """Normalise a datetime-ish value into an ES-friendly date string."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(raw, str):
        return raw[:19].replace("T", " ")  # convert ISO to ES format
    return str(raw)


# ── MySQL helpers ──────────────────────────────────────────────

def _upsert_page(session: Session, item: dict) -> tuple[int, bool] | tuple[None, None]:
    """Insert or update a Page row by normalized_url.

    Returns:
        ``(page_id, is_new)`` or ``(None, None)`` when skipped.
    """
    normalized_url = item.get("normalized_url", "").strip()
    if not normalized_url:
        logger.warning("Skipping item without normalized_url: %s", item.get("url"))
        return None, None

    existing: Optional[Page] = session.execute(
        select(Page).where(Page.normalized_url == normalized_url)
    ).scalar_one_or_none()

    if existing:
        existing.url = item.get("url", existing.url)
        existing.title = item.get("title", existing.title)
        existing.source_site = item.get("source_site", existing.source_site)
        existing.category = item.get("category", existing.category)
        existing.content_hash = item.get("content_hash", existing.content_hash)
        existing.snapshot_path = item.get("snapshot_path", existing.snapshot_path)
        existing.status_code = item.get("status_code", existing.status_code)
        existing.crawl_time = _parse_dt(item.get("crawl_time")) or existing.crawl_time
        existing.publish_time = _parse_dt(item.get("publish_time")) or existing.publish_time
        return existing.id, False

    publish_time = _parse_dt(item.get("publish_time"))
    crawl_time = _parse_dt(item.get("crawl_time")) or datetime.now()

    page = Page(
        url=item.get("url", ""),
        normalized_url=normalized_url,
        title=item.get("title", ""),
        source_site=item.get("source_site", ""),
        category=item.get("category", ""),
        publish_time=publish_time,
        crawl_time=crawl_time,
        content_hash=item.get("content_hash", ""),
        snapshot_path=item.get("snapshot_path", ""),
        status_code=item.get("status_code"),
        es_doc_id=None,
    )
    session.add(page)
    session.flush()  # populate page.id
    return page.id, True


def _set_es_doc_id(session: Session, page_id: int, es_id: str) -> None:
    page = session.get(Page, page_id)
    if page:
        page.es_doc_id = es_id


# ── Helpers ────────────────────────────────────────────────────

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


def _iter_jsonl(path: str) -> Iterator[dict]:
    """Yield parsed dicts from a JSONL file, skipping empty/malformed lines."""
    with open(path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Line %d: invalid JSON, skipped (%s)", line_no, exc)


# ── Main import routine ────────────────────────────────────────

def run_import(
    input_path: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> dict[str, int]:
    """Execute the full import pipeline.

    Returns:
        Dict with keys ``mysql_inserts``, ``mysql_updates``, ``es_indexed``,
        ``skipped``, ``failed``.
    """
    stats = {"mysql_inserts": 0, "mysql_updates": 0, "es_indexed": 0,
             "skipped": 0, "failed": 0}

    # ── MySQL engine (sync) ────────────────────────────────
    db_url = (
        f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
        f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}"
    )
    engine = create_engine(db_url, echo=False)

    # ── ES client ──────────────────────────────────────────
    es: Optional[Elasticsearch] = None
    if not dry_run:
        es = get_es_client()
        if not es.ping():
            logger.error("Cannot connect to Elasticsearch at %s", settings.ELASTICSEARCH_URL)
            sys.exit(1)
        logger.info("Elasticsearch connected: %s", es.info()["cluster_name"])

    # ── Process batches ────────────────────────────────────
    batch: list[dict] = []
    session: Optional[Session] = None if dry_run else Session(engine)

    def flush() -> None:
        nonlocal session
        if not batch:
            return
        if dry_run:
            stats["mysql_inserts"] += len(batch)
            stats["es_indexed"] += len(batch)
            batch.clear()
            return

        if session is None:
            session = Session(engine)

        es_actions: list[dict] = []
        for item in batch:
            try:
                result = _upsert_page(session, item)
                if result[0] is None:
                    stats["skipped"] += 1
                    continue
                page_id, is_new = result
                if is_new:
                    stats["mysql_inserts"] += 1
                else:
                    stats["mysql_updates"] += 1
                es_actions.append(_build_es_action(page_id, item))
            except Exception:
                logger.exception("MySQL write failed for %s", item.get("url"))
                stats["failed"] += 1

        if session:
            try:
                session.commit()
            except Exception:
                logger.exception("MySQL commit failed")
                session.rollback()
                stats["failed"] += len(batch)
                batch.clear()
                return

        # ES bulk write
        if es_actions and es:
            try:
                success, errors = es_bulk(es, es_actions, raise_on_error=False, refresh=False)
                stats["es_indexed"] += success
                if errors:
                    logger.warning("ES bulk had %d error(s)", len(errors))
                    stats["failed"] += len(errors)
                # Write ES doc IDs back to MySQL
                for action in es_actions[:success]:
                    if session:
                        _set_es_doc_id(session, int(action["_id"]), action["_id"])
                if session:
                    session.commit()
            except Exception:
                logger.exception("ES bulk write failed")
                stats["failed"] += len(es_actions)

        batch.clear()

    # ── Main loop ──────────────────────────────────────────
    for item in _iter_jsonl(input_path):
        batch.append(item)
        if len(batch) >= batch_size:
            flush()

    flush()  # final partial batch

    if session:
        session.close()

    return stats


# ── CLI ────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description="Import Scrapy JSONL pages into MySQL and Elasticsearch.",
    )
    parser.add_argument(
        "--input", default=DEFAULT_INPUT,
        help=f"Path to JSONL file (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
        help=f"Number of items per batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate JSONL and report stats without writing to DB/ES.",
    )
    args = parser.parse_args()

    logger.info("Starting import: input=%s batch_size=%d dry_run=%s",
                args.input, args.batch_size, args.dry_run)

    stats = run_import(
        input_path=args.input,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    logger.info(
        "Import complete — "
        "MySQL inserts: %(mysql_inserts)d, "
        "MySQL updates: %(mysql_updates)d, "
        "ES indexed: %(es_indexed)d, "
        "skipped: %(skipped)d, "
        "failed: %(failed)d",
        stats,
    )


if __name__ == "__main__":
    main()
