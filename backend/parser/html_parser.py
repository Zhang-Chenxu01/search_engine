"""Standalone HTML parser for NKU pages.

Extracts title, main content, publish time, and links from raw HTML.
Uses BeautifulSoup4 + lxml with readability-lxml as a fallback for
content extraction.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag


# ── Output model ───────────────────────────────────────────────

@dataclass
class ParsedDocument:
    url: str
    title: str = ""
    content: str = ""
    publish_time: Optional[datetime] = None
    out_links: list[str] = field(default_factory=list)
    anchor_texts: list[str] = field(default_factory=list)
    attachment_links: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "out_links": self.out_links,
            "anchor_texts": self.anchor_texts,
            "attachment_links": self.attachment_links,
        }


# ── Constants ──────────────────────────────────────────────────

CONTENT_SELECTORS = [
    "article",
    ".article-content",
    ".news-content",
    ".content",
    ".main",
    ".main-content",
    ".post-content",
    ".entry-content",
    "#content",
    "#article",
    ".TRS_Editor",
    ".TRS_PreAppend",
    ".Custom_UnionStyle",
]

ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"}

DATE_PATTERNS = [
    (re.compile(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}:\d{1,2})"), "%Y-%m-%d %H:%M:%S"),
    (re.compile(r"(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})"), "%Y-%m-%d %H:%M"),
    (re.compile(r"(\d{4}-\d{1,2}-\d{1,2})"), "%Y-%m-%d"),
    (re.compile(r"(\d{4}/\d{1,2}/\d{1,2}\s+\d{1,2}:\d{1,2})"), "%Y/%m/%d %H:%M"),
    (re.compile(r"(\d{4}/\d{1,2}/\d{1,2})"), "%Y/%m/%d"),
    (re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{1,2})"), "%Y年%m月%d日 %H:%M"),
    (re.compile(r"(\d{4}年\d{1,2}月\d{1,2}日)"), "%Y年%m月%d日"),
]

SCRIPT_STYLE_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "aside", "iframe"}


# ── Public API ─────────────────────────────────────────────────

def parse_html(html: str, url: str = "") -> ParsedDocument:
    """Parse *html* into a structured `ParsedDocument`.

    Args:
        html: Raw HTML string.
        url: Source URL, used to resolve relative links.

    Returns:
        `ParsedDocument` with extracted fields.
    """
    soup = BeautifulSoup(html, "lxml")
    doc = ParsedDocument(url=url)
    doc.title = _extract_title(soup)
    doc.content = _extract_content(soup, html)
    doc.publish_time = _extract_publish_time(soup, html)
    doc.out_links, doc.anchor_texts, doc.attachment_links = _extract_links(soup, url)
    return doc


# ── Private helpers ────────────────────────────────────────────

def _extract_title(soup: BeautifulSoup) -> str:
    """Extract page title from <title>, <h1>, or common selectors."""
    for selector in ("title", "h1", ".title", ".article-title", ".news-title", "h2"):
        tag = soup.select_one(selector)
        if tag:
            text = tag.get_text(strip=True)
            if text:
                return text
    return ""


def _extract_content(soup: BeautifulSoup, raw_html: str) -> str:
    """Extract main text using a cascade of strategies.

    1. Try common content selectors.
    2. Fall back to readability-lxml.
    3. Last resort: all body text.
    """
    # Strategy 1: known selectors
    for selector in CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container and len(container.get_text(strip=True)) > 120:
            return _inner_text(container)

    # Strategy 2: readability-lxml
    try:
        from readability import Document

        doc = Document(raw_html)
        summary_html = doc.summary()
        if summary_html:
            summary_soup = BeautifulSoup(summary_html, "lxml")
            text = summary_soup.get_text(separator="\n", strip=True)
            if len(text) > 80:
                return text
    except Exception:
        pass

    # Strategy 3: body fallback
    body = soup.find("body")
    if body:
        return _inner_text(body)
    return soup.get_text(separator="\n", strip=True)


def _extract_publish_time(soup: BeautifulSoup, raw_html: str) -> Optional[datetime]:
    """Best-effort extraction of publish time from visible text and <meta> tags."""
    # 1. Try <meta> tags
    for meta in soup.find_all("meta"):
        prop = (meta.get("property") or "").lower()
        name = (meta.get("name") or "").lower()
        content = (meta.get("content") or "").strip()
        if ("pubdate" in prop or "publish" in name or "date" in prop) and content:
            result = _parse_date(content)
            if result:
                return result

    # 2. Try common time containers
    for selector in (
        ".time", ".date", ".publish-time", ".pub-time", ".news-time",
        ".article-time", ".info-time", ".pubdate", "#pubtime",
    ):
        tag = soup.select_one(selector)
        if tag:
            result = _parse_date(tag.get_text())
            if result:
                return result

    # 3. Search visible text near the top (first 8 KB)
    visible = soup.get_text()[:8192]
    return _parse_date(visible)


def _extract_links(soup: BeautifulSoup, base_url: str) -> tuple[list[str], list[str], list[str]]:
    """Extract all <a href> links, classified into out_links / attachment_links.

    Returns:
        (out_links, anchor_texts, attachment_links)
    """
    out_links: list[str] = []
    anchor_texts: list[str] = []
    attachment_links: list[str] = []

    seen = set()
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue

        absolute: str = urljoin(base_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)

        text = a_tag.get_text(strip=True)
        anchor_texts.append(text)

        lower = absolute.lower()
        if any(lower.endswith(ext) for ext in ATTACHMENT_EXTENSIONS):
            attachment_links.append(absolute)
        else:
            out_links.append(absolute)

    return out_links, anchor_texts, attachment_links


# ── Text helpers ───────────────────────────────────────────────

def _inner_text(container: Tag) -> str:
    """Return cleaned inner text from *container*, removing scripting cruft."""
    for tag_name in SCRIPT_STYLE_TAGS:
        for tag in container.find_all(tag_name):
            tag.decompose()
    text = container.get_text(separator="\n", strip=True)
    return _clean_text(text)


def _clean_text(text: str) -> str:
    """Collapse consecutive whitespace into single space, strip each line."""
    lines = []
    for line in text.splitlines():
        stripped = re.sub(r"\s+", " ", line).strip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def _parse_date(text: str) -> Optional[datetime]:
    """Try to parse a datetime from *text* using known patterns."""
    text = text.replace("\n", " ").strip()
    for pattern, fmt in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return datetime.strptime(match.group(1), fmt)
            except ValueError:
                continue
    return None


# ── Test entry point ───────────────────────────────────────────

def main() -> None:
    """Smoke-test the parser against a sample HTML snippet."""
    sample_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>南开大学举办2024年毕业典礼 - 南开新闻网</title>
    <meta name="pubdate" content="2024-06-15 10:30:00">
</head>
<body>
    <nav>导航栏...</nav>
    <div class="article-content">
        <h1>南开大学举办2024年毕业典礼</h1>
        <p>　　南开新闻网讯（记者 张三）6月15日上午，南开大学2024年毕业典礼在八里台校区体育中心隆重举行。</p>
        <p>　　校长陈军院士发表讲话，寄语全体毕业生"公能日新，勇毅前行"。</p>
        <p>　　典礼现场，3000余名本科和研究生毕业生参加。<a href="/docs/schedule.pdf">典礼日程(PDF)</a></p>
        <p>相关链接：<a href="https://news.nankai.edu.cn/ywsd/2024/0615/article.html">详细报道</a></p>
    </div>
    <footer>页脚...</footer>
</body>
</html>"""

    doc = parse_html(sample_html, url="https://news.nankai.edu.cn/ywsd/test.html")
    print("=== Parsed Document ===")
    print(f"Title:           {doc.title}")
    print(f"Content preview: {doc.content[:200]}...")
    print(f"Publish time:    {doc.publish_time}")
    print(f"Out links:       {doc.out_links}")
    print(f"Anchor texts:    {doc.anchor_texts}")
    print(f"Attachment links:{doc.attachment_links}")
    print()
    print("=== Dict ===")
    import json
    print(json.dumps(doc.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
