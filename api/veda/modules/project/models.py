"""Project lifecycle tables (migration 0208_project_lifecycle).

Every row carries ``project_id`` and the project's ``lead_id`` (scope and erasure follow the lead, as for every MTQ row).
A project references the commercial records it was built from; it copies none of them and never writes to them:

- ``project``: identity (VS-P-…), the accepted quotation chain it executes, current stage, pinned lifecycle definition.
- ``project_baseline``: the commercial-baseline lineage, append-only: the original accepted quotation, then each
  accepted variation, with the digests that make each reproducible and a digest over the reference itself.
- ``project_stage``: one row per stage of the pinned definition (not started, active, completed; who and when).
- ``project_member``: the team, by responsibility; at most one active owner per ownership responsibility.
- ``project_transition``: every transition request, its gate evaluation (recorded, refused ones included), the
  independent approval when one is needed, and the handover details for the handover.
- ``project_checklist_item``: the execution of the pinned definition's checklists (the definition is code).
- ``project_milestone``: planned, actual and customer-promised dates kept apart; explicit completion only.
- ``project_blocker``: first-class blockers, GATING or INFORMATIONAL, with the responsible party as a code.
- ``project_site_readiness``: this project's observation of each site-readiness item the accepted quotation froze
  from the Customer Promise, plus staff-added items; never the quotation's frozen text.
- ``project_qc_check``: quality-check results, append-only (a recheck is a new row).
- ``project_snag``: snags (punch list) to resolution.
- ``project_event``: the immutable timeline: codes, ids and states only (database triggers refuse update and delete).

Execution, quality control, snags and handover (migration 0212_project_execution, PEX):

- ``project_work_package``: a body of work in one stage (optionally one space): owner, planned and actual dates kept
  apart, explicit start and completion; BLOCKED is derived from open gating blockers, never stored.
- ``project_qc_point``: the QC plan: what must be checked (category, space, work package, evidence requirement).
- ``project_customer_report``: an issue in the customer's own words, triaged by staff into a snag or declined.
- ``project_handover_package``: what is handed over, frozen with a SHA-256, and the customer's acknowledgement of it.
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


def _sha(table: str, col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} IS NULL OR length({col}) = 64", name=f"ck_{table}__{col}_len")


def _active(extra: str = "") -> dict:
    return where(f"is_active = 1 AND is_deleted = 0{extra}", f"is_active = true AND is_deleted = false{extra}")


class _ProjectRow:
    """The two columns every project row carries."""

    project_id: Mapped[str] = mapped_column(GUID(), _fk("project.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)


class Project(AuditedBase):
    __tablename__ = "project"

    project_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # VS-P-YYYY-NNNNNN: the reference
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="ACCEPTED_QUOTATION")
    source_quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # the commercial chain it executes
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="ACTIVE")
    stage_code: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="BOOKED")
    stage_entered_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    lifecycle_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    lifecycle_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    baseline_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)  # the current effective baseline
    handed_over_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    handed_over_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))

    __table_args__ = (
        in_check("project", "source", V.SOURCES),
        in_check("project", "status", V.PROJECT_STATUSES),
        in_check("project", "stage_code", V.STAGES),
        CheckConstraint("length(lifecycle_sha256) = 64", name="ck_project__lifecycle_sha256_len"),
        CheckConstraint("baseline_seq >= 1", name="ck_project__baseline_seq"),
        CheckConstraint(
            "(status = 'HANDED_OVER') = (stage_code = 'HANDED_OVER') AND (status = 'HANDED_OVER') = "
            "(handed_over_on IS NOT NULL AND handed_over_by IS NOT NULL)",
            name="ck_project__handed_over",
        ),
        Index("ux_project__project_number", "project_number", unique=True, **live_where()),
        # PLB-01: exactly one project per accepted baseline (and per commercial chain)
        Index("ux_project__source_quotation", "source_quotation_id", unique=True, **live_where()),
        Index("ux_project__quotation_number", "quotation_number", unique=True, **live_where()),
        Index("ix_project__lead_id", "lead_id"),
        Index("ix_project__property_id", "property_id"),
        Index("ix_project__stage", "status", "stage_code"),
    )


class ProjectBaseline(_ProjectRow, AuditedBase):
    __tablename__ = "project_baseline"

    sequence_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    kind: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    previous_baseline_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_baseline.id"))
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    accepted_baseline_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    accepted_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    cumulative_value_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    decision_method: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    decided_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    selected_optional_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    measurement_set_id: Mapped[str] = mapped_column(GUID(), _fk("measurement_set.id"), nullable=False)
    measurement_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    scope_id: Mapped[str] = mapped_column(GUID(), _fk("scope.id"), nullable=False)
    scope_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    boq_id: Mapped[str] = mapped_column(GUID(), _fk("boq.id"), nullable=False)
    boq_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cost_estimate_id: Mapped[str] = mapped_column(GUID(), _fk("cost_estimate.id"), nullable=False)
    estimate_revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    estimate_snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    customer_promise: Mapped[dict | None] = mapped_column(JSONType())  # the pack version and digest the quote froze
    baseline_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # over this row's reference document

    __table_args__ = (
        in_check("project_baseline", "kind", V.BASELINE_KINDS),
        CheckConstraint("sequence_no >= 1 AND (kind = 'ORIGINAL') = (sequence_no = 1)",
                        name="ck_project_baseline__sequence"),
        CheckConstraint("(kind = 'ORIGINAL') = (variation_no = 0) AND (sequence_no = 1) = "
                        "(previous_baseline_id IS NULL)", name="ck_project_baseline__lineage"),
        *(CheckConstraint(f"length({c}) = 64", name=f"ck_project_baseline__{c}_len")
          for c in ("snapshot_sha256", "accepted_baseline_sha256", "estimate_snapshot_sha256", "baseline_sha256")),
        Index("ux_project_baseline__sequence", "project_id", "sequence_no", unique=True, **live_where()),
        Index("ux_project_baseline__quotation", "quotation_id", unique=True, **live_where()),
        Index("ix_project_baseline__lead_id", "lead_id"),
        Index("ix_project_baseline__previous", "previous_baseline_id"),
        Index("ix_project_baseline__measurement_set_id", "measurement_set_id"),
        Index("ix_project_baseline__scope_id", "scope_id"),
        Index("ix_project_baseline__boq_id", "boq_id"),
        Index("ix_project_baseline__cost_estimate_id", "cost_estimate_id"),
    )  # fmt: skip


class ProjectStage(_ProjectRow, AuditedBase):
    __tablename__ = "project_stage"

    stage_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    sequence_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="NOT_STARTED")
    entered_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    entered_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))

    __table_args__ = (
        in_check("project_stage", "stage_code", V.STAGES),
        in_check("project_stage", "status", V.STAGE_STATUSES),
        CheckConstraint("status = 'NOT_STARTED' OR entered_on IS NOT NULL", name="ck_project_stage__entered"),
        CheckConstraint("(status = 'COMPLETED') = (completed_on IS NOT NULL)", name="ck_project_stage__completed"),
        Index("ux_project_stage__code", "project_id", "stage_code", unique=True, **live_where()),
        Index("ux_project_stage__one_active", "project_id", unique=True,
              **where("status = 'ACTIVE' AND is_deleted = 0", "status = 'ACTIVE' AND is_deleted = false")),
        Index("ix_project_stage__lead_id", "lead_id"),
    )  # fmt: skip


class ProjectMember(_ProjectRow, AuditedBase):
    __tablename__ = "project_member"

    user_id: Mapped[str] = mapped_column(GUID(), _fk("app_user.id"), nullable=False)
    responsibility: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    is_active: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    removed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    removed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    removal_reason: Mapped[str | None] = mapped_column(sa.String(500))

    __table_args__ = (
        in_check("project_member", "responsibility", V.RESPONSIBILITIES),
        CheckConstraint("is_active = (removed_on IS NULL) AND (removed_on IS NULL) = (removed_by IS NULL)",
                        name="ck_project_member__removed"),
        # one active owner per ownership responsibility; a person holds a responsibility once
        Index("ux_project_member__owner", "project_id", "responsibility", unique=True,
              **_active(" AND responsibility <> 'MEMBER'")),
        Index("ux_project_member__user_responsibility", "project_id", "user_id", "responsibility", unique=True,
              **_active()),
        Index("ix_project_member__user", "user_id", "is_active"),
        Index("ix_project_member__lead_id", "lead_id"),
    )  # fmt: skip


class ProjectTransition(_ProjectRow, AuditedBase):
    __tablename__ = "project_transition"

    kind: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="STAGE")
    from_stage: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    to_stage: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    lifecycle_version: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    evaluation: Mapped[dict] = mapped_column(JSONType(), nullable=False)  # gates, blockers, policy digest
    evaluation_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    independent_approval: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False,
                                                       server_default=sa.false())  # fmt: skip
    reason: Mapped[str | None] = mapped_column(sa.String(1000))  # the requester's note (internal)
    decided_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))  # approver, rejecter or withdrawer
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decision_reason: Mapped[str | None] = mapped_column(sa.String(1000))
    # PLB-29: the handover's operational evidence (kind HANDOVER only).
    handover_on: Mapped[date | None] = mapped_column(sa.Date)
    acknowledgement_reference: Mapped[str | None] = mapped_column(sa.String(200))
    evidence_attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    observations: Mapped[str | None] = mapped_column(sa.String(2000))  # non-blocking observations (internal)
    # PEX D5: the handover package this handover (and its approval) is bound to, with the digest that was current.
    handover_package_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_handover_package.id"))
    handover_package_sha256: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("project_transition", "kind", V.TRANSITION_KINDS),
        in_check("project_transition", "from_stage", V.STAGES),
        in_check("project_transition", "to_stage", V.STAGES),
        in_check("project_transition", "outcome", V.TRANSITION_OUTCOMES),
        CheckConstraint("length(evaluation_sha256) = 64", name="ck_project_transition__evaluation_sha256_len"),
        CheckConstraint("outcome IN ('REFUSED', 'AWAITING_APPROVAL') OR (decided_by IS NOT NULL AND decided_on IS "
                        "NOT NULL)", name="ck_project_transition__decided"),
        CheckConstraint("kind = 'HANDOVER' OR (handover_on IS NULL AND acknowledgement_reference IS NULL AND "
                        "evidence_attachment_id IS NULL AND observations IS NULL)",
                        name="ck_project_transition__handover_only"),
        CheckConstraint("kind <> 'HANDOVER' OR handover_on IS NOT NULL", name="ck_project_transition__handover_on"),
        CheckConstraint("kind = 'HANDOVER' OR (handover_package_id IS NULL AND handover_package_sha256 IS NULL)",
                        name="ck_project_transition__package_handover_only"),
        CheckConstraint("(handover_package_id IS NULL) = (handover_package_sha256 IS NULL)",
                        name="ck_project_transition__package_pair"),
        _sha("project_transition", "handover_package_sha256"),
        # one transition awaiting approval at a time: a second request cannot race the first
        Index("ux_project_transition__one_pending", "project_id", unique=True,
              **where("outcome = 'AWAITING_APPROVAL' AND is_deleted = 0",
                      "outcome = 'AWAITING_APPROVAL' AND is_deleted = false")),
        Index("ix_project_transition__project", "project_id", "created_on"),
        Index("ix_project_transition__lead_id", "lead_id"),
        Index("ix_project_transition__evidence", "evidence_attachment_id"),
        Index("ix_project_transition__package", "handover_package_id"),
    )  # fmt: skip


class _Evidence:
    """PLB-39: evidence is an existing, scanned attachment of the project's lead (never a new upload path or URL)."""

    evidence_attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    evidence_reference: Mapped[str | None] = mapped_column(sa.String(200))  # e.g. a document number (internal)


class ProjectChecklistItem(_ProjectRow, _Evidence, AuditedBase):
    __tablename__ = "project_checklist_item"

    stage_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    item_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="OPEN")
    completed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str | None] = mapped_column(sa.String(1000))
    not_applicable_reason: Mapped[str | None] = mapped_column(sa.String(1000))
    reopen_reason: Mapped[str | None] = mapped_column(sa.String(1000))  # why a completed item was reopened (last)

    __table_args__ = (
        in_check("project_checklist_item", "stage_code", V.STAGES),
        in_check("project_checklist_item", "state", V.CHECKLIST_STATES),
        CheckConstraint("(state = 'OPEN') = (completed_on IS NULL) AND (completed_on IS NULL) = (completed_by IS "
                        "NULL)", name="ck_project_checklist_item__completed"),
        CheckConstraint("(state = 'NOT_APPLICABLE') = (not_applicable_reason IS NOT NULL)",
                        name="ck_project_checklist_item__na_reason"),
        Index("ux_project_checklist_item__code", "project_id", "stage_code", "item_code", unique=True,
              **live_where()),
        Index("ix_project_checklist_item__lead_id", "lead_id"),
        Index("ix_project_checklist_item__evidence", "evidence_attachment_id"),
    )  # fmt: skip


class ProjectMilestone(_ProjectRow, _Evidence, AuditedBase):
    __tablename__ = "project_milestone"

    milestone_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    label: Mapped[str] = mapped_column(sa.String(120), nullable=False)  # internal
    customer_label: Mapped[str | None] = mapped_column(sa.String(120))  # potentially customer-safe (never published)
    description: Mapped[str | None] = mapped_column(sa.String(1000))
    stage_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="NOT_STARTED")
    planned_date: Mapped[date | None] = mapped_column(sa.Date)  # an internal plan, never a commitment
    actual_date: Mapped[date | None] = mapped_column(sa.Date)  # set only by explicit completion
    customer_promised_date: Mapped[date | None] = mapped_column(sa.Date)  # only what was already promised
    depends_on_milestone_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_milestone.id"))
    owner_responsibility: Mapped[str | None] = mapped_column(sa.String(12))
    status_reason: Mapped[str | None] = mapped_column(sa.String(500))  # why it is cancelled or not applicable

    __table_args__ = (
        in_check("project_milestone", "milestone_code", V.MILESTONE_TYPES),
        in_check("project_milestone", "stage_code", V.STAGES),
        in_check("project_milestone", "status", V.MILESTONE_STATES),
        in_check("project_milestone", "owner_responsibility", V.RESPONSIBILITIES, nullable=True),
        CheckConstraint("(status = 'COMPLETED') = (actual_date IS NOT NULL)",
                        name="ck_project_milestone__actual_date"),
        CheckConstraint("status NOT IN ('CANCELLED', 'NOT_APPLICABLE') OR status_reason IS NOT NULL",
                        name="ck_project_milestone__status_reason"),
        Index("ix_project_milestone__project", "project_id", "stage_code"),
        Index("ix_project_milestone__lead_id", "lead_id"),
        Index("ix_project_milestone__depends_on", "depends_on_milestone_id"),
        Index("ix_project_milestone__evidence", "evidence_attachment_id"),
    )  # fmt: skip


class ProjectSiteReadiness(_ProjectRow, _Evidence, AuditedBase):
    __tablename__ = "project_site_readiness"

    kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    item_code: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    label: Mapped[str | None] = mapped_column(sa.String(160))  # staff items only (promise items show the frozen text)
    promise_content_version: Mapped[str | None] = mapped_column(sa.String(40))
    status: Mapped[str] = mapped_column(sa.String(28), nullable=False, default="TO_BE_CONFIRMED")
    responsible_party: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="TO_BE_CONFIRMED")
    action: Mapped[str | None] = mapped_column(sa.String(500))  # internal
    customer_action: Mapped[str | None] = mapped_column(sa.String(300))  # the customer's action, customer-safe words
    due_date: Mapped[date | None] = mapped_column(sa.Date)
    note: Mapped[str | None] = mapped_column(sa.String(1000))  # internal
    resolved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))

    __table_args__ = (
        in_check("project_site_readiness", "kind", V.READINESS_KINDS),
        in_check("project_site_readiness", "source", V.READINESS_SOURCES),
        in_check("project_site_readiness", "category", V.READINESS_CATEGORIES),
        in_check("project_site_readiness", "status", V.READINESS_STATUSES),
        in_check("project_site_readiness", "responsible_party", V.RESPONSIBLE_PARTIES),
        CheckConstraint("source = 'CUSTOMER_PROMISE' OR label IS NOT NULL", name="ck_project_site_readiness__label"),
        CheckConstraint("(resolved_on IS NULL) = (resolved_by IS NULL)", name="ck_project_site_readiness__resolved"),
        Index("ux_project_site_readiness__item", "project_id", "kind", "item_code", unique=True, **live_where()),
        Index("ix_project_site_readiness__lead_id", "lead_id"),
        Index("ix_project_site_readiness__evidence", "evidence_attachment_id"),
    )  # fmt: skip


class ProjectBlocker(_ProjectRow, AuditedBase):
    __tablename__ = "project_blocker"

    category: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    source: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="STAFF")
    impact: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(160), nullable=False)  # internal
    description: Mapped[str | None] = mapped_column(sa.String(2000))  # internal
    customer_action: Mapped[str | None] = mapped_column(sa.String(300))  # the customer's action, customer-safe words
    responsible_party: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    target_date: Mapped[date | None] = mapped_column(sa.Date)
    blocks_stage_code: Mapped[str | None] = mapped_column(sa.String(24))  # GATING: this stage and later ones
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="OPEN")
    resolution: Mapped[str | None] = mapped_column(sa.String(1000))
    resolved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    related_milestone_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_milestone.id"))
    related_checklist_item_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_checklist_item.id"))
    related_site_readiness_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_site_readiness.id"))
    related_quotation_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation.id"))  # a variation
    related_work_package_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_work_package.id"))  # PEX
    # PEX: what the customer is told while this pauses their work, in customer-safe words (shown only when set)
    customer_summary: Mapped[str | None] = mapped_column(sa.String(300))

    __table_args__ = (
        in_check("project_blocker", "category", V.BLOCKER_CATEGORIES),
        in_check("project_blocker", "source", V.BLOCKER_SOURCES),
        in_check("project_blocker", "impact", V.BLOCKER_IMPACTS),
        in_check("project_blocker", "responsible_party", V.RESPONSIBLE_PARTIES),
        in_check("project_blocker", "status", V.BLOCKER_STATUSES),
        in_check("project_blocker", "blocks_stage_code", V.STAGES, nullable=True),
        CheckConstraint("impact <> 'GATING' OR blocks_stage_code IS NOT NULL",
                        name="ck_project_blocker__gating_stage"),
        CheckConstraint("status NOT IN ('RESOLVED', 'CANCELLED') OR (resolution IS NOT NULL AND resolved_on IS NOT "
                        "NULL AND resolved_by IS NOT NULL)", name="ck_project_blocker__closed"),
        Index("ix_project_blocker__project", "project_id", "status"),
        Index("ix_project_blocker__lead_id", "lead_id"),
        Index("ix_project_blocker__assigned_to", "assigned_to"),
        Index("ix_project_blocker__milestone", "related_milestone_id"),
        Index("ix_project_blocker__checklist", "related_checklist_item_id"),
        Index("ix_project_blocker__site_readiness", "related_site_readiness_id"),
        Index("ix_project_blocker__quotation", "related_quotation_id"),
        Index("ix_project_blocker__work_package", "related_work_package_id"),
    )  # fmt: skip


class ProjectQcCheck(_ProjectRow, _Evidence, AuditedBase):
    __tablename__ = "project_qc_check"

    category: Mapped[str] = mapped_column(sa.String(28), nullable=False)
    result: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    observation: Mapped[str | None] = mapped_column(sa.String(1000))  # internal
    recheck_of_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_qc_check.id"))
    qc_point_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_qc_point.id"))  # PEX: the planned check
    work_package_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_work_package.id"))  # PEX: the work checked

    __table_args__ = (
        in_check("project_qc_check", "category", V.QC_CATEGORIES),
        in_check("project_qc_check", "result", V.QC_RESULTS),
        CheckConstraint("result <> 'FAIL' OR observation IS NOT NULL", name="ck_project_qc_check__fail_observed"),
        Index("ix_project_qc_check__project", "project_id", "category", "created_on"),
        Index("ix_project_qc_check__lead_id", "lead_id"),
        Index("ix_project_qc_check__space_id", "space_id"),
        Index("ix_project_qc_check__recheck_of", "recheck_of_id"),
        Index("ix_project_qc_check__evidence", "evidence_attachment_id"),
        # PEX: a check is rechecked at most once, so a chain is a line and two simultaneous rechecks cannot both land
        Index("ux_project_qc_check__one_recheck", "recheck_of_id", unique=True,
              **where("recheck_of_id IS NOT NULL AND is_deleted = 0",
                      "recheck_of_id IS NOT NULL AND is_deleted = false")),
        Index("ix_project_qc_check__point", "qc_point_id"),
        Index("ix_project_qc_check__work_package", "work_package_id"),
    )  # fmt: skip


class ProjectSnag(_ProjectRow, _Evidence, AuditedBase):
    __tablename__ = "project_snag"

    snag_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    item_reference: Mapped[str | None] = mapped_column(sa.String(200))  # e.g. the quotation line or unit
    category: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    customer_title: Mapped[str] = mapped_column(sa.String(160), nullable=False)  # potentially customer-safe
    description: Mapped[str | None] = mapped_column(sa.String(2000))  # internal
    is_blocking: Mapped[bool] = mapped_column(Bool(), nullable=False, default=True, server_default=sa.true())
    # why the gating classification last changed (the change itself is a SNAG_RECLASSIFIED event)
    classification_reason: Mapped[str | None] = mapped_column(sa.String(500))
    owner_user_id: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    responsible_party: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="VEDA")
    status: Mapped[str] = mapped_column(sa.String(20), nullable=False, default="OPEN")
    target_date: Mapped[date | None] = mapped_column(sa.Date)
    resolution_note: Mapped[str | None] = mapped_column(sa.String(1000))
    resolved_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    closed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    closed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    qc_check_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_qc_check.id"))
    # PEX: triage, the fix (the fixer is never the verifier; every fix is also a SNAG_FIXED event) and closure.
    work_package_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_work_package.id"))
    source: Mapped[str] = mapped_column(sa.String(16), nullable=False, default="STAFF", server_default="STAFF")
    priority: Mapped[str] = mapped_column(sa.String(8), nullable=False, default="NORMAL", server_default="NORMAL")
    customer_visible: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    fixed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))  # the latest fix
    fixed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    fix_note: Mapped[str | None] = mapped_column(sa.String(1000))  # internal
    resolution_evidence_attachment_id: Mapped[str | None] = mapped_column(GUID(), _fk("attachment.id"))
    closure_code: Mapped[str | None] = mapped_column(sa.String(16))

    __table_args__ = (
        in_check("project_snag", "category", V.SNAG_CATEGORIES),
        in_check("project_snag", "source", V.SNAG_SOURCES),
        in_check("project_snag", "priority", V.SNAG_PRIORITIES),
        in_check("project_snag", "closure_code", V.SNAG_CLOSURE_CODES, nullable=True),
        CheckConstraint("(fixed_on IS NULL) = (fixed_by IS NULL)", name="ck_project_snag__fixed"),
        in_check("project_snag", "status", V.SNAG_STATUSES),
        in_check("project_snag", "responsible_party", V.RESPONSIBLE_PARTIES),
        CheckConstraint("snag_no >= 1", name="ck_project_snag__snag_no"),
        CheckConstraint("status <> 'RESOLVED' OR (resolved_on IS NOT NULL AND resolved_by IS NOT NULL)",
                        name="ck_project_snag__resolved"),
        CheckConstraint("(status = 'CLOSED') = (closed_on IS NOT NULL AND closed_by IS NOT NULL)",
                        name="ck_project_snag__closed"),
        Index("ux_project_snag__number", "project_id", "snag_no", unique=True, **live_where()),
        Index("ix_project_snag__lead_id", "lead_id"),
        Index("ix_project_snag__space_id", "space_id"),
        Index("ix_project_snag__owner", "owner_user_id"),
        Index("ix_project_snag__qc_check", "qc_check_id"),
        Index("ix_project_snag__evidence", "evidence_attachment_id"),
        Index("ix_project_snag__work_package", "work_package_id"),
        Index("ix_project_snag__fixed_by", "fixed_by"),
        Index("ix_project_snag__resolution_evidence", "resolution_evidence_attachment_id"),
    )  # fmt: skip


class ProjectWorkPackage(_ProjectRow, _Evidence, AuditedBase):
    """PEX: a body of work in one stage. Dates are only what was genuinely given: no planned date is unscheduled."""

    __tablename__ = "project_work_package"

    package_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    stage_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    title: Mapped[str] = mapped_column(sa.String(160), nullable=False)  # internal
    description: Mapped[str | None] = mapped_column(sa.String(2000))  # internal
    customer_label: Mapped[str | None] = mapped_column(sa.String(120))  # customer-safe words
    customer_visible: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    owner_user_id: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    depends_on_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_work_package.id"))  # finish-to-start
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="NOT_STARTED")
    planned_start: Mapped[date | None] = mapped_column(sa.Date)  # an internal plan, never a commitment
    planned_finish: Mapped[date | None] = mapped_column(sa.Date)
    plan_revision: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    replan_reason: Mapped[str | None] = mapped_column(sa.String(1000))  # why the plan last changed (internal)
    actual_start: Mapped[date | None] = mapped_column(sa.Date)  # set only by the start command
    actual_finish: Mapped[date | None] = mapped_column(sa.Date)  # set only by the completion command
    started_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    completed_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    completion_note: Mapped[str | None] = mapped_column(sa.String(1000))  # internal
    reopen_reason: Mapped[str | None] = mapped_column(sa.String(1000))  # why completed work was reopened (last)
    cancel_reason: Mapped[str | None] = mapped_column(sa.String(1000))

    __table_args__ = (
        in_check("project_work_package", "stage_code", V.STAGES),
        in_check("project_work_package", "status", V.WORK_PACKAGE_STATES),
        CheckConstraint("package_no >= 1", name="ck_project_work_package__package_no"),
        CheckConstraint("planned_start IS NULL OR planned_finish IS NULL OR planned_finish >= planned_start",
                        name="ck_project_work_package__planned_order"),
        CheckConstraint("status NOT IN ('IN_PROGRESS', 'COMPLETED') OR (actual_start IS NOT NULL AND started_by IS "
                        "NOT NULL)", name="ck_project_work_package__started"),
        CheckConstraint("(status = 'COMPLETED') = (actual_finish IS NOT NULL AND completed_by IS NOT NULL)",
                        name="ck_project_work_package__completed"),
        CheckConstraint("actual_finish IS NULL OR actual_finish >= actual_start",
                        name="ck_project_work_package__actual_order"),
        CheckConstraint("(status = 'CANCELLED') = (cancel_reason IS NOT NULL)",
                        name="ck_project_work_package__cancelled"),
        CheckConstraint("customer_visible = false OR customer_label IS NOT NULL",
                        name="ck_project_work_package__customer_label"),
        CheckConstraint("depends_on_id IS NULL OR depends_on_id <> id", name="ck_project_work_package__not_self"),
        Index("ux_project_work_package__number", "project_id", "package_no", unique=True, **live_where()),
        Index("ix_project_work_package__project", "project_id", "stage_code"),
        Index("ix_project_work_package__lead_id", "lead_id"),
        Index("ix_project_work_package__space_id", "space_id"),
        Index("ix_project_work_package__owner", "owner_user_id"),
        Index("ix_project_work_package__depends_on", "depends_on_id"),
        Index("ix_project_work_package__evidence", "evidence_attachment_id"),
        Index("ix_project_work_package__started_by", "started_by"),
        Index("ix_project_work_package__completed_by", "completed_by"),
    )  # fmt: skip


class ProjectQcPoint(_ProjectRow, AuditedBase):
    """PEX: one planned check. Satisfied only by a PASS chain head (with evidence when required); withdrawn only before
    any result, with a reason. Never NOT_APPLICABLE (review D2)."""

    __tablename__ = "project_qc_point"

    point_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    category: Mapped[str] = mapped_column(sa.String(28), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    work_package_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_work_package.id"))
    label: Mapped[str] = mapped_column(sa.String(160), nullable=False)  # internal
    evidence_required: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="ACTIVE")
    withdrawn_reason: Mapped[str | None] = mapped_column(sa.String(1000))
    withdrawn_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    withdrawn_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("project_qc_point", "category", V.QC_CATEGORIES),
        in_check("project_qc_point", "status", V.QC_POINT_STATES),
        CheckConstraint("point_no >= 1", name="ck_project_qc_point__point_no"),
        CheckConstraint("(status = 'WITHDRAWN') = (withdrawn_reason IS NOT NULL AND withdrawn_by IS NOT NULL AND "
                        "withdrawn_on IS NOT NULL)", name="ck_project_qc_point__withdrawn"),
        Index("ux_project_qc_point__number", "project_id", "point_no", unique=True, **live_where()),
        Index("ix_project_qc_point__lead_id", "lead_id"),
        Index("ix_project_qc_point__space_id", "space_id"),
        Index("ix_project_qc_point__work_package", "work_package_id"),
        Index("ix_project_qc_point__withdrawn_by", "withdrawn_by"),
    )  # fmt: skip


class ProjectCustomerReport(_ProjectRow, AuditedBase):
    """PEX: an issue reported by the customer (in the portal, or recorded by staff on their behalf), in the customer's
    own words. It is never a defect by itself: staff triage it into a snag (ACCEPTED) or decline it with a reason the
    customer reads."""

    __tablename__ = "project_customer_report"

    report_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))  # the reporting customer
    description: Mapped[str] = mapped_column(sa.String(2000), nullable=False)  # the customer's words
    area: Mapped[str | None] = mapped_column(sa.String(120))  # where, in the customer's words
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="SUBMITTED")
    client_key_sha256: Mapped[str | None] = mapped_column(sa.String(64))  # portal idempotency (never the key)
    request_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    triaged_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    triaged_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    snag_id: Mapped[str | None] = mapped_column(GUID(), _fk("project_snag.id"))
    decline_code: Mapped[str | None] = mapped_column(sa.String(16))
    response: Mapped[str | None] = mapped_column(sa.String(500))  # customer-safe reply

    __table_args__ = (
        in_check("project_customer_report", "channel", V.REPORT_CHANNELS),
        in_check("project_customer_report", "status", V.REPORT_STATES),
        in_check("project_customer_report", "decline_code", V.REPORT_DECLINE_CODES, nullable=True),
        CheckConstraint("report_no >= 1", name="ck_project_customer_report__report_no"),
        CheckConstraint("(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_project_customer_report__account"),
        CheckConstraint("(status = 'SUBMITTED') = (triaged_on IS NULL) AND (triaged_on IS NULL) = (triaged_by IS NULL)",
                        name="ck_project_customer_report__triaged"),
        CheckConstraint("(status = 'ACCEPTED') = (snag_id IS NOT NULL)", name="ck_project_customer_report__snag"),
        CheckConstraint("(status = 'DECLINED') = (decline_code IS NOT NULL) AND (status <> 'DECLINED' OR response IS "
                        "NOT NULL)", name="ck_project_customer_report__declined"),
        CheckConstraint("(client_key_sha256 IS NULL) = (request_sha256 IS NULL)",
                        name="ck_project_customer_report__key_pair"),
        _sha("project_customer_report", "client_key_sha256"),
        _sha("project_customer_report", "request_sha256"),
        Index("ux_project_customer_report__number", "project_id", "report_no", unique=True, **live_where()),
        Index("ux_project_customer_report__client_key", "account_id", "client_key_sha256", unique=True,
              **where("client_key_sha256 IS NOT NULL AND is_deleted = 0",
                      "client_key_sha256 IS NOT NULL AND is_deleted = false")),
        Index("ix_project_customer_report__lead_id", "lead_id"),
        Index("ix_project_customer_report__project", "project_id", "status"),
        Index("ix_project_customer_report__snag", "snag_id"),
        Index("ix_project_customer_report__triaged_by", "triaged_by"),
    )  # fmt: skip


class ProjectHandoverPackage(_ProjectRow, AuditedBase):
    """PEX: what is handed over, frozen with its SHA-256 when prepared. The content never changes except by lead erasure,
    which redacts it, records ``redacted_sha256`` and keeps the original digest (review D10)."""

    __tablename__ = "project_handover_package"

    package_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="PREPARED")
    content: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    content_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    redacted: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    redacted_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    superseded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    superseded_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    acknowledged_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))
    completed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("project_handover_package", "status", V.PACKAGE_STATES),
        CheckConstraint("package_no >= 1", name="ck_project_handover_package__package_no"),
        CheckConstraint("length(content_sha256) = 64", name="ck_project_handover_package__content_sha256_len"),
        _sha("project_handover_package", "redacted_sha256"),
        CheckConstraint("redacted = (redacted_sha256 IS NOT NULL)", name="ck_project_handover_package__redacted"),
        CheckConstraint("(status = 'SUPERSEDED') = (superseded_on IS NOT NULL AND superseded_by IS NOT NULL)",
                        name="ck_project_handover_package__superseded"),
        CheckConstraint("(status = 'COMPLETED') = (completed_on IS NOT NULL)",
                        name="ck_project_handover_package__completed"),
        CheckConstraint("(acknowledged_on IS NULL) = (acknowledged_account_id IS NULL)",
                        name="ck_project_handover_package__acknowledged"),
        Index("ux_project_handover_package__number", "project_id", "package_no", unique=True, **live_where()),
        Index("ux_project_handover_package__one_current", "project_id", unique=True,
              **where("status = 'PREPARED' AND is_deleted = 0", "status = 'PREPARED' AND is_deleted = false")),
        Index("ix_project_handover_package__lead_id", "lead_id"),
        Index("ix_project_handover_package__superseded_by", "superseded_by"),
        Index("ix_project_handover_package__account", "acknowledged_account_id"),
    )  # fmt: skip


class ProjectEvent(_ProjectRow, AuditedBase):
    """The immutable timeline (PLB-12): the actor is ``created_by``, the time ``created_on``."""

    __tablename__ = "project_event"

    event_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    stage_code: Mapped[str | None] = mapped_column(sa.String(24))
    from_state: Mapped[str | None] = mapped_column(sa.String(28))
    to_state: Mapped[str | None] = mapped_column(sa.String(28))
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # codes and ids only

    __table_args__ = (
        in_check("project_event", "event_code", V.EVENTS),
        in_check("project_event", "stage_code", V.STAGES, nullable=True),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_project_event__immutable_contract"),
        Index("ix_project_event__project", "project_id", "created_on"),
        Index("ix_project_event__lead_id", "lead_id"),
    )


TABLES = ("project", "project_baseline", "project_stage", "project_member", "project_transition",
          "project_checklist_item", "project_milestone", "project_site_readiness", "project_blocker",
          "project_qc_check", "project_snag", "project_event", "project_work_package", "project_qc_point",
          "project_customer_report", "project_handover_package")  # fmt: skip
