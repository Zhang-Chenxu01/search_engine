"""Site-level crawl configuration — tuned for ~150K capacity.

Based on actual crawl results (2026-06-10):
  - High-yield sites (3K-4K): news, chem, cz, career, sky, mse → raised to 5000
  - Medium sites (1K-3K): raised to 3000
  - Low sites (<1K): raised to 1500
  - New domains discovered during crawl: added from offsite/domains list
"""

CRAWL_SETTINGS: dict = {
    "default_max_pages": 1500,
    "global_max_pages": 0,
    "download_delay": 1,
    "concurrent_per_domain": 2,
    "obey_robots": True,
    "depth_limit": 10,
}

_DEFAULT_SELECTORS = [
    ".wp_articlecontent *", "#content *", ".content *",
    "article *", ".article-content *", ".TRS_Editor *",
    ".detail-content *", ".news-content *",
]

_DEFAULT_TITLE = ["h1::text", ".title::text", ".article-title::text"]

_DEFAULT_PATTERNS = [r"/\d{4}/\d{2}/\d{2}/[^/]+\.html?$",
                     r"/info/\d+/\d+\.htm"]

def _site(name, domain, category, max_pages=1500, start_paths=None, **kw):
    if start_paths is None:
        start_paths = [f"https://{domain}"]
    else:
        start_paths = [f"https://{domain}{p}" for p in start_paths]
    return {
        "name": f"nku_{name}",
        "base_url": f"https://{domain}",
        "allowed_domains": [domain],
        "category": category,
        "source_site": domain,
        "max_pages": max_pages,
        "start_urls": start_paths,
        "list_patterns": kw.get("list_patterns", []),
        "detail_patterns": kw.get("detail_patterns", _DEFAULT_PATTERNS),
        "content_selectors": kw.get("content_selectors", _DEFAULT_SELECTORS),
        "title_selectors": kw.get("title_selectors", _DEFAULT_TITLE),
    }


SITES: list[dict] = [
    # ── Tier 1: 高产站点 (实际跑出 3K-4K) — 提到 8000 ──────
    _site("news",  "news.nankai.edu.cn", "news",   max_pages=8000),
    _site("chem",  "chem.nankai.edu.cn",  "chemistry", max_pages=8000),
    _site("cz",    "cz.nankai.edu.cn",    "marxism", max_pages=8000),
    _site("career","career.nankai.edu.cn","employment", max_pages=8000),
    _site("sky",   "sky.nankai.edu.cn",   "biology", max_pages=8000),
    _site("mse",   "mse.nankai.edu.cn",   "materials", max_pages=8000),

    # ── Tier 2: 中产站点 (1K-3K) — 提到 5000 ──────────────
    _site("international","international.nankai.edu.cn","international",max_pages=5000),
    _site("ai",     "ai.nankai.edu.cn",    "cs",       max_pages=5000),
    _site("finance","finance.nankai.edu.cn","finance",  max_pages=5000),
    _site("cs",     "cs.nankai.edu.cn",    "cs",       max_pages=5000),
    _site("wxy",    "wxy.nankai.edu.cn",   "literature",max_pages=5000),
    _site("medical","medical.nankai.edu.cn","medical",  max_pages=5000),
    _site("math",   "math.nankai.edu.cn",  "math",     max_pages=5000),
    _site("tas",    "tas.nankai.edu.cn",   "tourism",  max_pages=5000),
    _site("graduate","graduate.nankai.edu.cn","graduate",max_pages=5000),
    _site("sfs",    "sfs.nankai.edu.cn",   "foreign_lang",max_pages=5000),
    _site("env",    "env.nankai.edu.cn",   "env",      max_pages=5000),
    _site("skleoc", "skleoc.nankai.edu.cn","lab",      max_pages=5000),
    _site("pharmacy","pharmacy.nankai.edu.cn","pharmacy",max_pages=5000),
    _site("jwc",    "jwc.nankai.edu.cn",   "academic", max_pages=5000),
    _site("phil",   "phil.nankai.edu.cn",  "philosophy",max_pages=5000),
    _site("ceo",    "ceo.nankai.edu.cn",   "ee",       max_pages=5000),
    _site("shxy",   "shxy.nankai.edu.cn",  "sociology",max_pages=5000),
    _site("rsc",    "rsc.nankai.edu.cn",   "hr",       max_pages=5000),
    _site("lib",    "lib.nankai.edu.cn",   "library",  max_pages=5000),
    _site("history","history.nankai.edu.cn","history", max_pages=5000),
    _site("hyxy",   "hyxy.nankai.edu.cn",  "language", max_pages=5000),

    # ── Tier 3: 低产站点 (<1K) — 提到 3000 ────────────────
    _site("www",    "www.nankai.edu.cn",   "portal",   max_pages=3000),
    _site("law",    "law.nankai.edu.cn",   "law",      max_pages=3000),
    _site("archives","archives.nankai.edu.cn","archives",max_pages=3000),
    _site("xgb",    "xgb.nankai.edu.cn",   "student",  max_pages=3000),
    _site("sklmcb", "sklmcb.nankai.edu.cn","lab",      max_pages=3000),
    _site("std",    "std.nankai.edu.cn",   "research", max_pages=3000),
    _site("sie",    "sie.nankai.edu.cn",   "education",max_pages=3000),
    _site("cyber",  "cyber.nankai.edu.cn", "cs",       max_pages=3000),
    _site("cc",     "cc.nankai.edu.cn",    "cs",       max_pages=3000),
    _site("economics","economics.nankai.edu.cn","economics",max_pages=3000),
    _site("yzb",    "yzb.nankai.edu.cn",   "admission",max_pages=3000),
    _site("nkzbb",  "nkzbb.nankai.edu.cn", "procurement",max_pages=3000),
    _site("zsb",    "zsb.nankai.edu.cn",   "admission",max_pages=3000),

    # ── 新增: 已验证可达 ─────────────────────────────────
]
