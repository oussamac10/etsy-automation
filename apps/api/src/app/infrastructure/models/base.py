"""Declarative base, shared mixins and enum helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import ENUM as PostgresEnum  # noqa: N811
from sqlalchemy.orm import Mapped, mapped_column

# Re-exported so every model imports its base from one place.
from app.infrastructure.database import Base as Base

#: Predictable constraint names, so migrations can drop what they created.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
Base.metadata.naming_convention = NAMING_CONVENTION
metadata: MetaData = Base.metadata


def pg_enum[EnumT: StrEnum](enum_type: type[EnumT], name: str) -> PostgresEnum:
    """A PostgreSQL enum column built from a domain enum.

    ``values_callable`` stores the enum *values* ("market-led") rather than the
    member names ("MARKET_LED"), so the database holds the vocabulary the
    product actually speaks and the API can round-trip it unchanged.
    """
    return PostgresEnum(
        enum_type,
        name=name,
        values_callable=lambda enum: [member.value for member in enum],
        create_type=False,
    )


def utc_now() -> datetime:
    """Timezone-aware now. Used as a Python-side default so tests can freeze it."""
    return datetime.now(UTC)


class UuidMixin:
    """UUID primary key generated in Python.

    Client-side generation means an entity has an identity before it is flushed,
    which lets a use case build a whole object graph and its audit events in one
    transaction without round-tripping for each ID.
    """

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, sort_order=-100)


class TimestampMixin:
    """Created/updated timestamps, both timezone-aware UTC."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
        sort_order=100,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        sort_order=101,
    )


class CreatedAtMixin:
    """Creation timestamp only.

    Used by append-only tables. The absence of ``updated_at`` is the point: there
    is no supported way to update an approval, an audit event or an idea
    revision, so the schema does not offer a column that implies otherwise.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
        sort_order=100,
    )


def timestamp_column(**kwargs: Any) -> Mapped[datetime]:
    """A timezone-aware timestamp column."""
    return mapped_column(DateTime(timezone=True), **kwargs)
