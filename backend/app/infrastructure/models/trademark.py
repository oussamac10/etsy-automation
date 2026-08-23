"""SQLAlchemy model for USPTO trademark records."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.models.base import Base, TimestampMixin, UuidMixin


class TrademarkRecord(Base, UuidMixin, TimestampMixin):
    """Stores official USPTO registered trademark records for local phrase screening."""

    __tablename__ = "trademark_records"

    mark_text: Mapped[str] = mapped_column(String(512), nullable=False)
    normalized_mark_text: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    serial_number: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    registration_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status_text: Mapped[str] = mapped_column(String(64), nullable=False, default="REGISTERED")
    is_live: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    classes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    goods_services: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    filing_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    registration_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_trademark_records_norm_live", "normalized_mark_text", "is_live"),
        Index("ix_trademark_records_mark_text", "mark_text"),
        Index(
            "ix_trademark_records_trgm",
            "normalized_mark_text",
            postgresql_using="gin",
            postgresql_ops={"normalized_mark_text": "gin_trgm_ops"},
        ),
    )
