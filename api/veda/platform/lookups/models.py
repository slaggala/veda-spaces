"""Reference data (03 §6): lookups and business number sequences."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where
from veda.kernel.types import GUID, JSONType


class LookupCategory(AuditedBase):
    __tablename__ = "lookup_category"

    code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500))
    module: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    is_system: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())

    __table_args__ = (Index("ux_lookup_category__code", "code", unique=True, **live_where()),)


class LookupValue(AuditedBase):
    __tablename__ = "lookup_value"

    category_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("lookup_category.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.String(500))
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=100, server_default=sa.text("100"))
    is_active: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    attributes: Mapped[dict | None] = mapped_column(JSONType())

    __table_args__ = (
        Index("ux_lookup_value__category_code", "category_id", "code", unique=True, **live_where()),
        Index("ix_lookup_value__category_active", "category_id", "is_active", "sort_order"),
    )


class NumberSequence(AuditedBase):
    __tablename__ = "number_sequence"

    sequence_key: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    prefix: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    reset_period: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="YEAR", server_default="YEAR")
    current_period: Mapped[str | None] = mapped_column(sa.String(10))
    next_value: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=1, server_default=sa.text("1"))
    padding: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=6, server_default=sa.text("6"))

    __table_args__ = (
        in_check("number_sequence", "reset_period", ("NONE", "YEAR", "MONTH")),
        CheckConstraint("next_value >= 1", name="ck_number_sequence__next_value_positive"),
        CheckConstraint("padding BETWEEN 1 AND 12", name="ck_number_sequence__padding_range"),
        Index("ux_number_sequence__key", "sequence_key", unique=True, **live_where()),
    )
