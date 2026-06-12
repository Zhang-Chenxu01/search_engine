"""Batch spider — extends broad BFS logic with per-batch output and stats.

Usage (via run_crawl_batch.py or directly)::

    python -m scrapy crawl batch \
        -a batch_name=news_main \
        -a allowed_domains=news.nankai.edu.cn \
        -a start_urls=https://news.nankai.edu.cn/ywsd/index.shtml,... \
        -a max_pages=5000 \
        -a output_file=data/jsonl/batches/news_main.jsonl \
        -a source_site=南开新闻网 \
        -a category=news
"""

import hashlib
import json
import os
import re
import time
from datetime import datetime
from typing import Generator
from urllib.parse import urljoin, urlparse, urlunparse

import scrapy
from scrapy.http import Request, Response

from nku_crawler.items import PageItem

# ── Shared logic (same as broad_spider) ──────────────────────

_SKIP_EXT = re.compile(
    r"\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot|mp4|mp3|"
    r"webp|bmp|pdf|docx?|xlsx?|pptx?|zip|rar|7z|tar|gz)$",
    re.IGNORECASE,
)

_SKIP_PATH = re.compile(
    r"/(search|login|logout|register|user|admin|wp-admin|"
    r"wp-content/(?!uploads)|wp-json|api|feed|rss|"
    r"comment|reply|trackback|tag/|category/|author/|"
    r"page/\d+|date/)\b|"
    r"\$\[|nextcid=",
    re.IGNORECASE,
)

_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})[/.]")

_CONTENT_SELECTORS = (
    "article *, .article-content *, .TRS_Editor *, "
    "#content *, .content *, .main-content *, "
    ".wp_articlecontent *, .detail-content *, .news-content *, "
    ".entry-content *, .post-content *"
)

ATTACHMENT_EXTENSIONS = (
    ".pdf", ".docx", ".doc", ".xlsx", ".xls",
    ".zip", ".ppt", ".pptx", ".rar",
)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(parsed._replace(fragment="", path=path))


# ═══════════════════════════════════════════════════════════════

class BatchSpider(scrapy.Spider):
    """Single-batch BFS crawler with fixed output file and per-batch stats."""

    name = "batch"

    custom_settings = {
        "ITEM_PIPELINES": {
            "nku_crawler.pipelines.SnapshotPipeline": 100,
            "nku_crawler.spiders.batch_spider.BatchJsonlPipeline": 200,
        },
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 0.5,
        "AUTOTHROTTLE_MAX_DELAY": 5.0,
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    def __init__(self, batch_name=None, allowed_domains=None, start_urls=None,
                 max_pages=None, output_file=None, source_site=None,
                 category=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.batch_name = batch_name or "unknown"
        self.allowed_domains = (
            [d.strip() for d in allowed_domains.split(",")]
            if allowed_domains else []
        )
        self.start_urls = (
            [u.strip() for u in start_urls.split(",")]
            if start_urls else []
        )
        self._max_pages = int(max_pages) if max_pages else 5000
        self._output_file = output_file
        self._source_site = source_site or ""
        self._category = category or "web"

        # Stats
        self._total = 0
        self._total_bytes = 0
        self._attachment_count = 0
        self._empty_count = 0
        self._skipped_by_ext = 0

    # ── Entry point ──────────────────────────────────────────

    def start_requests(self):
        for url in self.start_urls:
            yield Request(url, callback=self.parse)

    def is_allowed(self, url: str) -> bool:
        netloc = urlparse(url).netloc.lower()
        netloc = netloc[4:] if netloc.startswith("www.") else netloc
        return netloc in self.allowed_domains

    # ── Parse ────────────────────────────────────────────────

    def parse(self, response: Response) -> Generator[object, None, None]:
        if self._total >= self._max_pages:
            return

        content_type = (response.headers.get("Content-Type", b"")).decode("utf-8", "ignore")
        is_html = "text/html" in content_type or content_type.strip() == ""

        if is_html:
            try:
                yield from self._extract_page(response)
            except Exception:
                pass

        if not is_html or self._total >= self._max_pages:
            return

        # Follow internal links
        seen: set[str] = set()
        for a_tag in response.css("a[href]"):
            href = a_tag.attrib.get("href", "")
            if not href:
                continue
            if not href.startswith(("http://", "https://", "/", "./", "../")):
                if not href[0].isascii() or href.startswith(("javascript:", "mailto:", "tel:")):
                    continue
            try:
                full_url = urljoin(response.url, href)
            except ValueError:
                continue
            if not self.is_allowed(full_url):
                continue
            if _SKIP_EXT.search(full_url) or _SKIP_PATH.search(full_url):
                self._skipped_by_ext += 1
                continue
            norm = normalize_url(full_url)
            if norm in seen:
                continue
            seen.add(norm)
            if self._total >= self._max_pages:
                break
            yield Request(full_url, callback=self.parse)

    def _extract_page(self, response: Response) -> Generator[PageItem, None, None]:
        # Title
        title = ""
        for sel in ["h1::text", ".title::text", "title::text"]:
            t = response.css(sel).get()
            if t and t.strip():
                title = t.strip()
                break

        # Content
        body_blocks = response.css(_CONTENT_SELECTORS).css("::text").getall()
        if not body_blocks:
            body_blocks = response.css("body ::text").getall()
        content = "\n".join(t.strip() for t in body_blocks if t.strip())

        if len(content) < 50:
            self._empty_count += 1
            return

        # Publish time from URL
        publish_time: datetime | None = None
        m = _URL_DATE_RE.search(response.url)
        if m:
            try:
                publish_time = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # Links
        anchor_texts: list[str] = []
        out_links: list[str] = []
        attachment_links: list[str] = []

        for a_tag in response.css("a[href]"):
            href = a_tag.attrib.get("href", "")
            if not href:
                continue
            try:
                full_url = urljoin(response.url, href)
            except ValueError:
                continue
            text = a_tag.css("::text").get("").strip()
            anchor_texts.append(text)
            if full_url.lower().endswith(ATTACHMENT_EXTENSIONS):
                attachment_links.append(full_url)
                self._attachment_count += 1
            else:
                out_links.append(full_url)

        # Build item
        item = PageItem()
        item["url"] = response.url
        item["normalized_url"] = normalize_url(response.url)
        item["title"] = title
        item["content"] = content
        item["raw_html"] = response.text
        item["source_site"] = self._source_site
        item["category"] = self._category
        item["publish_time"] = publish_time
        item["anchor_texts"] = anchor_texts
        item["out_links"] = out_links
        item["attachment_links"] = attachment_links
        item["crawl_time"] = datetime.now()
        item["content_hash"] = hashlib.sha256(content.encode()).hexdigest()
        item["snapshot_path"] = ""
        item["status_code"] = response.status

        self._total += 1
        self._total_bytes += len(content.encode())

        yield item

    # ── Stats on close ───────────────────────────────────────

    def closed(self, reason: str) -> None:
        elapsed = time.time() - self.crawler.stats.get_value("start_time").timestamp()
        stats = {
            "batch_name": self.batch_name,
            "elapsed_seconds": round(elapsed, 1),
            "pages_scraped": self._total,
            "pages_per_minute": round(self._total / max(elapsed / 60, 0.01), 1),
            "duplicate_filtered": self.crawler.stats.get_value("dupefilter/filtered", 0),
            "offsite_filtered": self.crawler.stats.get_value("offsite/filtered", 0),
            "skipped_by_ext": self._skipped_by_ext,
            "http_404_count": self.crawler.stats.get_value("downloader/response_status_count/404", 0),
            "retry_count": self.crawler.stats.get_value("retry/count", 0),
            "timeout_count": self.crawler.stats.get_value("downloader/exception_type_count/scrapy.exceptions.DownloadTimeoutError", 0),
            "attachment_links_count": self._attachment_count,
            "empty_content_count": self._empty_count,
            "average_content_length": round(self._total_bytes / max(self._total, 1), 1),
            "finish_reason": reason,
            "finished_at": datetime.now().isoformat(),
        }

        stats_dir = os.path.dirname(self._output_file) if self._output_file else "data/jsonl/batches"
        os.makedirs(stats_dir, exist_ok=True)
        stats_path = os.path.join(stats_dir, f"{self.batch_name}.stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

        self.logger.info("Batch stats saved: %s", stats_path)
        self.logger.info(
            "Batch '%s' done — %d pages in %.1fs (%.1f ppm)",
            self.batch_name, self._total, elapsed, stats["pages_per_minute"],
        )


# ── Custom pipeline: fixed-output JSONL writer ───────────────

class BatchJsonlPipeline:
    """Write items to a fixed-output JSONL file (one per batch)."""

    def open_spider(self, spider: BatchSpider) -> None:
        output = getattr(spider, "_output_file", None)
        if output:
            os.makedirs(os.path.dirname(output), exist_ok=True)
            self.file = open(output, "w", encoding="utf-8")
            spider.logger.info("Batch JSONL output: %s", output)
        else:
            self.file = None

    def close_spider(self, spider: BatchSpider) -> None:
        if self.file:
            self.file.close()

    def process_item(self, item: dict, spider: BatchSpider) -> dict:
        if self.file is None:
            return item
        for key in ("crawl_time", "publish_time"):
            val = item.get(key)
            if isinstance(val, datetime):
                item[key] = val.isoformat()
        line = json.dumps(dict(item), ensure_ascii=False) + "\n"
        self.file.write(line)
        return item
