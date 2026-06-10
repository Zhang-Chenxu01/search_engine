"""Snapshot service — resolve, validate, and read HTML snapshot files.

Security: all file access is confined to the configured snapshot root directory.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.page import Page

# ── Resolve the canonical snapshot root ──────────────────────
# SNAPSHOT_DIR from settings.py defaults to:
#   crawler/../data/snapshots  →  backend/data/snapshots
# This file is at backend/app/services/ — go up 3 levels to reach backend/
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent   # backend/
_SNAPSHOT_ROOT = (_BACKEND_DIR / "data" / "snapshots").resolve()


NOTICE_BAR_HTML = """\
<div id="snapshot-notice" style="\
position:sticky;top:0;z-index:9999;\
background:#fff3cd;color:#856404;\
border-bottom:2px solid #ffc107;\
padding:12px 20px;font-size:14px;\
font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;\
text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.1);\
">
⚠️ 这是系统在爬取时保存的<strong>网页快照</strong>，原网页可能已经发生变化。
</div>
"""

# Regex for inserting notice bar after <body> or similar opening tags
_BODY_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)


# ── Path security ────────────────────────────────────────────

def _sanitise_path(raw_path: str) -> str:
    """Strip characters commonly abused for traversal.

    Rejects paths containing null bytes, and normalises slashes.
    """
    if "\x00" in raw_path:
        raise ValueError("Path contains null bytes")
    # Normalise Windows backslashes to forward slashes, then let Path handle it
    return raw_path.replace("\\", "/")


def resolve_safe_path(file_path: str) -> Path:
    """Resolve *file_path* to an absolute, canonical path under the snapshot root.

    Raises ``ValueError`` if the resolved path escapes the snapshot directory.
    Returns the resolved ``Path`` on success.
    """
    cleaned = _sanitise_path(file_path)

    # If the path is already absolute (e.g. from the DB), resolve it directly.
    # If relative, resolve against the snapshot root.
    candidate = Path(cleaned)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (_SNAPSHOT_ROOT / candidate).resolve()

    # Canonical root for comparison
    root = _SNAPSHOT_ROOT

    # Pathlib's resolve() on Windows needs careful prefix check
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError(
            f"Access denied: path escapes snapshot directory. "
            f"resolved={resolved} root={root}"
        )

    return resolved


# ── DB helpers ───────────────────────────────────────────────

async def get_page_by_id(db: AsyncSession, page_id: int) -> Optional[Page]:
    """Fetch a page row by primary key."""
    result = await db.execute(select(Page).where(Page.id == page_id))
    return result.scalar_one_or_none()


# ── Snapshot reading ─────────────────────────────────────────

def read_snapshot_html(file_path: Path) -> str:
    """Read the raw HTML from *file_path* and inject the notice bar.

    Returns the full HTML string.
    Raises ``FileNotFoundError`` if the file does not exist.
    """
    if not file_path.is_file():
        raise FileNotFoundError(f"Snapshot file not found: {file_path}")

    raw_html = file_path.read_text(encoding="utf-8")

    # Inject notice bar after <body> if present; otherwise prepend
    if _BODY_RE.search(raw_html):
        injected = _BODY_RE.sub(r"\1" + NOTICE_BAR_HTML, raw_html, count=1)
    else:
        injected = NOTICE_BAR_HTML + raw_html

    return injected


# ── High-level service functions ─────────────────────────────

async def get_snapshot_by_page_id(
    db: AsyncSession, page_id: int
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(html, error_message)`` for a page ID.

    - If successful, ``html`` is the full page HTML with notice bar,
      ``error_message`` is ``None``.
    - On failure, ``html`` is ``None`` and ``error_message`` explains why.
    """
    page = await get_page_by_id(db, page_id)
    if page is None:
        return None, f"Page with id={page_id} not found"

    raw_path = (page.snapshot_path or "").strip()
    if not raw_path:
        return None, f"Page id={page_id} has no snapshot"

    try:
        safe_path = resolve_safe_path(raw_path)
        html = read_snapshot_html(safe_path)
        return html, None
    except ValueError as exc:
        return None, f"Path security check failed: {exc}"
    except FileNotFoundError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Failed to read snapshot: {exc}"


async def get_snapshot_by_raw_path(
    snapshot_path: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(html, error_message)`` for a user-supplied snapshot path.

    Applies strict path traversal checks.
    """
    if not snapshot_path or not snapshot_path.strip():
        return None, "snapshot_path query parameter is required"

    try:
        safe_path = resolve_safe_path(snapshot_path.strip())
        html = read_snapshot_html(safe_path)
        return html, None
    except ValueError as exc:
        return None, f"Path security check failed: {exc}"
    except FileNotFoundError as exc:
        return None, str(exc)
    except Exception as exc:
        return None, f"Failed to read snapshot: {exc}"
