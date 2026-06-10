from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(
        String(767), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    source_site: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )
    publish_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    crawl_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    snapshot_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )
    status_code: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )
    es_doc_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
