"""Config-driven multi-site spider for Nankai University.

Reads site definitions from ``nku_crawler.config.sites`` and crawls
each site independently, respecting per-site page limits and global caps.

Usage (from backend/crawler/)::

    python -m scrapy crawl news                          # default 100/site
    python -m scrapy crawl news -a max_pages=500         # override per-site
    python -m scrapy crawl news -a global_max=2000       # global cap
    python -m scrapy crawl news -a max_pages=1000 -a global_max=5000
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

# ── Shared domain allowlist (union of all site domains) ──────

_ALLOWED_DOMAINS: set[str] = set()
for _s in SITES:
    for _d in _s.get("allowed_domains", []):
        _ALLOWED_DOMAINS.add(_d.lower())

# ── Helpers ──────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    """Remove fragments and trailing slashes for dedup."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(parsed._replace(fragment="", path=path))


def is_allowed_domain(url: str) -> bool:
    """Check whether *url* belongs to any configured NKU domain."""
    netloc = urlparse(url).netloc.lower()
    for allowed in _ALLOWED_DOMAINS:
        if netloc == allowed or netloc.endswith("." + allowed):
            return True
    return False


def extract_publish_time(text: str) -> datetime | None:
    """Best-effort extraction of a publish timestamp from raw page text."""
    patterns = [
        r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})",
        r"(\d{4}-\d{1,2}-\d{1,2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{1,2})",
        r"(\d{4}年\d{1,2}月\d{1,2}日)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            raw = raw.replace("年", "-").replace("月", "-").replace("日", "")
            try:
                return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                try:
                    return datetime.strptime(raw.strip(), "%Y-%m-%d")
                except ValueError:
                    continue
    return None


# ═══════════════════════════════════════════════════════════════

class NewsSpider(scrapy.Spider):
    name = "news"

    # Per-site compiled patterns are built in __init__
    _compiled_sites: list[dict] = []

    def __init__(self, max_pages: str | None = None,
                 global_max: str | None = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # CLI overrides
        self._override_max = int(max_pages) if max_pages else None
        self._global_max = int(global_max) if global_max else CRAWL_SETTINGS["global_max_pages"]

        # Build per-site compiled configs
        self._compiled_sites = []
        all_domains: set[str] = set()
        all_start: list[str] = []

        for site in SITES:
            entry: dict = {
                **site,
                "list_re": [re.compile(p) for p in site.get("list_patterns", [])],
                "detail_re": [re.compile(p) for p in site.get("detail_patterns", [])],
                "count": 0,
                "max": self._override_max or site.get("max_pages",
                        CRAWL_SETTINGS["default_max_pages"]),
            }
            self._compiled_sites.append(entry)
            for d in site.get("allowed_domains", []):
                all_domains.add(d.lower())
            all_start.extend(site.get("start_urls", []))

        self.allowed_domains = list(all_domains)
        self.start_urls = all_start

        # Global stats
        self._total_items = 0
        self._total_requests = 0
        self._total_errors = 0

    # ── Helpers ──────────────────────────────────────────────

    def _find_site(self, url: str) -> dict | None:
        """Return the site config whose patterns match *url*."""
        for entry in self._compiled_sites:
            for pat in entry["detail_re"] + entry["list_re"]:
                if pat.search(url):
                    return entry
        return None

    def _site_at_limit(self, entry: dict) -> bool:
        return entry["count"] >= entry["max"]

    def _global_at_limit(self) -> bool:
        if self._global_max <= 0:
            return False
        return self._total_items >= self._global_max

    # ── Entry point ──────────────────────────────────────────

    def start_requests(self):
        """Tag each start URL with its site config name so we can route."""
        for entry in self._compiled_sites:
            for url in entry.get("start_urls", []):
                yield Request(url, callback=self.parse,
                              meta={"site_name": entry["name"]})

    # ── List page parser ─────────────────────────────────────

    def parse(self, response: Response) -> Generator[object, None, None]:
        """Parse a listing page: yield detail requests, follow pagination."""
        self._total_requests += 1

        site_name = response.meta.get("site_name", "")
        site = next((s for s in self._compiled_sites
                     if s["name"] == site_name), None)

        if site is None:
            # Fallback: find by URL pattern
            site = self._find_site(response.url)
        if site is None:
            return

        # Respect per-site limit
        if self._site_at_limit(site) or self._global_at_limit():
            return

        detail_urls: set[str] = set()
        list_urls: set[str] = set()

        for a_tag in response.css("a[href]"):
            href = a_tag.attrib.get("href", "")
            if not href:
                continue
            try:
                full_url = urljoin(response.url, href)
            except ValueError:
                continue
            if not is_allowed_domain(full_url):
                continue

            normalized = normalize_url(full_url)

            # Is this a detail page?
            for pat in site["detail_re"]:
                if pat.search(href) or pat.search(full_url):
                    detail_urls.add(full_url)
                    break
            else:
                # Is this a list/pagination page?
                for pat in site["list_re"]:
                    if pat.search(href) or pat.search(full_url):
                        list_urls.add(normalized)
                        break

        # Yield detail requests
        for url in detail_urls:
            if self._site_at_limit(site) or self._global_at_limit():
                break
            yield Request(
                url=url,
                callback=self.parse_detail,
                meta={
                    "site_name": site["name"],
                    "from_url": response.url,
                    "anchor_text": "",
                },
            )

        # Follow list/pagination pages
        for url in list_urls:
            if self._site_at_limit(site) or self._global_at_limit():
                break
            yield Request(
                url=url,
                callback=self.parse,
                meta={"site_name": site["name"]},
            )

    # ── Detail page parser ───────────────────────────────────

    def parse_detail(self, response: Response) -> Generator[PageItem, None, None]:
        """Parse a single article detail page and yield a PageItem."""
        site_name = response.meta.get("site_name", "")
        site = next((s for s in self._compiled_sites
                     if s["name"] == site_name), None)
        if site is None:
            return

        if self._site_at_limit(site) or self._global_at_limit():
            return

        # ── Title ─────────────────────────────────────────────
        title = ""
        for sel in site.get("title_selectors", []):
            t = response.css(sel).get()
            if t and t.strip():
                title = t.strip()
                break
        if not title:
            title = (response.css("title::text").get() or "").strip()

        # ── Content ───────────────────────────────────────────
        selectors = site.get("content_selectors", [])
        body_blocks: list[str] = []
        if selectors:
            body_blocks = response.css(
                ", ".join(selectors)
            ).css("::text").getall()
        if not body_blocks:
            body_blocks = response.css("body ::text").getall()
        content = "\n".join(t.strip() for t in body_blocks if t.strip())

        # ── Publish time (URL first, then text) ───────────────
        publish_time: datetime | None = None
        for pat in site["detail_re"]:
            m = pat.search(response.url)
            if m and m.lastindex and m.lastindex >= 3:
                try:
                    publish_time = datetime(
                        int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except (ValueError, IndexError):
                    pass
                break
        if publish_time is None:
            publish_time = extract_publish_time(response.text)

        # ── Links ─────────────────────────────────────────────
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
                (".pdf", ".docx", ".doc", ".xlsx", ".xls", ".zip", ".ppt", ".pptx"),
            ):
                attachment_links.append(full_url)
            else:
                out_links.append(full_url)

        # ── Build item ────────────────────────────────────────
        item = PageItem()
        item["url"] = response.url
        item["normalized_url"] = normalize_url(response.url)
        item["title"] = title
        item["content"] = content
        item["raw_html"] = response.text
        item["source_site"] = site.get("source_site", urlparse(response.url).netloc)
        item["category"] = site.get("category", "news")
        item["publish_time"] = publish_time
        item["anchor_texts"] = anchor_texts
        item["out_links"] = out_links
        item["attachment_links"] = attachment_links
        item["crawl_time"] = datetime.now()
        item["content_hash"] = hashlib.sha256(content.encode()).hexdigest()
        item["snapshot_path"] = ""
        item["status_code"] = response.status

        site["count"] += 1
        self._total_items += 1

        yield item

    # ── Stats on close ───────────────────────────────────────

    def closed(self, reason: str) -> None:
        """Log per-site and global crawl statistics."""
        self.logger.info("=" * 56)
        self.logger.info("Crawl finished — reason: %s", reason)
        self.logger.info("Total items: %d | Requests: %d | Errors: %d",
                         self._total_items, self._total_requests, self._total_errors)
        self.logger.info("-" * 56)
        for s in self._compiled_sites:
            pct = s["count"] / max(s["max"], 1) * 100
            self.logger.info(
                "  %-24s  %4d / %-4d  (%5.1f%%)  [%s]",
                s["name"], s["count"], s["max"], pct, s.get("category", "?"),
            )
        self.logger.info("=" * 56)
