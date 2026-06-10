"""Download, parse, and index attachment files (PDF/DOCX/XLSX) from JSONL.

Usage::

    cd backend
    python -m indexer.process_attachments                          # default
    python -m indexer.process_attachments --dry-run
    python -m indexer.process_attachments --force --limit 10
    python -m indexer.process_attachments --max-size-mb 100
"""

import argparse
import hashlib
import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import urlparse

import requests
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk as es_bulk
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attachment import Attachment
from app.models.page import Page
from app.search.es_client import get_es_client
from parser.document_parser import parse_document as parse_doc

logger = logging.getLogger(__name__)

DOCUMENTS_INDEX = "nku_documents_v1"
DEFAULT_INPUT = "data/jsonl/pages.jsonl"
DEFAULT_DOWNLOAD_DIR = "data/attachments"
DEFAULT_MAX_SIZE_MB = 50
DEFAULT_RETRY = 2
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}

HEADERS = {
    "User-Agent": "NankaiSearchBot/1.0 (+https://github.com/nankai-search; educational research project)"
}

# ── Stats ─────────────────────────────────────────────────────

class Stats:
    def __init__(self) -> None:
        self.found = 0
        self.new_att = 0
        self.skipped = 0
        self.dl_ok = 0
        self.dl_fail = 0
        self.parse_ok = 0
        self.parse_fail = 0
        self.indexed = 0

    def summary(self) -> str:
        return (
            f"Found: {self.found}  New: {self.new_att}  Skipped: {self.skipped}  "
            f"DL-OK: {self.dl_ok}  DL-Fail: {self.dl_fail}  "
            f"Parse-OK: {self.parse_ok}  Parse-Fail: {self.parse_fail}  "
            f"Indexed: {self.indexed}"
        )


# ── Helpers ───────────────────────────────────────────────────

def _iter_jsonl(path: str) -> Iterator[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                pass


def _safe_filename(url: str) -> str:
    """Generate a unique filename: md5(normalized_url) + original extension."""
    parsed = urlparse(url)
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    orig_name = os.path.basename(parsed.path) or "download"
    ext = os.path.splitext(orig_name)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        ext = _guess_ext(url, ext)
    return f"{url_hash}{ext}"


def _guess_ext(url: str, current: str) -> str:
    """Try to determine extension from URL or Content-Type."""
    lower = url.lower()
    for e in SUPPORTED_EXTENSIONS:
        if e in lower:
            return e
    return current or ".pdf"


def _is_safe_url(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https")


def _build_es_action(att: Attachment, file_text: str) -> dict[str, Any]:
    return {
        "_op_type": "index",
        "_index": DOCUMENTS_INDEX,
        "_id": str(att.id),
        "_source": {
            "attachment_id": att.id,
            "file_url": att.file_url,
            "file_name": att.file_name,
            "file_type": att.file_type,
            "file_text": file_text,
            "parent_page_id": att.parent_page_id,
            "parent_title": att.parent_title,
            "parent_url": att.parent_url,
            "source_site": att.source_site,
            "category": att.category,
            "text_length": len(file_text),
            "crawl_time": att.crawl_time.strftime("%Y-%m-%d %H:%M:%S") if att.crawl_time else None,
        },
    }


# ── Download ──────────────────────────────────────────────────

def download_file(url: str, dest_dir: str, max_size: int,
                  retry: int) -> tuple[Optional[str], Optional[str], int]:
    """Download *url* to *dest_dir*.  Returns ``(local_path, error, file_size)``."""
    fname = _safe_filename(url)
    local_path = os.path.join(dest_dir, fname)

    for attempt in range(retry + 1):
        try:
            resp = requests.get(url, headers=HEADERS, stream=True,
                                timeout=(10, 60), allow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" in content_type:
                return None, f"Unexpected Content-Type: {content_type}", 0

            # Check size
            cl = resp.headers.get("Content-Length")
            if cl and int(cl) > max_size:
                return None, f"File too large: {int(cl)} > {max_size}", 0

            # Stream to temp file, then rename
            tmp_fd, tmp_path = tempfile.mkstemp(dir=dest_dir)
            total = 0
            with os.fdopen(tmp_fd, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    total += len(chunk)
                    if total > max_size:
                        os.unlink(tmp_path)
                        return None, f"Download exceeded {max_size} bytes", total

            os.replace(tmp_path, local_path)
            return local_path, None, total

        except requests.RequestException as e:
            if attempt < retry:
                time.sleep(2 ** attempt)
                continue
            return None, str(e), 0

    return None, "Max retries exceeded", 0


# ── Main pipeline ─────────────────────────────────────────────

def run(
    input_path: str,
    download_dir: str,
    file_types: list[str],
    dry_run: bool = False,
    force: bool = False,
    limit: int = 0,
    retry: int = DEFAULT_RETRY,
    max_size_mb: int = DEFAULT_MAX_SIZE_MB,
) -> Stats:
    stats = Stats()
    max_size = max_size_mb * 1024 * 1024

    # ── DB engine ──────────────────────────────────────────────
    db_url = (f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}"
              f"@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DATABASE}")
    engine = create_engine(db_url, echo=False)

    # ── ES client ──────────────────────────────────────────────
    es: Optional[Elasticsearch] = None
    if not dry_run:
        es = get_es_client()
        if not es.ping():
            logger.error("ES not reachable")
            return stats

    os.makedirs(download_dir, exist_ok=True)
    ext_filter = {f".{t}" for t in file_types}

    batch_actions: list[dict] = []
    page_cache: dict[str, Page] = {}

    with Session(engine) as session:
        for item in _iter_jsonl(input_path):
            if limit > 0 and stats.found >= limit:
                break

            # Parent page info
            parent_url = item.get("url", "")
            parent_title = item.get("title", "")
            source_site = item.get("source_site", "")
            category = item.get("category", "")
            crawl_time_str = item.get("crawl_time", "")

            attachment_links = item.get("attachment_links", []) or []
            if not attachment_links:
                continue

            stats.found += len(attachment_links)

            for att_url in attachment_links:
                if not _is_safe_url(att_url):
                    continue
                ext = os.path.splitext(urlparse(att_url).path)[1].lower()
                if ext not in ext_filter:
                    continue

                normalized = att_url

                # ── Check existing ─────────────────────────────
                existing = session.execute(
                    select(Attachment).where(Attachment.normalized_file_url == normalized)
                ).scalar_one_or_none()

                if existing and not force:
                    if existing.parse_status == "indexed":
                        stats.skipped += 1
                        continue

                if dry_run:
                    stats.new_att += 1
                    stats.dl_ok += 1
                    stats.parse_ok += 1
                    stats.indexed += 1
                    continue

                stats.new_att += 1

                # ── Download ───────────────────────────────────
                local_path, dl_error, file_size = download_file(
                    att_url, download_dir, max_size, retry)
                if dl_error:
                    logger.warning("Download failed: %s — %s", att_url, dl_error)
                    stats.dl_fail += 1
                    if existing:
                        existing.parse_status = "download_failed"
                        existing.parse_error = dl_error[:1000]
                        session.commit()
                    continue
                stats.dl_ok += 1

                # ── Parse ──────────────────────────────────────
                file_text = parse_doc(local_path or "")
                if not file_text:
                    logger.warning("Parse empty: %s", local_path)
                    stats.parse_fail += 1
                    if existing:
                        existing.parse_status = "parse_failed"
                        existing.parse_error = "Empty or unsupported content"
                        session.commit()
                    else:
                        att = Attachment(
                            file_url=att_url,
                            normalized_file_url=normalized,
                            file_name=os.path.basename(local_path or ""),
                            file_type=ext.lstrip("."),
                            file_size=file_size,
                            local_path=local_path,
                            parent_url=parent_url,
                            parent_title=parent_title,
                            source_site=source_site,
                            category=category,
                            content_hash=hashlib.sha256(file_text.encode()).hexdigest(),
                            parse_status="parse_failed",
                            parse_error="Empty or unsupported content",
                            text_length=0,
                            crawl_time=_parse_dt(crawl_time_str),
                        )
                        session.add(att)
                        session.commit()
                    continue
                stats.parse_ok += 1
                text_len = len(file_text)

                # ── Write MySQL ────────────────────────────────
                if existing:
                    existing.local_path = local_path
                    existing.file_size = file_size
                    existing.content_hash = hashlib.sha256(file_text.encode()).hexdigest()
                    existing.parse_status = "indexed"
                    existing.parse_error = None
                    existing.text_length = text_len
                    existing.parent_title = parent_title
                    existing.source_site = source_site
                    existing.category = category
                    att = existing
                else:
                    att = Attachment(
                        file_url=att_url,
                        normalized_file_url=normalized,
                        file_name=os.path.basename(local_path or ""),
                        file_type=ext.lstrip("."),
                        file_size=file_size,
                        local_path=local_path,
                        parent_url=parent_url,
                        parent_title=parent_title,
                        source_site=source_site,
                        category=category,
                        content_hash=hashlib.sha256(file_text.encode()).hexdigest(),
                        parse_status="indexed",
                        text_length=text_len,
                        crawl_time=_parse_dt(crawl_time_str),
                    )
                    session.add(att)
                session.flush()
                session.commit()

                # ── Index ES ───────────────────────────────────
                if es:
                    action = _build_es_action(att, file_text)
                    try:
                        ok, errs = es_bulk(es, [action], raise_on_error=False, refresh=False)
                        if errs:
                            logger.warning("ES error for %s: %s", att_url, errs)
                        else:
                            stats.indexed += 1
                            att.es_doc_id = str(att.id)
                            session.commit()
                    except Exception as exc:
                        logger.warning("ES bulk failed for %s: %s", att_url, exc)

    return stats


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


# ── CLI ───────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    parser = argparse.ArgumentParser(description="Download, parse, and index attachments from JSONL.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="JSONL input file")
    parser.add_argument("--limit", type=int, default=0, help="Max attachments to process")
    parser.add_argument("--file-types", default="pdf,docx,xlsx")
    parser.add_argument("--download-dir", default=DEFAULT_DOWNLOAD_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Re-process already indexed attachments")
    parser.add_argument("--retry", type=int, default=DEFAULT_RETRY)
    parser.add_argument("--max-size-mb", type=int, default=DEFAULT_MAX_SIZE_MB)
    args = parser.parse_args()

    file_types = [t.strip() for t in args.file_types.split(",")]

    logger.info("Starting attachment processing: input=%s types=%s dry=%s force=%s",
                args.input, file_types, args.dry_run, args.force)

    stats = run(
        input_path=args.input,
        download_dir=args.download_dir,
        file_types=file_types,
        dry_run=args.dry_run,
        force=args.force,
        limit=args.limit,
        retry=args.retry,
        max_size_mb=args.max_size_mb,
    )

    logger.info("Done.  %s", stats.summary())


if __name__ == "__main__":
    main()
