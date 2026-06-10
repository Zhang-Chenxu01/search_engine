from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_file_url: Mapped[str] = mapped_column(
        String(767), unique=True, nullable=False, index=True
    )
    file_name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    local_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    parent_page_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("pages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    parent_title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    parent_url: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    source_site: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, default="", index=True
    )
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", index=True
    )
    parse_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", index=True
    )
    parse_error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    text_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    es_doc_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    crawl_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )
