"""MTQ B2-B4 tables (migrations 0201_mtq_estimation, 0202_mtq_commercial; blueprint §4.2, §4.3).

Quantities are integer hundredths (``*_centi``) and money integer paise (``*_minor``), never floats. Every revisioned
aggregate (scope, BOQ, estimate, quotation) stores the id, revision number and sealed digest of the upstream revision
it was built from, so a quotation line can be walked back to the measured wall it came from. Historical revisions are
never edited: a change upstream makes a new revision downstream.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, Bool, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

from . import vocab as V


def _fk(target: str):
    return ForeignKey(target, ondelete="RESTRICT")


def _one(table: str, status: str) -> dict:
    return where(f"status = '{status}' AND is_deleted = 0", f"status = '{status}' AND is_deleted = false")


def _sha(table: str, col: str = "snapshot_sha256") -> CheckConstraint:
    return CheckConstraint(f"{col} IS NULL OR length({col}) = 64", name=f"ck_{table}__{col}_len")


# --- B2: requirements --------------------------------------------------------------------------------------------------
class Requirement(AuditedBase):
    """A need for one space (or the whole project) with its provenance and the staff decision on it."""

    __tablename__ = "requirement"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))  # NULL: project-level
    requirement_type_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    custom_label: Mapped[str | None] = mapped_column(sa.String(120))
    necessity_code: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="PROPOSED")
    source_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    # Provenance: rule key, template key and version, ruleset version and digest, the measurement set it fired on.
    source_ref: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    anchor_wall_index: Mapped[int | None] = mapped_column(sa.Integer)  # wall indexes are stable across revisions
    instance_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default="1")
    # One requirement per (space or project, type, anchor or instance): duplicate scope is refused by this key.
    dedupe_key: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    preferences: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # card options, finish
    notes: Mapped[str | None] = mapped_column(sa.Text)
    decided_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision_reason: Mapped[str | None] = mapped_column(sa.String(500))

    __table_args__ = (
        in_check("requirement", "requirement_type_code", V.REQUIREMENT_TYPES),
        in_check("requirement", "necessity_code", V.NECESSITIES),
        in_check("requirement", "status", V.REQUIREMENT_STATUSES),
        in_check("requirement", "source_code", V.REQUIREMENT_SOURCES),
        CheckConstraint(
            "requirement_type_code <> 'CUSTOM' OR custom_label IS NOT NULL", name="ck_requirement__custom_label"
        ),
        CheckConstraint("instance_no >= 1", name="ck_requirement__instance_no"),
        CheckConstraint(
            "status = 'PROPOSED' OR (decided_by IS NOT NULL AND decided_on IS NOT NULL)",
            name="ck_requirement__decided",
        ),
        Index("ux_requirement__property_dedupe", "property_id", "dedupe_key", unique=True, **live_where()),
        Index("ix_requirement__lead_id", "lead_id"),
        Index("ix_requirement__space_id", "space_id"),
    )


# --- B2: scope ---------------------------------------------------------------------------------------------------------
class Scope(AuditedBase):
    """One revision of a property's scope, built from the accepted requirements over one verified measurement set."""

    __tablename__ = "scope"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    measurement_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    measurement_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    supersedes_scope_id: Mapped[str | None] = mapped_column(GUID(), _fk("scope.id"))
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="DRAFT")
    tier_code: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="ESSENTIAL")
    ruleset_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    ruleset_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    ruleset_status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    # Digest of the property's requirement decisions this revision was built from (lineage.requirements_sha256): a
    # later decision changes it and makes the revision, and everything built on it, stale.
    requirements_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    generation_run: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    exclusions: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)  # declined requirements
    confirmed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    confirmed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        in_check("scope", "status", V.SCOPE_STATUSES),
        in_check("scope", "tier_code", V.TIERS),
        CheckConstraint("revision_no >= 1", name="ck_scope__revision_no"),
        _sha("scope"),
        CheckConstraint(
            "status = 'DRAFT' OR (confirmed_on IS NOT NULL AND confirmed_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_scope__confirmed_sealed",
        ),
        CheckConstraint("supersedes_scope_id IS NULL OR supersedes_scope_id <> id", name="ck_scope__not_self"),
        Index("ux_scope__property_revision", "property_id", "revision_no", unique=True, **live_where()),
        Index("ux_scope__one_draft", "property_id", unique=True, **_one("scope", "DRAFT")),
        Index("ux_scope__one_confirmed", "property_id", unique=True, **_one("scope", "CONFIRMED")),
        Index("ix_scope__measurement_set_id", "measurement_set_id"),
        Index("ix_scope__lead_id", "lead_id"),
        Index("ix_scope__supersedes_scope_id", "supersedes_scope_id"),
    )


class ScopeItem(AuditedBase):
    """One item of a scope revision: what will be quoted, where, with its catalogue mapping and resolved dimensions."""

    __tablename__ = "scope_item"

    scope_id: Mapped[str] = mapped_column(GUID(), _fk("scope.id"), nullable=False)
    requirement_id: Mapped[str] = mapped_column(GUID(), _fk("requirement.id"), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    item_type_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    card_product_code: Mapped[str | None] = mapped_column(sa.String(40))  # NULL: no catalogue line yet
    label: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    origin_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    necessity_code: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    inclusion_code: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="INCLUDED")
    rule_key: Mapped[str | None] = mapped_column(sa.String(80))
    anchor_wall_index: Mapped[int | None] = mapped_column(sa.Integer)
    options: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # card option → choice
    finish_code: Mapped[str | None] = mapped_column(sa.String(20))  # NULL: the tier's baseline finish
    material_key: Mapped[str | None] = mapped_column(sa.String(80))
    # Resolved card inputs, each {value, unit, source, explain, measurement refs}; recomputed, never trusted from a client.
    dimensions: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    dimension_overrides: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # input → value
    override_reason: Mapped[str | None] = mapped_column(sa.String(500))
    # Staff overrides of an earlier revision made on a different (superseded) measurement set: kept here, not applied,
    # until staff confirm or replace them ({values, reason, from_scope_item_id}).
    carried_overrides: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    dimension_source_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    carried_from_item_id: Mapped[str | None] = mapped_column(GUID(), _fk("scope_item.id"))
    sort_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        in_check("scope_item", "item_type_code", V.REQUIREMENT_TYPES),
        in_check("scope_item", "origin_code", V.ITEM_ORIGINS),
        in_check("scope_item", "necessity_code", V.NECESSITIES),
        in_check("scope_item", "inclusion_code", V.INCLUSIONS),
        in_check("scope_item", "dimension_source_code", V.DIMENSION_SOURCES),
        in_check("scope_item", "finish_code", V.FINISHES, nullable=True),
        Index("ux_scope_item__scope_requirement", "scope_id", "requirement_id", unique=True, **live_where()),
        Index("ix_scope_item__requirement_id", "requirement_id"),
        Index("ix_scope_item__space_id", "space_id"),
        Index("ix_scope_item__carried_from_item_id", "carried_from_item_id"),
    )


# --- B2: BOQ -----------------------------------------------------------------------------------------------------------
class Boq(AuditedBase):
    """One BOQ revision: the quantities of a confirmed scope, by the versioned quantity engine."""

    __tablename__ = "boq"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    scope_id: Mapped[str] = mapped_column(GUID(), _fk("scope.id"), nullable=False)
    scope_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    scope_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    measurement_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    supersedes_boq_id: Mapped[str | None] = mapped_column(GUID(), _fk("boq.id"))
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="GENERATED")
    quantity_engine_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    ruleset_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    # The catalogue (rate card document) whose product lines and quantity bases the BOQ follows. Rates are not read.
    catalogue_card_id: Mapped[str] = mapped_column(GUID(), _fk("estimator_rate_card.id"), nullable=False)
    catalogue_card_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    catalogue_card_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    rounding_policy: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    issues: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    reviewed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    reviewed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("boq", "status", V.BOQ_STATUSES),
        CheckConstraint("revision_no >= 1", name="ck_boq__revision_no"),
        _sha("boq"),
        CheckConstraint(
            "status <> 'REVIEWED' OR (reviewed_on IS NOT NULL AND reviewed_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_boq__reviewed_sealed",
        ),
        CheckConstraint("supersedes_boq_id IS NULL OR supersedes_boq_id <> id", name="ck_boq__not_self"),
        Index("ux_boq__property_revision", "property_id", "revision_no", unique=True, **live_where()),
        Index("ux_boq__one_generated", "property_id", unique=True, **_one("boq", "GENERATED")),
        Index("ux_boq__one_reviewed", "property_id", unique=True, **_one("boq", "REVIEWED")),
        Index("ix_boq__scope_id", "scope_id"),
        Index("ix_boq__lead_id", "lead_id"),
        Index("ix_boq__measurement_set_id", "measurement_set_id"),
        Index("ix_boq__catalogue_card_id", "catalogue_card_id"),
        Index("ix_boq__supersedes_boq_id", "supersedes_boq_id"),
    )


class BoqLine(AuditedBase):
    """One quantity: its formula, inputs and measurement source, the calculated value and any explained override."""

    __tablename__ = "boq_line"

    boq_id: Mapped[str] = mapped_column(GUID(), _fk("boq.id"), nullable=False)
    scope_item_id: Mapped[str] = mapped_column(GUID(), _fk("scope_item.id"), nullable=False)
    requirement_id: Mapped[str] = mapped_column(GUID(), _fk("requirement.id"), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    item_type_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    card_product_code: Mapped[str | None] = mapped_column(sa.String(40))
    card_line_code: Mapped[str | None] = mapped_column(sa.String(40))
    label: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    uom_code: Mapped[str | None] = mapped_column(sa.String(4))
    formula_kind: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    formula_inputs: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    derivation: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    measurement_source: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    calculated_quantity_centi: Mapped[int | None] = mapped_column(sa.BigInteger)
    override_quantity_centi: Mapped[int | None] = mapped_column(sa.BigInteger)
    override_reason: Mapped[str | None] = mapped_column(sa.String(500))
    override_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    override_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    final_quantity_centi: Mapped[int | None] = mapped_column(sa.BigInteger)
    is_optional: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    dimension_source_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(8), nullable=False, default="OK")
    quantity_status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="VALID")
    issue_codes: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)

    __table_args__ = (
        in_check("boq_line", "uom_code", V.UOMS, nullable=True),
        in_check("boq_line", "formula_kind", V.FORMULA_KINDS),
        in_check("boq_line", "dimension_source_code", V.DIMENSION_SOURCES),
        in_check("boq_line", "status", V.LINE_STATUSES),
        in_check("boq_line", "quantity_status", V.QUANTITY_STATUSES),
        CheckConstraint(
            "calculated_quantity_centi IS NULL OR calculated_quantity_centi >= 0", name="ck_boq_line__calculated_nn"
        ),
        CheckConstraint(
            "override_quantity_centi IS NULL OR override_quantity_centi >= 0", name="ck_boq_line__override_nn"
        ),
        CheckConstraint(
            "override_quantity_centi IS NULL OR (override_reason IS NOT NULL AND override_by IS NOT NULL "
            "AND override_on IS NOT NULL)",
            name="ck_boq_line__override_explained",
        ),
        CheckConstraint(
            "final_quantity_centi IS NULL OR final_quantity_centi = coalesce(override_quantity_centi, calculated_quantity_centi)",
            name="ck_boq_line__final",
        ),
        Index("ux_boq_line__boq_position", "boq_id", "position", unique=True, **live_where()),
        Index("ix_boq_line__scope_item_id", "scope_item_id"),
        Index("ix_boq_line__requirement_id", "requirement_id"),
        Index("ix_boq_line__space_id", "space_id"),
    )


B2_TABLES = ("requirement", "scope", "scope_item", "boq", "boq_line")


# --- B3: internal estimate ---------------------------------------------------------------------------------------------
class CostEstimate(AuditedBase):
    """One estimate revision: a reviewed BOQ priced with the rate card in force, every rate pinned (reproducible)."""

    __tablename__ = "cost_estimate"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    boq_id: Mapped[str] = mapped_column(GUID(), _fk("boq.id"), nullable=False)
    boq_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    boq_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    scope_id: Mapped[str] = mapped_column(GUID(), _fk("scope.id"), nullable=False)
    scope_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    measurement_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    supersedes_estimate_id: Mapped[str | None] = mapped_column(GUID(), _fk("cost_estimate.id"))
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="DRAFT")
    tier_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    # Pricing provenance: the rate card row, its version and document digest, and the engine rules version.
    rate_card_id: Mapped[str] = mapped_column(GUID(), _fk("estimator_rate_card.id"), nullable=False)
    rate_card_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    rate_card_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    calculation_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    policy_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    pricing_basis_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, default="INR", server_default="INR")
    subtotal_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)  # priced included lines
    optional_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    taxable_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    tax_status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    total_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    unpriced_lines: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    blockers: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    approved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (
        in_check("cost_estimate", "status", V.ESTIMATE_STATUSES),
        in_check("cost_estimate", "tier_code", V.TIERS),
        in_check("cost_estimate", "pricing_basis_code", V.PRICING_BASES),
        in_check("cost_estimate", "tax_status", V.TAX_STATUSES),
        CheckConstraint("revision_no >= 1", name="ck_cost_estimate__revision_no"),
        _sha("cost_estimate"),
        CheckConstraint(
            "subtotal_minor >= 0 AND optional_minor >= 0 AND discount_minor >= 0 AND discount_minor <= subtotal_minor "
            "AND taxable_minor = subtotal_minor - discount_minor",
            name="ck_cost_estimate__amounts",
        ),
        CheckConstraint(
            "(tax_status = 'APPLIED' AND tax_minor IS NOT NULL AND total_minor = taxable_minor + tax_minor) "
            "OR (tax_status = 'GST_POLICY_REQUIRED' AND tax_minor IS NULL AND total_minor IS NULL)",
            name="ck_cost_estimate__tax",
        ),
        CheckConstraint(
            "status <> 'APPROVED' OR (approved_on IS NOT NULL AND approved_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_cost_estimate__approved_sealed",
        ),
        CheckConstraint(
            "supersedes_estimate_id IS NULL OR supersedes_estimate_id <> id", name="ck_cost_estimate__not_self"
        ),
        Index("ux_cost_estimate__property_revision", "property_id", "revision_no", unique=True, **live_where()),
        Index("ux_cost_estimate__one_draft", "property_id", unique=True, **_one("cost_estimate", "DRAFT")),
        Index("ux_cost_estimate__one_approved", "property_id", unique=True, **_one("cost_estimate", "APPROVED")),
        Index("ix_cost_estimate__boq_id", "boq_id"),
        Index("ix_cost_estimate__scope_id", "scope_id"),
        Index("ix_cost_estimate__lead_id", "lead_id"),
        Index("ix_cost_estimate__measurement_set_id", "measurement_set_id"),
        Index("ix_cost_estimate__rate_card_id", "rate_card_id"),
        Index("ix_cost_estimate__supersedes_estimate_id", "supersedes_estimate_id"),
    )


class CostEstimateLine(AuditedBase):
    """One priced (or explicitly unpriced) line: BOQ line → card product line → rate → amount, with discount and tax."""

    __tablename__ = "cost_estimate_line"

    estimate_id: Mapped[str] = mapped_column(GUID(), _fk("cost_estimate.id"), nullable=False)
    boq_line_id: Mapped[str | None] = mapped_column(GUID(), _fk("boq_line.id"))  # NULL: a project charge
    scope_item_id: Mapped[str | None] = mapped_column(GUID(), _fk("scope_item.id"))
    requirement_id: Mapped[str | None] = mapped_column(GUID(), _fk("requirement.id"))
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    component_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    category_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    card_product_code: Mapped[str | None] = mapped_column(sa.String(40))
    card_line_code: Mapped[str | None] = mapped_column(sa.String(40))
    prep_component_code: Mapped[str | None] = mapped_column(sa.String(40))
    item_type_code: Mapped[str | None] = mapped_column(sa.String(40))
    label: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    uom_code: Mapped[str | None] = mapped_column(sa.String(4))
    quantity_centi: Mapped[int | None] = mapped_column(sa.BigInteger)
    tier_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    finish_code: Mapped[str | None] = mapped_column(sa.String(20))
    rate_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    rate_status: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    rate_note: Mapped[str | None] = mapped_column(sa.String(500))
    amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)  # before discount
    discount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)  # allocated
    taxable_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    tax_rate_bp: Mapped[int | None] = mapped_column(sa.Integer)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    is_optional: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    dimension_source_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    __table_args__ = (
        in_check("cost_estimate_line", "component_code", V.COMPONENTS),
        in_check("cost_estimate_line", "rate_status", V.RATE_STATUSES),
        in_check("cost_estimate_line", "tier_code", V.TIERS),
        in_check("cost_estimate_line", "finish_code", V.FINISHES, nullable=True),
        in_check("cost_estimate_line", "uom_code", V.UOMS, nullable=True),
        in_check("cost_estimate_line", "dimension_source_code", V.DIMENSION_SOURCES),
        CheckConstraint(
            "(rate_status = 'PRICED' AND rate_minor IS NOT NULL AND amount_minor IS NOT NULL) "
            "OR (rate_status <> 'PRICED' AND amount_minor IS NULL)",
            name="ck_cost_estimate_line__priced",
        ),
        CheckConstraint(
            "coalesce(rate_minor, 0) >= 0 AND coalesce(amount_minor, 0) >= 0 AND discount_minor >= 0 "
            "AND discount_minor <= coalesce(amount_minor, 0)",
            name="ck_cost_estimate_line__amounts",
        ),
        Index("ux_cost_estimate_line__position", "estimate_id", "position", unique=True, **live_where()),
        Index("ix_cost_estimate_line__boq_line_id", "boq_line_id"),
        Index("ix_cost_estimate_line__scope_item_id", "scope_item_id"),
        Index("ix_cost_estimate_line__requirement_id", "requirement_id"),
        Index("ix_cost_estimate_line__space_id", "space_id"),
    )


class CostEstimateAdjustment(AuditedBase):
    """A discount (line, category or project) with its pre/post values, reason, authority and approval. It never
    changes a rate: the line keeps its card rate and amount; the discount is allocated beside them."""

    __tablename__ = "cost_estimate_adjustment"

    estimate_id: Mapped[str] = mapped_column(GUID(), _fk("cost_estimate.id"), nullable=False)
    scope_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    target_line_id: Mapped[str | None] = mapped_column(GUID(), _fk("cost_estimate_line.id"))
    target_category: Mapped[str | None] = mapped_column(sa.String(20))
    kind_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    value_bp: Mapped[int | None] = mapped_column(sa.Integer)
    amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    base_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)  # pre-discount value of the target
    discount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    post_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="PROPOSED")
    authority_code: Mapped[str | None] = mapped_column(sa.String(15))
    policy_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision_note: Mapped[str | None] = mapped_column(sa.String(500))

    __table_args__ = (
        in_check("cost_estimate_adjustment", "scope_code", V.ADJUSTMENT_SCOPES),
        in_check("cost_estimate_adjustment", "kind_code", V.ADJUSTMENT_KINDS),
        in_check("cost_estimate_adjustment", "status", V.ADJUSTMENT_STATUSES),
        in_check("cost_estimate_adjustment", "authority_code", V.AUTHORITIES, nullable=True),
        CheckConstraint(
            "(kind_code = 'PERCENT' AND value_bp BETWEEN 1 AND 10000 AND amount_minor IS NULL) "
            "OR (kind_code = 'AMOUNT' AND amount_minor > 0 AND value_bp IS NULL)",
            name="ck_cost_estimate_adjustment__value",
        ),
        CheckConstraint(
            "discount_minor >= 0 AND discount_minor <= base_minor AND post_minor = base_minor - discount_minor",
            name="ck_cost_estimate_adjustment__amounts",
        ),
        CheckConstraint(
            "(scope_code = 'LINE') = (target_line_id IS NOT NULL) AND (scope_code = 'CATEGORY') = (target_category IS NOT NULL)",
            name="ck_cost_estimate_adjustment__target",
        ),
        CheckConstraint(
            "status = 'PROPOSED' OR (decided_by IS NOT NULL AND decided_on IS NOT NULL)",
            name="ck_cost_estimate_adjustment__decided",
        ),
        Index("ix_cost_estimate_adjustment__estimate_id", "estimate_id"),
        Index("ix_cost_estimate_adjustment__target_line_id", "target_line_id"),
    )


B3_TABLES = ("cost_estimate", "cost_estimate_line", "cost_estimate_adjustment")


# --- B4: quotation -----------------------------------------------------------------------------------------------------
_OPEN = "status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED')"


class Quotation(AuditedBase):
    """One version of a customer quotation (or of a variation to an accepted one), frozen from ISSUED on."""

    __tablename__ = "quotation"

    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # stable across versions
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    quotation_kind: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="BASE")
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)  # 0 = the base quotation
    variation_of_quotation_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation.id"))
    baseline_quotation_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation.id"))  # accepted baseline
    supersedes_quotation_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation.id"))
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    measurement_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    scope_id: Mapped[str] = mapped_column(GUID(), _fk("scope.id"), nullable=False)
    scope_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    boq_id: Mapped[str] = mapped_column(GUID(), _fk("boq.id"), nullable=False)
    boq_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cost_estimate_id: Mapped[str] = mapped_column(GUID(), _fk("cost_estimate.id"), nullable=False)
    estimate_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    estimate_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="DRAFT")
    title: Mapped[str] = mapped_column(sa.String(160), nullable=False)
    cover_note: Mapped[str | None] = mapped_column(sa.Text)  # customer-facing
    tier_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    policy_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    terms: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # terms snapshot (policy + scope)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, default="INR", server_default="INR")
    base_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)  # included, pre-discount
    optional_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    discount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    taxable_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    tax_status: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    total_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    blockers: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)  # customer-issuance blockers
    submitted_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    approved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    issued_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    issued_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    valid_until: Mapped[date | None] = mapped_column(sa.Date)
    snapshot: Mapped[dict | None] = mapped_column(JSONType())  # the customer document, set on ISSUED
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    # The customer HTML frozen at ISSUE with the pinned template version: an issued quotation renders this, never the
    # current template; a digest mismatch refuses to render (rendering.rendered).
    template_version: Mapped[str | None] = mapped_column(sa.String(40))
    issued_html: Mapped[str | None] = mapped_column(sa.Text)
    issued_html_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    decision_method: Mapped[str | None] = mapped_column(sa.String(16))
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision_recorded_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    selected_optional_line_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    accepted_total_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    # The effective accepted customer baseline, frozen at ACCEPTED: included lines plus the optional items the customer
    # chose (variations.effective_baseline). Variations compare against it; the issued document is never changed.
    accepted_baseline: Mapped[list | None] = mapped_column(JSONType())
    accepted_baseline_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    decision_note: Mapped[str | None] = mapped_column(sa.String(1000))

    __table_args__ = (
        in_check("quotation", "status", V.QUOTATION_STATUSES),
        in_check("quotation", "quotation_kind", V.QUOTATION_KINDS),
        in_check("quotation", "tier_code", V.TIERS),
        in_check("quotation", "tax_status", V.TAX_STATUSES),
        in_check("quotation", "decision_method", V.DECISION_METHODS, nullable=True),
        CheckConstraint("version_no >= 1 AND variation_no >= 0", name="ck_quotation__numbers"),
        CheckConstraint(
            "(quotation_kind = 'BASE') = (variation_no = 0) AND (quotation_kind = 'BASE') = (variation_of_quotation_id IS NULL)",
            name="ck_quotation__kind",
        ),
        _sha("quotation"),
        _sha("quotation", "issued_html_sha256"),
        _sha("quotation", "accepted_baseline_sha256"),
        CheckConstraint(
            "status IN ('DRAFT', 'INTERNAL_REVIEW', 'APPROVED') OR status = 'SUPERSEDED' "
            "OR (issued_on IS NOT NULL AND snapshot_sha256 IS NOT NULL AND total_minor IS NOT NULL "
            "AND issued_html_sha256 IS NOT NULL AND template_version IS NOT NULL)",
            name="ck_quotation__issued_frozen",
        ),
        CheckConstraint(
            "status NOT IN ('ACCEPTED', 'REJECTED') OR (decided_on IS NOT NULL AND decision_recorded_by IS NOT NULL "
            "AND decision_method IS NOT NULL)",
            name="ck_quotation__decided",
        ),
        CheckConstraint(
            "status <> 'ACCEPTED' OR (accepted_total_minor IS NOT NULL AND accepted_baseline_sha256 IS NOT NULL)",
            name="ck_quotation__accepted",
        ),
        CheckConstraint(
            "optional_minor >= 0 AND discount_minor >= 0 AND taxable_minor = base_total_minor - discount_minor "
            "AND (quotation_kind = 'VARIATION' OR base_total_minor >= 0)",  # a variation's net change may be negative
            name="ck_quotation__amounts",
        ),
        Index(
            "ux_quotation__number_variation_version",
            "quotation_number",
            "variation_no",
            "version_no",
            unique=True,
            **live_where(),
        ),  # fmt: skip
        Index(
            "ux_quotation__one_open",
            "quotation_number",
            "variation_no",
            unique=True,
            **where(f"{_OPEN} AND is_deleted = 0", f"{_OPEN} AND is_deleted = false"),
        ),
        Index("ix_quotation__property_id", "property_id"),
        Index("ix_quotation__lead_id", "lead_id"),
        Index("ix_quotation__cost_estimate_id", "cost_estimate_id"),
        Index("ix_quotation__scope_id", "scope_id"),
        Index("ix_quotation__boq_id", "boq_id"),
        Index("ix_quotation__measurement_set_id", "measurement_set_id"),
        Index("ix_quotation__variation_of", "variation_of_quotation_id"),
        Index("ix_quotation__baseline", "baseline_quotation_id"),
        Index("ix_quotation__supersedes", "supersedes_quotation_id"),
        Index("ix_quotation__status_valid_until", "status", "valid_until"),
    )


class QuotationSection(AuditedBase):
    __tablename__ = "quotation_section"

    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section_code: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    title: Mapped[str] = mapped_column(sa.String(120), nullable=False)
    subtotal_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    optional_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)

    __table_args__ = (
        in_check("quotation_section", "section_code", V.SECTION_CODES),
        Index("ux_quotation_section__position", "quotation_id", "position", unique=True, **live_where()),
        Index("ix_quotation_section__space_id", "space_id"),
    )


class QuotationLine(AuditedBase):
    """A customer-facing line. The unit rate is stored for reconciliation and shown only if OI-MTQ-10 allows."""

    __tablename__ = "quotation_line"

    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    section_id: Mapped[str] = mapped_column(GUID(), _fk("quotation_section.id"), nullable=False)
    cost_estimate_line_id: Mapped[str | None] = mapped_column(GUID(), _fk("cost_estimate_line.id"))
    requirement_id: Mapped[str | None] = mapped_column(GUID(), _fk("requirement.id"))
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    line_key: Mapped[str] = mapped_column(sa.String(200), nullable=False)  # stable across versions and variations
    description: Mapped[str] = mapped_column(sa.String(300), nullable=False)
    detail: Mapped[str | None] = mapped_column(sa.String(300))
    uom_code: Mapped[str | None] = mapped_column(sa.String(4))
    quantity_centi: Mapped[int | None] = mapped_column(sa.BigInteger)
    finish_code: Mapped[str | None] = mapped_column(sa.String(20))
    rate_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    discount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False, default=0)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    is_priced: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    is_optional: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    is_mandatory: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    change_code: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="NONE")
    baseline_amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    delta_amount_minor: Mapped[int | None] = mapped_column(sa.BigInteger)

    __table_args__ = (
        in_check("quotation_line", "change_code", V.CHANGE_CODES),
        in_check("quotation_line", "uom_code", V.UOMS, nullable=True),
        CheckConstraint("is_priced OR amount_minor IS NULL", name="ck_quotation_line__unpriced"),
        Index("ux_quotation_line__position", "quotation_id", "position", unique=True, **live_where()),
        Index("ix_quotation_line__section_id", "section_id"),
        Index("ix_quotation_line__cost_estimate_line_id", "cost_estimate_line_id"),
        Index("ix_quotation_line__requirement_id", "requirement_id"),
        Index("ix_quotation_line__space_id", "space_id"),
    )


class QuotationEvent(AuditedBase):
    """The quotation's lifecycle, append-only by service rule (each row is also FULL-audited)."""

    __tablename__ = "quotation_event"

    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    event_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    from_status: Mapped[str | None] = mapped_column(sa.String(16))
    to_status: Mapped[str | None] = mapped_column(sa.String(16))
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    __table_args__ = (
        in_check("quotation_event", "event_code", V.QUOTATION_EVENTS),
        Index("ix_quotation_event__quotation", "quotation_id", "created_on"),
    )


B4_TABLES = ("quotation", "quotation_section", "quotation_line", "quotation_event")
