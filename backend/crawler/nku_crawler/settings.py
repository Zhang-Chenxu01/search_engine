"""Scrapy settings for NKU crawler."""

import os

BOT_NAME = "nku_crawler"

SPIDER_MODULES = ["nku_crawler.spiders"]
NEWSPIDER_MODULE = "nku_crawler.spiders"

# ── Politeness ──────────────────────────────────────────────
ROBOTSTXT_OBEY = True
DOWNLOAD_DELAY = 1                         # seconds between requests to same domain (1s for scale)
CONCURRENT_REQUESTS = 16                   # global concurrent requests (12 domains × 1+)
CONCURRENT_REQUESTS_PER_DOMAIN = 2         # per-domain cap (polite: 1 req/sec per domain)
RANDOMIZE_DOWNLOAD_DELAY = True            # add jitter to delay

# ── Identity ────────────────────────────────────────────────
USER_AGENT = (
    "NankaiSearchBot/1.0 "
    "(+https://github.com/nankai-search; educational research project)"
)

# ── Limits ───────────────────────────────────────────────────
# Spider manages its own caps via config/sites.py + -a params.
# These act as a hard safety net for long-running crawls.
CLOSESPIDER_ITEMCOUNT = 0                  # 0 = no hard limit
CLOSESPIDER_PAGECOUNT = 500000             # safety net for 100K+ runs
CLOSESPIDER_TIMEOUT = 0                    # 0 = no timeout (for 100K crawl)

# ── Depth ───────────────────────────────────────────────────
DEPTH_LIMIT = 3                            # max link depth from start_urls
DEPTH_PRIORITY = 1
SCHEDULER_DISK_QUEUE = "scrapy.squeues.PickleFifoDiskQueue"
SCHEDULER_MEMORY_QUEUE = "scrapy.squeues.FifoMemoryQueue"

# ── Pipelines ───────────────────────────────────────────────
ITEM_PIPELINES = {
    "nku_crawler.pipelines.SnapshotPipeline": 100,
    "nku_crawler.pipelines.JsonlWriterPipeline": 200,
}

# ── Output directories (relative to crawler/ root) ──────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "jsonl")
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "snapshots")

# ── HTTP cache ───────────────────────────────────────────────
# Enable for dev/testing to avoid re-downloading.
# Disable (False) for production crawls to ensure fresh content.
HTTPCACHE_ENABLED = False
HTTPCACHE_EXPIRATION_SECS = 86400          # 24 hours
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = []

# ── Misc ────────────────────────────────────────────────────
LOG_LEVEL = "INFO"
RETRY_ENABLED = True
RETRY_TIMES = 2
DOWNLOAD_TIMEOUT = 15
REDIRECT_ENABLED = True
COOKIES_ENABLED = False
