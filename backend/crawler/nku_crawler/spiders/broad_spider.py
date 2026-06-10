"""Breadth-first broad spider — follow ALL internal links, extract from every page.

Usage (from backend/crawler/)::

    # Scale-10:  ~100K pages (~2h)
    python -m scrapy crawl broad -a max_pages=8000 -a global_max=100000

    # Scale-2:   ~20K  pages (~20min)
    python -m scrapy crawl broad -a max_pages=1500 -a global_max=20000

    # Test:      ~500  pages
    python -m scrapy crawl broad -a max_pages=50 -a global_max=500
"""

import hashlib
import re
from datetime import datetime
from typing import Generator
from urllib.parse import urljoin, urlparse, urlunparse

import scrapy
from scrapy.http import Request, Response

from nku_crawler.config.sites import CRAWL_SETTINGS, SITES
from nku_crawler.items import PageItem

# ── Collect all allowed domains from config ───────────────────

_ALLOWED_DOMAINS: set[str] = set()
for _s in SITES:
    for _d in _s.get("allowed_domains", []):
        _ALLOWED_DOMAINS.add(_d.lower())


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(parsed._replace(fragment="", path=path))


def is_allowed_domain(url: str) -> bool:
    """Exact domain match only — suffixes like ``old.lib.nankai.edu.cn``
    are NOT automatically allowed."""
    netloc = urlparse(url).netloc.lower()
    # Strip leading "www." for matching
    netloc = netloc[4:] if netloc.startswith("www.") else netloc
    return netloc in _ALLOWED_DOMAINS


# Regex for extracting publish time from URL path: /2026/06/09/
_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})[/.]")

# File extensions to skip (non-content)
_SKIP_EXT = re.compile(
    r"\.(css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot|mp4|mp3|"
    r"webp|bmp|pdf|docx?|xlsx?|pptx?|zip|rar|7z|tar|gz)$",
    re.IGNORECASE,
)

# URL patterns that are unlikely to contain article content
_SKIP_PATH = re.compile(
    r"/(search|login|logout|register|user|admin|wp-admin|"
    r"wp-content/(?!uploads)|wp-json|api|feed|rss|"
    r"comment|reply|trackback|tag/|category/|author/|"
    r"page/\d+|date/)\b|"
    r"\$\["     # unescaped template variables like $[portalCategoryId]
    r"|nextcid=",  # broken pagination params (zhgl.nankai.edu.cn)
    re.IGNORECASE,
)


# ═══════════════════════════════════════════════════════════════

class BroadSpider(scrapy.Spider):
    """Breadth-first crawler for NKU domains.

    Unlike ``NewsSpider`` which uses detail/list patterns, this spider
    treats EVERY internal page as a potential content page — extracting
    title, body text, links, and attachments from all of them.

    Suitable for high-volume crawls (10K–100K+ pages).
    """

    name = "broad"

    # Broad default content selectors
    _CONTENT_SELECTORS = (
        "article *, .article-content *, .TRS_Editor *, "
        "#content *, .content *, .main-content *, "
        ".wp_articlecontent *, .detail-content *, .news-content *, "
        ".entry-content *, .post-content *"
    )

    def __init__(self, max_pages: str | None = None,
                 global_max: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._per_site_max = int(max_pages) if max_pages else CRAWL_SETTINGS["default_max_pages"]
        self._global_max = int(global_max) if global_max else CRAWL_SETTINGS["global_max_pages"]

        all_domains: set[str] = set()
        all_start: list[str] = []
        self._site_stats: dict[str, int] = {}  # site_name → count

        for site in SITES:
            self._site_stats[site["name"]] = 0
            for d in site.get("allowed_domains", []):
                all_domains.add(d.lower())
            all_start.extend(site.get("start_urls", []))

        self.allowed_domains = list(all_domains)
        self.start_urls = all_start

        self._total = 0

    def _at_global_limit(self) -> bool:
        return self._global_max > 0 and self._total >= self._global_max

    # ── Entry point ──────────────────────────────────────────

    def start_requests(self):
        """Seed the crawl from every configured start URL."""
        for site in SITES:
            for url in site.get("start_urls", []):
                yield Request(url, callback=self.parse,
                              meta={"site_name": site["name"]})

    # ── Parse (BFS) ──────────────────────────────────────────

    def parse(self, response: Response) -> Generator[object, None, None]:
        """Parse any page: extract content as PageItem, follow all internal links."""
        site_name = response.meta.get("site_name", "")
        site = next((s for s in SITES if s["name"] == site_name), None)

        # Fallback: match by domain
        if site is None:
            netloc = urlparse(response.url).netloc.lower()
            site = next((s for s in SITES
                         if any(d in netloc for d in s.get("allowed_domains", []))), None)
        if site is None:
            return

        # Respect limits
        count = self._site_stats.get(site_name, 0)
        if count >= self._per_site_max or self._at_global_limit():
            return

        # ── Skip non-HTML responses (PDF, images, etc.) ──
        content_type = (response.headers.get("Content-Type", b"")).decode("utf-8", "ignore")
        # Treat as HTML if text/html explicitly, or if Content-Type is missing
        is_html = "text/html" in content_type or content_type.strip() == ""

        # ── Extract content → yield PageItem ──────────────
        if is_html and self._total < self._per_site_max * len(SITES):
            try:
                yield from self._extract_page(response, site)
            except Exception:
                pass  # binary file masquerading as HTML

        # ── Follow internal links (BFS) ───────────────────
        if is_html and not self._at_global_limit():
            seen: set[str] = set()
            for a_tag in response.css("a[href]"):
                href = a_tag.attrib.get("href", "")
                if not href:
                    continue
                # Skip non-URL strings (Chinese text, javascript:, mailto:, etc.)
                if not href.startswith(("http://", "https://", "/", "./", "../")):
                    if not href[0].isascii() or href.startswith(("javascript:", "mailto:", "tel:")):
                        continue
                try:
                    full_url = urljoin(response.url, href)
                except ValueError:
                    continue
                if not is_allowed_domain(full_url):
                    continue
                # Skip file downloads
                if _SKIP_EXT.search(full_url):
                    continue
                try:
                    norm = normalize_url(full_url)
                except ValueError:
                    continue
                if norm in seen:
                    continue
                if self._site_stats.get(site_name, 0) >= self._per_site_max:
                    break
                if self._at_global_limit():
                    break
                # Skip static files and non-content paths
                if _SKIP_EXT.search(full_url) or _SKIP_PATH.search(full_url):
                    continue
                yield Request(full_url, callback=self.parse,
                              meta={"site_name": site["name"]})

    # ── Content extraction ───────────────────────────────────

    def _extract_page(self, response: Response,
                      site: dict) -> Generator[PageItem, None, None]:
        """Extract title, body, and links from a single page."""

        # Title
        title = ""
        for sel in site.get("title_selectors", ["h1::text", "title::text"]):
            t = response.css(sel).get()
            if t and t.strip():
                title = t.strip()
                break

        # Content
        body_blocks = response.css(self._CONTENT_SELECTORS).css("::text").getall()
        if not body_blocks:
            body_blocks = response.css("body ::text").getall()
        content = "\n".join(t.strip() for t in body_blocks if t.strip())
        if len(content) < 50:  # skip near-empty pages
            return

        # Publish time from URL or text
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
            if full_url.lower().endswith(
                (".pdf", ".docx", ".doc", ".xlsx", ".xls",
                 ".zip", ".ppt", ".pptx", ".rar"),
            ):
                attachment_links.append(full_url)
            else:
                out_links.append(full_url)

        # Build item
        item = PageItem()
        item["url"] = response.url
        item["normalized_url"] = normalize_url(response.url)
        item["title"] = title
        item["content"] = content
        item["raw_html"] = response.text
        item["source_site"] = site.get("source_site", urlparse(response.url).netloc)
        item["category"] = site.get("category", "web")
        item["publish_time"] = publish_time
        item["anchor_texts"] = anchor_texts
        item["out_links"] = out_links
        item["attachment_links"] = attachment_links
        item["crawl_time"] = datetime.now()
        item["content_hash"] = hashlib.sha256(content.encode()).hexdigest()
        item["snapshot_path"] = ""
        item["status_code"] = response.status

        # Track stats
        site_name = site["name"]
        self._site_stats[site_name] = self._site_stats.get(site_name, 0) + 1
        self._total += 1

        yield item

    # ── Stats ────────────────────────────────────────────────

    def closed(self, reason: str) -> None:
        self.logger.info("=" * 56)
        self.logger.info("Broad crawl finished — reason: %s", reason)
        self.logger.info("Total items: %d", self._total)
        self.logger.info("-" * 56)
        for name, cnt in sorted(self._site_stats.items(), key=lambda x: -x[1]):
            if cnt > 0:
                self.logger.info("  %-30s %6d", name, cnt)
        self.logger.info("=" * 56)
