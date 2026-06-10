from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PageLink(Base):
    __tablename__ = "page_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, index=True
    )
    to_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, index=True
    )
    anchor_text: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
