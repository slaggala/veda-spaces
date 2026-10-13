"""MTQ B2-B4 tables (migrations 0201_mtq_estimation, 0202_mtq_commercial; blueprint §4.2, §4.3).

Quantities are integer hundredths (``*_centi``) and money integer paise (``*_minor``), never floats. Every revisioned
aggregate (scope, BOQ, estimate, quotation) stores the id, revision number and sealed digest of the upstream revision
it was built from, so a quotation line can be walked back to the measured wall it came from. Historical revisions are
never edited: a change upstream makes a new revision downstream.
"""

from __future__ import annotations

from datetime import datetime

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
            "status = 'GENERATED' OR (reviewed_on IS NOT NULL AND reviewed_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)",
            name="ck_boq__reviewed_sealed",
        ),
        CheckConstraint("supersedes_boq_id IS NULL OR supersedes_boq_id <> id", name="ck_boq__not_self"),
        Index("ux_boq__property_revision", "property_id", "revision_no", unique=True, **live_where()),
        Index("ux_boq__one_generated", "property_id", unique=True, **_one("boq", "GENERATED")),
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
    issue_codes: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)

    __table_args__ = (
        in_check("boq_line", "uom_code", V.UOMS, nullable=True),
        in_check("boq_line", "formula_kind", V.FORMULA_KINDS),
        in_check("boq_line", "dimension_source_code", V.DIMENSION_SOURCES),
        in_check("boq_line", "status", V.LINE_STATUSES),
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
