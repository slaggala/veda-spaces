"""Transactional outbox and in-app notifications (03 §8, 02 §10)."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

OUTBOX_STATUSES = ("PENDING", "PROCESSING", "DONE", "FAILED", "DEAD")


class OutboxEvent(AuditedBase):
    __tablename__ = "outbox_event"

    event_type: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(GUID(), nullable=False)  # registered FK-less (EXC-011)
    payload: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="PENDING", server_default="PENDING")
    attempts: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    next_attempt_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    locked_by: Mapped[str | None] = mapped_column(sa.String(64))  # non-entity string identifier (03 §2.11.1)
    locked_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    processed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(sa.String(2000))

    __table_args__ = (
        in_check("outbox_event", "status", OUTBOX_STATUSES),
        CheckConstraint("attempts >= 0", name="ck_outbox_event__attempts"),
        CheckConstraint("is_deleted = false", name="ck_outbox_event__never_deleted"),
        Index("ix_outbox_event__due", "status", "next_attempt_on", **where("status IN ('PENDING','FAILED')")),
        Index("ix_outbox_event__aggregate", "aggregate_type", "aggregate_id"),
    )


class Notification(AuditedBase):
    __tablename__ = "notification"

    recipient_user_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False
    )
    notification_type: Mapped[str] = mapped_column(sa.String(60), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(sa.String(1000))
    entity_type: Mapped[str | None] = mapped_column(sa.String(60))
    entity_id: Mapped[str | None] = mapped_column(GUID())  # registered FK-less (EXC-011)
    link_path: Mapped[str | None] = mapped_column(sa.String(300))
    read_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    source_event_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("outbox_event.id", ondelete="RESTRICT"))

    __table_args__ = (
        CheckConstraint("(entity_type IS NULL) = (entity_id IS NULL)", name="ck_notification__entity_pair"),
        Index(
            "ix_notification__recipient_unread",
            "recipient_user_id",
            sa.text("created_on DESC"),
            **where("read_on IS NULL AND is_deleted = 0", "read_on IS NULL AND is_deleted = false"),
        ),
        Index("ix_notification__recipient_all", "recipient_user_id", sa.text("created_on DESC")),
        Index("ix_notification__entity", "entity_type", "entity_id", **where("entity_id IS NOT NULL")),
        Index(
            "ux_notification__event_recipient",
            "source_event_id",
            "recipient_user_id",
            unique=True,
            **where("source_event_id IS NOT NULL"),
        ),
    )
