from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ClickLog(Base):
    __tablename__ = "click_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    query_log_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="page", index=True
    )
    target_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, index=True
    )
    rank_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )
