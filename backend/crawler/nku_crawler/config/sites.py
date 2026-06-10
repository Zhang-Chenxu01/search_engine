"""Site-level crawl configuration.

Each site dict has these fields:

===============  ====================================================
Field             Description
===============  ====================================================
name              Unique identifier for the site (used in logs).
base_url          Root URL for resolving relative links.
allowed_domains   List of domains the spider is permitted to visit.
category          Category tag applied to every item from this site.
source_site       ``source_site`` value in the PageItem.
max_pages         Stop after this many PageItems from this site.
start_urls        List of entry-point URLs (listing pages).
list_patterns     Regex patterns that identify list/pagination pages.
detail_patterns   Regex patterns that identify article/detail pages.
content_selectors CSS selectors for extracting body text.
title_selectors   CSS selectors for extracting the article title.
===============  ====================================================
"""

# ═══════════════════════════════════════════════════════════════════
#  Per-run crawl settings
# ═══════════════════════════════════════════════════════════════════

CRAWL_SETTINGS: dict = {
    "default_max_pages": 100,       # 单站默认上限（可通过 -a max_pages=N 覆盖）
    "global_max_pages": 0,          # 全局上限（0 = 不限）
    "download_delay": 2,            # 同域名请求间隔（秒）
    "concurrent_per_domain": 4,     # 单域名并发数
    "obey_robots": True,
    "depth_limit": 5,               # 从 start_url 出发的最大深度
}

# ═══════════════════════════════════════════════════════════════════
#  Site definitions
# ═══════════════════════════════════════════════════════════════════

SITES: list[dict] = [
    # ── 南开新闻网 ───────────────────────────────────────────
    {
        "name": "nku_news_ywsd",
        "base_url": "https://news.nankai.edu.cn",
        "allowed_domains": ["news.nankai.edu.cn"],
        "category": "ywsd",
        "source_site": "news.nankai.edu.cn",
        "max_pages": 5000,
        "start_urls": ["https://news.nankai.edu.cn/ywsd/index.shtml"],
        "list_patterns": [r"/ywsd/index(?:_\d+)?\.shtml"],
        "detail_patterns": [r"/ywsd/system/\d{4}/\d{2}/\d{2}/\d+\.shtml"],
        "content_selectors": ["article .content *", ".article-content *",
                              ".TRS_Editor *", "#content *", ".content *"],
        "title_selectors": ["h1::text", ".title::text"],
    },
    {
        "name": "nku_news_mtnk",
        "base_url": "https://news.nankai.edu.cn",
        "allowed_domains": ["news.nankai.edu.cn"],
        "category": "mtnk",
        "source_site": "news.nankai.edu.cn",
        "max_pages": 5000,
        "start_urls": ["https://news.nankai.edu.cn/mtnk/index.shtml"],
        "list_patterns": [r"/mtnk/index(?:_\d+)?\.shtml"],
        "detail_patterns": [r"/mtnk/system/\d{4}/\d{2}/\d{2}/\d+\.shtml"],
        "content_selectors": ["article .content *", ".article-content *",
                              ".TRS_Editor *", "#content *", ".content *"],
        "title_selectors": ["h1::text", ".title::text"],
    },
    {
        "name": "nku_news_zhxw",
        "base_url": "https://news.nankai.edu.cn",
        "allowed_domains": ["news.nankai.edu.cn"],
        "category": "zhxw",
        "source_site": "news.nankai.edu.cn",
        "max_pages": 5000,
        "start_urls": ["https://news.nankai.edu.cn/zhxw/index.shtml"],
        "list_patterns": [r"/zhxw/index(?:_\d+)?\.shtml"],
        "detail_patterns": [r"/zhxw/system/\d{4}/\d{2}/\d{2}/\d+\.shtml"],
        "content_selectors": ["article .content *", ".article-content *",
                              ".TRS_Editor *", "#content *", ".content *"],
        "title_selectors": ["h1::text", ".title::text"],
    },
    {
        "name": "nku_news_nkrw",
        "base_url": "https://news.nankai.edu.cn",
        "allowed_domains": ["news.nankai.edu.cn"],
        "category": "nkrw",
        "source_site": "news.nankai.edu.cn",
        "max_pages": 5000,
        "start_urls": ["https://news.nankai.edu.cn/nkrw/index.shtml"],
        "list_patterns": [r"/nkrw/index(?:_\d+)?\.shtml"],
        "detail_patterns": [r"/nkrw/system/\d{4}/\d{2}/\d{2}/\d+\.shtml"],
        "content_selectors": ["article .content *", ".article-content *",
                              ".TRS_Editor *", "#content *", ".content *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学官网 ─────────────────────────────────────────
    {
        "name": "nku_main",
        "base_url": "https://www.nankai.edu.cn",
        "allowed_domains": ["www.nankai.edu.cn"],
        "category": "portal",
        "source_site": "www.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://www.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$",
                            r"/info/\d+/\d+\.htm"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text", ".wp_title::text"],
    },

    # ── 南开大学就业指导中心 ─────────────────────────────────
    {
        "name": "nku_career",
        "base_url": "https://career.nankai.edu.cn",
        "allowed_domains": ["career.nankai.edu.cn"],
        "category": "employment",
        "source_site": "career.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://career.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$",
                            r"/web/[^/]+/detail\?id=\d+"],
        "content_selectors": [".article-body *", ".content *",
                              "#content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学研究生院 ─────────────────────────────────────
    {
        "name": "nku_graduate",
        "base_url": "https://graduate.nankai.edu.cn",
        "allowed_domains": ["graduate.nankai.edu.cn"],
        "category": "graduate",
        "source_site": "graduate.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://graduate.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学教务处 ───────────────────────────────────────
    {
        "name": "nku_jwc",
        "base_url": "https://jwc.nankai.edu.cn",
        "allowed_domains": ["jwc.nankai.edu.cn"],
        "category": "academic",
        "source_site": "jwc.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://jwc.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学图书馆 ───────────────────────────────────────
    {
        "name": "nku_lib",
        "base_url": "https://lib.nankai.edu.cn",
        "allowed_domains": ["lib.nankai.edu.cn"],
        "category": "library",
        "source_site": "lib.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://lib.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学计算机学院 ───────────────────────────────────
    {
        "name": "nku_cc",
        "base_url": "https://cc.nankai.edu.cn",
        "allowed_domains": ["cc.nankai.edu.cn"],
        "category": "cs",
        "source_site": "cc.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://cc.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学化学学院 ─────────────────────────────────────
    {
        "name": "nku_chem",
        "base_url": "https://chem.nankai.edu.cn",
        "allowed_domains": ["chem.nankai.edu.cn"],
        "category": "chemistry",
        "source_site": "chem.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://chem.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学经济学院 ─────────────────────────────────────
    {
        "name": "nku_econ",
        "base_url": "https://economics.nankai.edu.cn",
        "allowed_domains": ["economics.nankai.edu.cn"],
        "category": "economics",
        "source_site": "economics.nankai.edu.cn",
        "max_pages": 10000,
        "start_urls": ["https://economics.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },

    # ── 南开大学数学科学学院 ─────────────────────────────────
    {
        "name": "nku_math",
        "base_url": "https://math.nankai.edu.cn",
        "allowed_domains": ["math.nankai.edu.cn"],
        "category": "math",
        "source_site": "math.nankai.edu.cn",
        "max_pages": 5000,
        "start_urls": ["https://math.nankai.edu.cn"],
        "list_patterns": [],
        "detail_patterns": [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$"],
        "content_selectors": [".wp_articlecontent *", "#content *",
                              ".content *", "article *"],
        "title_selectors": ["h1::text", ".title::text"],
    },
]
