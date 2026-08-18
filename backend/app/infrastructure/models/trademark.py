"""SQLAlchemy model for USPTO trademark records."""

from __future__ import annotations

from sqlalchemy import Boolean, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin


class TrademarkRecord(Base, UuidMixin, TimestampMixin):
    """Stores official USPTO registered trademark records for local phrase screening."""

    __tablename__ = "trademark_records"

    mark_text: Mapped[str] = mapped_column(String(512), nullable=False)
    norm_mark_text: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="REGISTERED")
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    classes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    goods_services: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filing_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    registration_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="USPTO_BULK")

    __table_args__ = (
        Index("ix_trademark_records_norm_live", "norm_mark_text", "is_live"),
        Index("ix_trademark_records_mark_text", "mark_text"),
    )
