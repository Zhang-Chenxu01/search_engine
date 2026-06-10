"""Snapshot API — serve cached HTML snapshots of crawled pages."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.snapshot_service import (
    get_snapshot_by_page_id,
    get_snapshot_by_raw_path,
)

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/by-page/{page_id}")
async def snapshot_by_page(
    page_id: int,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Return the HTML snapshot for a given page ID.

    Returns 404 if the page or its snapshot file does not exist.
    """
    html, error = await get_snapshot_by_page_id(db, page_id)

    if error is not None:
        raise HTTPException(status_code=404, detail=error)

    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/raw")
async def snapshot_raw(
    snapshot_path: str = Query(..., min_length=1, description="Snapshot file path"),
) -> Response:
    """Return a snapshot HTML file by its raw filesystem path.

    The path is strictly validated to prevent directory traversal attacks —
    only files inside the configured snapshot root are accessible.
    """
    html, error = await get_snapshot_by_raw_path(snapshot_path)

    if error is not None:
        raise HTTPException(status_code=404, detail=error)

    return Response(content=html, media_type="text/html; charset=utf-8")
