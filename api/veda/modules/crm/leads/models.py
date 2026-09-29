"""Lead management tables (04 §2, §9, §10)."""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

LEAD_STATUSES = ("NEW", "CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION", "WON", "LOST")
OPEN_STATUSES = ("NEW", "CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION")
PRIORITIES = ("HIGH", "MEDIUM", "LOW")
DUPLICATE_STATUSES = ("NONE", "SUSPECTED", "CONFIRMED", "NOT_DUPLICATE")
SPAM_STATUSES = ("NONE", "SUSPECTED", "CONFIRMED_SPAM", "NOT_SPAM")
CONSENT_CHANNELS = ("WEBSITE_FORM", "PHONE_VERBAL", "IN_PERSON", "WHATSAPP", "EMAIL")
WITHDRAWAL_CHANNELS = ("PHONE_VERBAL", "IN_PERSON", "WHATSAPP", "EMAIL", "WEBSITE")

ACTIVITY_TYPES = (
    "CALL",
    "WHATSAPP",
    "EMAIL",
    "MEETING",
    "SITE_VISIT",
    "QUOTATION",
    "FOLLOW_UP",
    "STATUS_CHANGE",
    "ASSIGNMENT",
    "SYSTEM",
)
SYSTEM_ACTIVITY_TYPES = ("STATUS_CHANGE", "ASSIGNMENT", "SYSTEM")
CONTACT_ACTIVITY_TYPES = ("CALL", "WHATSAPP", "EMAIL", "MEETING", "SITE_VISIT", "FOLLOW_UP")
ACTIVITY_STATUSES = ("PLANNED", "COMPLETED", "CANCELLED")
DIRECTIONS = ("INBOUND", "OUTBOUND")
NOTE_VISIBILITIES = ("INTERNAL", "CUSTOMER_VISIBLE")

_OPEN_NOT_CLOSED = "status NOT IN ('WON','LOST')"


class Lead(AuditedBase):
    __tablename__ = "lead"

    lead_number: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    public_reference: Mapped[str] = mapped_column(sa.CHAR(9), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(150), nullable=False)
    phone: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    phone_raw: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(254))
    email_normalized: Mapped[str | None] = mapped_column(sa.String(254))
    city: Mapped[str | None] = mapped_column(sa.String(100))
    locality: Mapped[str | None] = mapped_column(sa.String(150))
    project_type_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"))
    property_type_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"))
    budget_range_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"))
    message: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="NEW", server_default="NEW")
    status_changed_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    priority: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="MEDIUM", server_default="MEDIUM")
    source_id: Mapped[str] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"), nullable=False)
    source_detail: Mapped[str | None] = mapped_column(sa.String(200))
    utm_source: Mapped[str | None] = mapped_column(sa.String(100))
    utm_medium: Mapped[str | None] = mapped_column(sa.String(100))
    utm_campaign: Mapped[str | None] = mapped_column(sa.String(100))
    utm_term: Mapped[str | None] = mapped_column(sa.String(100))
    utm_content: Mapped[str | None] = mapped_column(sa.String(100))
    landing_page: Mapped[str | None] = mapped_column(sa.String(500))
    referrer_url: Mapped[str | None] = mapped_column(sa.String(500))
    assigned_to: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    assigned_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    next_follow_up_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_activity_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    expected_close_on: Mapped[date | None] = mapped_column(sa.Date)
    quoted_amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    currency: Mapped[str] = mapped_column(sa.CHAR(3), nullable=False, default="INR", server_default="INR")
    won_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lost_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    lost_reason_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"))
    lost_reason_note: Mapped[str | None] = mapped_column(sa.String(1000))
    duplicate_status: Mapped[str] = mapped_column(sa.String(15), nullable=False, default="NONE", server_default="NONE")
    duplicate_of_lead_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lead.id", ondelete="RESTRICT"))
    consent_contact: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    consent_policy_version: Mapped[str | None] = mapped_column(sa.String(20))
    consent_captured_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    consent_channel: Mapped[str | None] = mapped_column(sa.String(20))
    consent_source_page: Mapped[str | None] = mapped_column(sa.String(500))
    consent_ip_address: Mapped[str | None] = mapped_column(sa.String(45))
    intake_idempotency_key: Mapped[str | None] = mapped_column(sa.String(64))
    intake_request_fingerprint: Mapped[str | None] = mapped_column(sa.CHAR(64))
    intake_unmapped: Mapped[dict | None] = mapped_column(JSONType())
    spam_status: Mapped[str] = mapped_column(sa.String(15), nullable=False, default="NONE", server_default="NONE")
    consent_withdrawn_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    consent_withdrawal_channel: Mapped[str | None] = mapped_column(sa.String(20))
    consent_withdrawal_note: Mapped[str | None] = mapped_column(sa.String(500))
    search_text: Mapped[str] = mapped_column(sa.Text, nullable=False, default="", server_default="")
    anonymized_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("lead", "status", LEAD_STATUSES),
        in_check("lead", "priority", PRIORITIES),
        in_check("lead", "duplicate_status", DUPLICATE_STATUSES),
        in_check("lead", "consent_channel", CONSENT_CHANNELS, nullable=True),
        in_check("lead", "spam_status", SPAM_STATUSES),
        in_check("lead", "consent_withdrawal_channel", WITHDRAWAL_CHANNELS, nullable=True),
        CheckConstraint("(status = 'WON') = (won_on IS NOT NULL)", name="ck_lead__won_consistency"),
        CheckConstraint(
            "(status = 'LOST') = (lost_on IS NOT NULL AND lost_reason_id IS NOT NULL)", name="ck_lead__lost_consistency"
        ),
        CheckConstraint("(assigned_to IS NULL) = (assigned_on IS NULL)", name="ck_lead__assigned_consistency"),
        CheckConstraint(
            "consent_contact = false OR (consent_policy_version IS NOT NULL AND consent_captured_on IS NOT NULL "
            "AND consent_channel IS NOT NULL)",
            name="ck_lead__consent_complete",
        ),
        CheckConstraint("quoted_amount_minor IS NULL OR quoted_amount_minor >= 0", name="ck_lead__quoted_amount"),
        CheckConstraint(
            "duplicate_of_lead_id IS NULL OR duplicate_of_lead_id <> id", name="ck_lead__not_self_duplicate"
        ),
        CheckConstraint(
            "consent_withdrawn_on IS NULL OR (consent_contact = false AND consent_withdrawal_channel IS NOT NULL)",
            name="ck_lead__withdrawal_consistency",
        ),
        CheckConstraint("length(message) <= 4000", name="ck_lead__message_len"),
        Index("ux_lead__lead_number", "lead_number", unique=True, **live_where()),
        Index("ux_lead__public_reference", "public_reference", unique=True),
        Index(
            "ux_lead__intake_idempotency_key",
            "intake_idempotency_key",
            unique=True,
            **where("intake_idempotency_key IS NOT NULL"),
        ),
        Index("ix_lead__status_created", "status", sa.text("created_on DESC"), **live_where()),
        Index("ix_lead__assigned_status", "assigned_to", "status", sa.text("created_on DESC"), **live_where()),
        Index("ix_lead__created_by", "created_by", **live_where()),
        Index("ix_lead__phone", "phone", **live_where()),
        Index(
            "ix_lead__email_normalized",
            "email_normalized",
            **where(
                "email_normalized IS NOT NULL AND is_deleted = 0", "email_normalized IS NOT NULL AND is_deleted = false"
            ),
        ),
        Index(
            "ix_lead__next_follow_up",
            "next_follow_up_on",
            **where(f"{_OPEN_NOT_CLOSED} AND is_deleted = 0", f"{_OPEN_NOT_CLOSED} AND is_deleted = false"),
        ),
        Index("ix_lead__created_on", sa.text("created_on DESC")),
        Index("ix_lead__source", "source_id", sa.text("created_on DESC"), **live_where()),
        Index(
            "ix_lead__spam_queue",
            "spam_status",
            sa.text("created_on DESC"),
            **where("spam_status = 'SUSPECTED' AND is_deleted = 0", "spam_status = 'SUSPECTED' AND is_deleted = false"),
        ),
        Index(
            "ix_lead__retention",
            "status",
            "status_changed_on",
            **where("status IN ('WON','LOST') AND anonymized_on IS NULL"),
        ),
    )


class LeadNote(AuditedBase):
    __tablename__ = "lead_note"

    lead_id: Mapped[str] = mapped_column(GUID(), ForeignKey("lead.id", ondelete="RESTRICT"), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    visibility: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="INTERNAL", server_default="INTERNAL"
    )

    __table_args__ = (
        in_check("lead_note", "visibility", NOTE_VISIBILITIES),
        CheckConstraint("length(body) BETWEEN 1 AND 10000", name="ck_lead_note__body_len"),
        Index(
            "ix_lead_note__lead_created",
            "lead_id",
            sa.text("is_pinned DESC"),
            sa.text("created_on DESC"),
            **live_where(),
        ),
        Index("ix_lead_note__created_by", "created_by", **live_where()),
    )


class LeadActivity(AuditedBase):
    __tablename__ = "lead_activity"

    lead_id: Mapped[str] = mapped_column(GUID(), ForeignKey("lead.id", ondelete="RESTRICT"), nullable=False)
    activity_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    is_system_generated: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    activity_status: Mapped[str] = mapped_column(
        sa.String(12), nullable=False, default="COMPLETED", server_default="COMPLETED"
    )
    subject: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    direction: Mapped[str | None] = mapped_column(sa.String(10))
    scheduled_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    duration_minutes: Mapped[int | None] = mapped_column(sa.Integer)
    outcome_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("lookup_value.id", ondelete="RESTRICT"))
    owner_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False)
    location: Mapped[str | None] = mapped_column(sa.String(300))
    from_status: Mapped[str | None] = mapped_column(sa.String(20))
    to_status: Mapped[str | None] = mapped_column(sa.String(20))
    cancelled_reason: Mapped[str | None] = mapped_column(sa.String(300))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONType())

    __table_args__ = (
        in_check("lead_activity", "activity_type", ACTIVITY_TYPES, name="ck_lead_activity__type"),
        in_check("lead_activity", "activity_status", ACTIVITY_STATUSES, name="ck_lead_activity__status"),
        in_check("lead_activity", "direction", DIRECTIONS, nullable=True),
        in_check("lead_activity", "from_status", LEAD_STATUSES, nullable=True),
        in_check("lead_activity", "to_status", LEAD_STATUSES, nullable=True),
        CheckConstraint(
            "activity_status <> 'PLANNED' OR scheduled_on IS NOT NULL", name="ck_lead_activity__planned_has_schedule"
        ),
        CheckConstraint(
            "activity_status <> 'COMPLETED' OR completed_on IS NOT NULL", name="ck_lead_activity__completed_has_time"
        ),
        CheckConstraint(
            "activity_type <> 'STATUS_CHANGE' OR (from_status IS NOT NULL AND to_status IS NOT NULL)",
            name="ck_lead_activity__status_change_fields",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes BETWEEN 0 AND 1440", name="ck_lead_activity__duration"
        ),
        CheckConstraint("length(description) <= 4000", name="ck_lead_activity__description_len"),
        Index("ix_lead_activity__lead_timeline", "lead_id", sa.text("created_on DESC"), **live_where()),
        Index(
            "ix_lead_activity__owner_planned",
            "owner_user_id",
            "scheduled_on",
            **where(
                "activity_status = 'PLANNED' AND is_deleted = 0", "activity_status = 'PLANNED' AND is_deleted = false"
            ),
        ),
        Index(
            "ix_lead_activity__lead_planned",
            "lead_id",
            "scheduled_on",
            **where(
                "activity_status = 'PLANNED' AND is_deleted = 0", "activity_status = 'PLANNED' AND is_deleted = false"
            ),
        ),
    )
