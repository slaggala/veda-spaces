"""Budgetary Estimate tables (ADR-012 §4, owner instruction 2026-10-08 Part G).

No table here holds personal data: an estimate is rooms, measurements and preferences. Personal data enters only
through a consented enquiry, as a `lead`, which `budget_estimate_lead_link` connects. Money is integer paise
(`*_minor`); quantities are integer hundredths (`*_centi`), never floats.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

CARD_STATUSES = ("DRAFT", "ACTIVE", "RETIRED")
PACKAGES = ("ESSENTIAL", "PREMIUM", "LUXURY")
PROPERTY_TYPES = ("APARTMENT", "VILLA")
HOME_SIZES = ("1BHK", "2BHK", "3BHK", "4BHK", "CUSTOM")
PROJECT_KINDS = ("NEW_HOME", "RENOVATION")
ESTIMATE_ORIGINS = ("PUBLIC", "STAFF")
UOMS = ("SFT", "RFT", "NOS", "LUMP")
CONTACT_METHODS = ("PHONE", "WHATSAPP", "EMAIL")
EVENT_TYPES = (
    "CARD_LOADED",
    "CARD_ACTIVATED",
    "CARD_RETIRED",
    "CARD_ROLLED_BACK",
    "ESTIMATE_CREATED",
    "ESTIMATE_LINKED",
    "ESTIMATE_DUPLICATED",
    "ESTIMATE_REVISED",
    "CONSULTATION_COPY",
    "SITE_MEASUREMENT_REQUIRED",
    "QUOTATION_PROCESS_STARTED",
    "ESTIMATE_EXPIRED",
)
SPEC_EVENT_TYPES = ("SPEC_LOADED", "SPEC_ACTIVATED", "SPEC_RETIRED", "SPEC_ROLLED_BACK")
_ACTIVE_LIVE = "status = 'ACTIVE' AND is_deleted = 0"


class EstimatorRateCard(AuditedBase):
    """A versioned rate card. The validated document is kept whole, so every estimate can be reproduced."""

    __tablename__ = "estimator_rate_card"

    card_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="DRAFT", server_default="DRAFT")
    effective_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    calculation_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    document: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    document_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    approval_reference: Mapped[str | None] = mapped_column(sa.String(200))
    activated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activated_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    retired_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("estimator_rate_card", "status", CARD_STATUSES),
        CheckConstraint("length(document_sha256) = 64", name="ck_estimator_rate_card__sha_len"),
        Index("ux_estimator_rate_card__card_version", "card_version", unique=True, **live_where()),
        Index(
            "ux_estimator_rate_card__one_active",
            "status",
            unique=True,
            **where(_ACTIVE_LIVE, "status = 'ACTIVE' AND is_deleted = false"),
        ),
    )


class EstimatorRateItem(AuditedBase):
    """One priced line of a rate card, flattened from its document for staff review (the engine reads the document)."""

    __tablename__ = "estimator_rate_item"

    rate_card_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("estimator_rate_card.id", ondelete="RESTRICT"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    line_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    uom: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    rate_essential_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    rate_premium_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    rate_luxury_minor: Mapped[int | None] = mapped_column(sa.BigInteger)

    __table_args__ = (
        in_check("estimator_rate_item", "uom", UOMS),
        CheckConstraint(
            "coalesce(rate_essential_minor, 0) >= 0 AND coalesce(rate_premium_minor, 0) >= 0 "
            "AND coalesce(rate_luxury_minor, 0) >= 0",
            name="ck_estimator_rate_item__rates_nonneg",
        ),
        Index(
            "ux_estimator_rate_item__card_line",
            "rate_card_id",
            "product_code",
            "line_code",
            unique=True,
            **live_where(),
        ),
    )


class BudgetEstimate(AuditedBase):
    """An immutable Budgetary Estimate: inputs, the rule versions used and the computed result."""

    __tablename__ = "budget_estimate"

    public_reference: Mapped[str] = mapped_column(sa.String(9), nullable=False)
    rate_card_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("estimator_rate_card.id", ondelete="RESTRICT"), nullable=False
    )
    rate_card_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    calculation_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    origin: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    source_estimate_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT")
    )
    package: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    property_type: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    home_size: Mapped[str] = mapped_column(sa.String(6), nullable=False)
    project_kind: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    city: Mapped[str | None] = mapped_column(sa.String(60))
    inputs: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    result: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, default="INR", server_default="INR")
    base_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    range_low_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    range_high_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    preparation_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    # The customer specification shown with this estimate (ADR-012 T9), frozen at creation: later specification
    # versions never change it. Null when no specification was active (added by 0102).
    customer_spec_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("estimator_customer_spec.id", ondelete="RESTRICT")
    )
    customer_spec_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    # Custom Features Allowance (D9): the midpoint is part of base_minor; the band is part of the range.
    allowance_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    allowance_low_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    allowance_high_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    optional_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gst_low_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    gst_high_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    timeline_min_days: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    timeline_max_days: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    budget_range_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    project_type_code: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    site_measurement_required: Mapped[bool] = mapped_column(
        Bool(), nullable=False, default=False, server_default=sa.false()
    )

    __table_args__ = (
        in_check("budget_estimate", "origin", ESTIMATE_ORIGINS),
        in_check("budget_estimate", "package", PACKAGES),
        in_check("budget_estimate", "property_type", PROPERTY_TYPES),
        in_check("budget_estimate", "home_size", HOME_SIZES),
        in_check("budget_estimate", "project_kind", PROJECT_KINDS),
        CheckConstraint(
            "base_minor >= 0 AND range_low_minor >= 0 AND range_low_minor <= base_minor "
            "AND base_minor <= range_high_minor AND preparation_minor >= 0 AND optional_minor >= 0 "
            "AND allowance_low_minor >= 0 AND allowance_low_minor <= allowance_minor "
            "AND allowance_minor <= allowance_high_minor "
            "AND gst_low_minor >= 0 AND gst_high_minor >= gst_low_minor",
            name="ck_budget_estimate__amounts",
        ),
        CheckConstraint(
            "timeline_min_days >= 1 AND timeline_max_days >= timeline_min_days", name="ck_budget_estimate__timeline"
        ),
        Index("ux_budget_estimate__public_reference", "public_reference", unique=True),
        Index("ix_budget_estimate__expires", "expires_on", **live_where()),
        Index("ix_budget_estimate__source", "source_estimate_id", **live_where()),
    )


class BudgetEstimateLine(AuditedBase):
    __tablename__ = "budget_estimate_line"

    estimate_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    room: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    instance: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    line_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    uom: Mapped[str] = mapped_column(sa.String(4), nullable=False)
    quantity_centi: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    rate_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    is_typical: Mapped[bool] = mapped_column(Bool(), nullable=False)
    is_optional: Mapped[bool] = mapped_column(Bool(), nullable=False)

    __table_args__ = (
        in_check("budget_estimate_line", "uom", UOMS),
        CheckConstraint(
            "quantity_centi > 0 AND rate_minor >= 0 AND amount_minor >= 0", name="ck_budget_estimate_line__amounts"
        ),
        Index("ux_budget_estimate_line__position", "estimate_id", "position", unique=True, **live_where()),
    )


class BudgetEstimateAssumption(AuditedBase):
    __tablename__ = "budget_estimate_assumption"

    estimate_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    room: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    instance: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    input_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    value_centi: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    unit: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    text: Mapped[str] = mapped_column(sa.String(300), nullable=False)

    __table_args__ = (
        Index("ux_budget_estimate_assumption__position", "estimate_id", "position", unique=True, **live_where()),
    )


class BudgetEstimateProjectItem(AuditedBase):
    """A component of the Project Preparation & Protection Package (internal detail; customers see the total)."""

    __tablename__ = "budget_estimate_project_item"

    estimate_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"), nullable=False
    )
    component_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    inclusion: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint("amount_minor >= 0", name="ck_budget_estimate_project_item__amount"),
        Index(
            "ux_budget_estimate_project_item__component", "estimate_id", "component_code", unique=True, **live_where()
        ),
    )


class BudgetEstimateLeadLink(AuditedBase):
    """The consented enquiry that an estimate became. One lead per estimate."""

    __tablename__ = "budget_estimate_lead_link"

    estimate_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[str] = mapped_column(GUID(), ForeignKey("lead.id", ondelete="RESTRICT"), nullable=False)
    consent_policy_version: Mapped[str | None] = mapped_column(sa.String(40))
    preferred_contact: Mapped[str | None] = mapped_column(sa.String(10))
    linked_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        in_check("budget_estimate_lead_link", "preferred_contact", CONTACT_METHODS, nullable=True),
        Index("ux_budget_estimate_lead_link__estimate", "estimate_id", unique=True, **live_where()),
        Index("ix_budget_estimate_lead_link__lead", "lead_id", **live_where()),
    )


class EstimateEvent(AuditedBase):
    """What happened to a rate card or an estimate, and who did it (`created_by`)."""

    __tablename__ = "estimate_event"

    event_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    estimate_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("budget_estimate.id", ondelete="RESTRICT"))
    rate_card_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("estimator_rate_card.id", ondelete="RESTRICT"))
    detail: Mapped[dict | None] = mapped_column(JSONType())

    __table_args__ = (
        in_check("estimate_event", "event_type", EVENT_TYPES),
        CheckConstraint("estimate_id IS NOT NULL OR rate_card_id IS NOT NULL", name="ck_estimate_event__subject"),
        Index("ix_estimate_event__estimate", "estimate_id", "created_on", **live_where()),
        Index("ix_estimate_event__card", "rate_card_id", "created_on", **live_where()),
    )


# --- customer specification master (ADR-012 T9) ---------------------------------------------------------------------


class EstimatorCustomerSpec(AuditedBase):
    """A versioned customer-facing material specification for one package (no rates, no costs). The validated
    document is kept whole and never edited: a change is a new version, so estimates keep what they were shown."""

    __tablename__ = "estimator_customer_spec"

    spec_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    spec_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    package: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="DRAFT", server_default="DRAFT")
    effective_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    document: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    document_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    approval_reference: Mapped[str | None] = mapped_column(sa.String(200))
    activated_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    activated_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="RESTRICT"))
    retired_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("estimator_customer_spec", "status", CARD_STATUSES),
        in_check("estimator_customer_spec", "package", PACKAGES),
        CheckConstraint("length(document_sha256) = 64", name="ck_estimator_customer_spec__sha_len"),
        Index("ux_estimator_customer_spec__spec_code", "spec_code", unique=True, **live_where()),
        Index(
            "ux_estimator_customer_spec__one_active",
            "package",
            unique=True,
            **where(_ACTIVE_LIVE, "status = 'ACTIVE' AND is_deleted = false"),
        ),
    )


class EstimatorCustomerSpecItem(AuditedBase):
    """One material category of a customer specification, flattened for staff review."""

    __tablename__ = "estimator_customer_spec_item"

    customer_spec_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("estimator_customer_spec.id", ondelete="RESTRICT"), nullable=False
    )
    category_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(80), nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    requirement: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    grade: Mapped[str | None] = mapped_column(sa.String(160))
    thickness: Mapped[str | None] = mapped_column(sa.String(300))
    finish: Mapped[str | None] = mapped_column(sa.String(160))
    brand_examples: Mapped[str | None] = mapped_column(sa.String(400))
    equivalent_rule: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    final_selection: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    hardware_category: Mapped[str | None] = mapped_column(sa.String(80))
    warranty_summary: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    applicability: Mapped[dict] = mapped_column(JSONType(), nullable=False)  # rooms and products it applies to

    __table_args__ = (
        Index(
            "ux_estimator_customer_spec_item__spec_category",
            "customer_spec_id",
            "category_code",
            unique=True,
            **live_where(),
        ),
    )


class EstimatorSpecEvent(AuditedBase):
    """What happened to a customer specification, and who did it (`created_by`)."""

    __tablename__ = "estimator_spec_event"

    event_type: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    customer_spec_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("estimator_customer_spec.id", ondelete="RESTRICT"), nullable=False
    )
    detail: Mapped[dict | None] = mapped_column(JSONType())

    __table_args__ = (
        in_check("estimator_spec_event", "event_type", SPEC_EVENT_TYPES),
        Index("ix_estimator_spec_event__spec", "customer_spec_id", "created_on", **live_where()),
    )
