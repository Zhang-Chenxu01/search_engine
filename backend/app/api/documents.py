"""Document API — full-text search and detail for indexed attachments."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentSearchParams,
    DocumentSearchResponse,
)
from app.search.es_client import get_es_client
from app.services.document_service import get_document_detail, search_documents

router = APIRouter(prefix="/api/documents", tags=["documents"])


# ── GET /api/documents/search ─────────────────────────────────

@router.get("/search", response_model=DocumentSearchResponse)
async def doc_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    file_type: str | None = Query(None, description="文件类型: pdf, docx, xlsx…"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> DocumentSearchResponse:
    """全文搜索附件文档（PDF / Word / Excel 等）。

    检索范围：file_name、file_text、parent_title。
    """
    es = get_es_client()
    params = DocumentSearchParams(
        q=q,
        file_type=file_type,
        page=page,
        page_size=page_size,
    )
    return await search_documents(es, db, params)


# ── GET /api/documents/{document_id} ──────────────────────────

@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def doc_detail(
    document_id: int,
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    """获取单个附件的完整元数据与文本预览。

    从 MySQL 查询元数据，若附件已在 ES 中索引则附带文本预览。
    """
    es = get_es_client()
    resp = await get_document_detail(es, db, document_id)

    if resp.code == 404:
        raise HTTPException(status_code=404, detail=resp.message)

    return resp
