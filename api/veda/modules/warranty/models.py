"""Warranty and after-sales service tables (WSV, migration 0214_warranty_service).

- ``warranty_entitlement``: one per handed-over project, registered from its completed HANDOVER transition, frozen
  (``terms`` + ``terms_sha256``): the verbatim warranty and service-support statements of every accepted quotation of
  the handed-over lineage, the handover facts and the structured coverage classes of owner decision WSV-D01 that apply.
  Never re-derived; its start is the handover date, never the time it was registered.
- ``service_request``: a post-handover request; its initial meaning is only "the customer reported an issue".
- ``service_request_photo``: a customer or staff photo of a request (an attachment of entity type ``service_request``)
  and who added it.
- ``service_assessment``: each coverage decision, with its basis, as-of date, customer explanation and internal reason.
- ``service_visit``: an inspection or service visit (planned date entered by staff, outcome).
- ``service_resolution``: each resolution (one per cycle) and what became of it (confirmed, verified, rejected).
- ``service_evidence``: staff evidence cited on a request; customer-visible only when marked so (never INTERNAL).
- ``service_note``: free text exchanged or recorded (information requests and answers, internal notes, reasons), with
  its visibility.
- ``service_event``: the immutable timeline (codes, ids, states, dates and digests only; the database refuses UPDATE
  and DELETE), so erasure never touches it: free text lives only in the rows above, which erasure redacts.
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


class WarrantyEntitlement(AuditedBase):
    __tablename__ = "warranty_entitlement"

    project_id: Mapped[str] = mapped_column(GUID(), _fk("project.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    handover_transition_id: Mapped[str] = mapped_column(GUID(), _fk("project_transition.id"), nullable=False)
    handover_on: Mapped[date] = mapped_column(sa.Date, nullable=False)  # the start of every HANDOVER-trigger class
    terms: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    terms_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    policy_version: Mapped[str] = mapped_column(sa.String(40), nullable=False)
    policy_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    registered_via: Mapped[str] = mapped_column(sa.String(16), nullable=False)

    __table_args__ = (
        in_check("warranty_entitlement", "registered_via", ("HANDOVER_EVENT", "STAFF")),
        CheckConstraint("length(terms_sha256) = 64", name="ck_warranty_entitlement__terms_sha256_len"),
        CheckConstraint("length(policy_sha256) = 64", name="ck_warranty_entitlement__policy_sha256_len"),
        Index("ux_warranty_entitlement__project", "project_id", unique=True, **live_where()),
        Index("ix_warranty_entitlement__lead_id", "lead_id"),
        Index("ix_warranty_entitlement__property", "property_id"),
        Index("ix_warranty_entitlement__transition", "handover_transition_id"),
    )  # fmt: skip


class ServiceRequest(AuditedBase):
    __tablename__ = "service_request"

    request_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # VS-SR-YYYY-NNNNNN
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(GUID(), _fk("project.id"), nullable=False)
    entitlement_id: Mapped[str | None] = mapped_column(GUID(), _fk("warranty_entitlement.id"))
    related_request_id: Mapped[str | None] = mapped_column(GUID(), _fk("service_request.id"))
    duplicate_of_id: Mapped[str | None] = mapped_column(GUID(), _fk("service_request.id"))
    channel: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))  # the reporting customer
    category: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    area: Mapped[str | None] = mapped_column(sa.String(120))  # where, in the customer's words
    description: Mapped[str] = mapped_column(sa.String(2000), nullable=False)  # the customer's words
    noticed_on: Mapped[date | None] = mapped_column(sa.Date)  # when the customer noticed it (their statement)
    reported_on: Mapped[date] = mapped_column(sa.Date, nullable=False)  # India date of submission: coverage as of it
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default=V.REPORTED)
    return_state: Mapped[str | None] = mapped_column(sa.String(32))  # where an answered information request returns
    priority: Mapped[str] = mapped_column(sa.String(8), nullable=False, default="NORMAL", server_default="NORMAL")
    owner_user_id: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa.text("1"))
    rejections: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default=sa.text("0"))
    service_class: Mapped[str | None] = mapped_column(sa.String(16))
    closure_code: Mapped[str | None] = mapped_column(sa.String(32))
    closed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    verified_by_kind: Mapped[str | None] = mapped_column(sa.String(8))
    client_key_sha256: Mapped[str | None] = mapped_column(sa.String(64))  # portal idempotency (never the key)
    request_sha256: Mapped[str | None] = mapped_column(sa.String(64))

    __table_args__ = (
        in_check("service_request", "channel", V.CHANNELS),
        in_check("service_request", "category", tuple(V.CATEGORIES)),
        in_check("service_request", "status", V.REQUEST_STATES),
        in_check("service_request", "return_state", V.INFORMATION_FROM, nullable=True),
        in_check("service_request", "priority", V.PRIORITIES),
        in_check("service_request", "service_class", V.SERVICE_CLASSES, nullable=True),
        in_check("service_request", "closure_code", V.CLOSURE_CODES, nullable=True),
        in_check("service_request", "verified_by_kind", V.VERIFIED_BY, nullable=True),
        CheckConstraint("(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_service_request__account"),
        CheckConstraint("(status = 'CLOSED') = (closure_code IS NOT NULL AND closed_on IS NOT NULL)",
                        name="ck_service_request__closed"),
        CheckConstraint("(status = 'INFORMATION_REQUESTED') = (return_state IS NOT NULL)",
                        name="ck_service_request__information_return"),
        CheckConstraint("(closure_code = 'SERVICED') = (verified_by_kind IS NOT NULL)",
                        name="ck_service_request__verified"),
        CheckConstraint("closure_code IS NULL OR closure_code <> 'DUPLICATE' OR duplicate_of_id IS NOT NULL",
                        name="ck_service_request__duplicate"),
        CheckConstraint("cycle >= 1 AND rejections >= 0", name="ck_service_request__counters"),
        CheckConstraint("(client_key_sha256 IS NULL) = (request_sha256 IS NULL)", name="ck_service_request__key_pair"),
        _sha("service_request", "client_key_sha256"),
        _sha("service_request", "request_sha256"),
        Index("ux_service_request__number", "request_number", unique=True, **live_where()),
        Index("ux_service_request__client_key", "account_id", "client_key_sha256", unique=True,
              **where("client_key_sha256 IS NOT NULL AND is_deleted = 0",
                      "client_key_sha256 IS NOT NULL AND is_deleted = false")),
        Index("ix_service_request__lead_id", "lead_id"),
        Index("ix_service_request__property", "property_id", "status"),
        Index("ix_service_request__project", "project_id", "status"),
        Index("ix_service_request__status", "status", "created_on"),
        Index("ix_service_request__owner", "owner_user_id"),
        Index("ix_service_request__entitlement", "entitlement_id"),
        Index("ix_service_request__related", "related_request_id"),
        Index("ix_service_request__duplicate_of", "duplicate_of_id"),
        Index("ix_service_request__account", "account_id"),
        Index("ix_service_request__space", "space_id"),
    )  # fmt: skip


class _RequestRow:
    request_id: Mapped[str] = mapped_column(GUID(), _fk("service_request.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)


class ServiceRequestPhoto(_RequestRow, AuditedBase):
    __tablename__ = "service_request_photo"

    attachment_id: Mapped[str] = mapped_column(GUID(), _fk("attachment.id"), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))

    __table_args__ = (
        in_check("service_request_photo", "channel", V.CHANNELS),
        CheckConstraint("(channel = 'PORTAL') = (account_id IS NOT NULL)", name="ck_service_request_photo__account"),
        Index("ux_service_request_photo__attachment", "attachment_id", unique=True, **live_where()),
        Index("ix_service_request_photo__request", "request_id"),
        Index("ix_service_request_photo__lead_id", "lead_id"),
        Index("ix_service_request_photo__account", "account_id"),
    )  # fmt: skip


class ServiceAssessment(_RequestRow, AuditedBase):
    __tablename__ = "service_assessment"

    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    service_class: Mapped[str | None] = mapped_column(sa.String(16))
    basis_kind: Mapped[str | None] = mapped_column(sa.String(32))
    basis_path: Mapped[str | None] = mapped_column(sa.String(120))  # e.g. sources/0/warranty/2, coverage/WORKMANSHIP
    basis_text_sha256: Mapped[str | None] = mapped_column(sa.String(64))  # the cited text's digest when assessed
    as_of: Mapped[date] = mapped_column(sa.Date, nullable=False)  # the request's reported date
    coverage_status: Mapped[str | None] = mapped_column(sa.String(16))  # the class status as of that date
    explanation: Mapped[str] = mapped_column(sa.String(1000), nullable=False)  # customer-safe
    internal_reason: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    period_basis: Mapped[str | None] = mapped_column(sa.String(1000))  # internal: why within (or outside) the period
    assessed_by: Mapped[str] = mapped_column(GUID(), _fk("app_user.id"), nullable=False)
    assessed_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        in_check("service_assessment", "outcome", V.OUTCOMES),
        in_check("service_assessment", "service_class", V.SERVICE_CLASSES, nullable=True),
        in_check("service_assessment", "basis_kind", V.BASES, nullable=True),
        in_check("service_assessment", "coverage_status", (V.ACTIVE, V.EXPIRED, V.NOT_STARTED, V.NOT_RECORDED),
                 nullable=True),
        CheckConstraint("outcome <> 'COVERED' OR (service_class = 'WARRANTY' AND basis_kind IN ('COVERAGE_CLASS', "
                        "'WARRANTY_STATEMENT', 'SERVICE_SUPPORT_STATEMENT'))", name="ck_service_assessment__covered"),
        CheckConstraint("(basis_kind IS NULL) = (basis_path IS NULL)", name="ck_service_assessment__basis"),
        CheckConstraint("cycle >= 1", name="ck_service_assessment__cycle"),
        _sha("service_assessment", "basis_text_sha256"),
        Index("ix_service_assessment__request", "request_id", "created_on"),
        Index("ix_service_assessment__lead_id", "lead_id"),
        Index("ix_service_assessment__assessed_by", "assessed_by"),
    )  # fmt: skip


class ServiceVisit(_RequestRow, AuditedBase):
    __tablename__ = "service_visit"

    visit_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # the request cycle it belongs to
    kind: Mapped[str] = mapped_column(sa.String(12), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(12), nullable=False, default="PLANNED")
    planned_on: Mapped[date] = mapped_column(sa.Date, nullable=False)  # entered by staff (agreed with the customer)
    done_on: Mapped[date | None] = mapped_column(sa.Date)
    customer_note: Mapped[str | None] = mapped_column(sa.String(1000))
    internal_note: Mapped[str | None] = mapped_column(sa.String(2000))
    cancel_reason: Mapped[str | None] = mapped_column(sa.String(300))
    done_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))

    __table_args__ = (
        in_check("service_visit", "kind", V.VISIT_KINDS),
        in_check("service_visit", "status", V.VISIT_STATES),
        CheckConstraint("(status = 'DONE') = (done_on IS NOT NULL AND done_by IS NOT NULL)",
                        name="ck_service_visit__done"),
        CheckConstraint("(status = 'CANCELLED') = (cancel_reason IS NOT NULL)", name="ck_service_visit__cancelled"),
        CheckConstraint("visit_no >= 1 AND cycle >= 1", name="ck_service_visit__visit_no"),
        Index("ux_service_visit__number", "request_id", "visit_no", unique=True, **live_where()),
        Index("ix_service_visit__lead_id", "lead_id"),
        Index("ix_service_visit__done_by", "done_by"),
    )  # fmt: skip


class ServiceResolution(_RequestRow, AuditedBase):
    __tablename__ = "service_resolution"

    cycle: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    summary: Mapped[str] = mapped_column(sa.String(1000), nullable=False)  # customer-safe
    internal_note: Mapped[str | None] = mapped_column(sa.String(2000))
    resolved_by: Mapped[str] = mapped_column(GUID(), _fk("app_user.id"), nullable=False)
    resolved_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    outcome: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="PENDING")
    decided_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decided_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))  # staff verification
    decided_account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))  # customer decision

    __table_args__ = (
        in_check("service_resolution", "outcome", ("PENDING", "CONFIRMED", "VERIFIED", "REJECTED", "SUPERSEDED")),
        CheckConstraint("(outcome = 'PENDING') = (decided_on IS NULL)", name="ck_service_resolution__decided"),
        CheckConstraint("outcome <> 'VERIFIED' OR decided_by IS NOT NULL", name="ck_service_resolution__verified"),
        CheckConstraint("outcome NOT IN ('CONFIRMED', 'REJECTED') OR decided_account_id IS NOT NULL",
                        name="ck_service_resolution__customer"),
        CheckConstraint("cycle >= 1", name="ck_service_resolution__cycle"),
        Index("ux_service_resolution__pending", "request_id", unique=True,
              **where("outcome = 'PENDING' AND is_deleted = 0", "outcome = 'PENDING' AND is_deleted = false")),
        Index("ix_service_resolution__request", "request_id", "created_on"),
        Index("ix_service_resolution__lead_id", "lead_id"),
        Index("ix_service_resolution__resolved_by", "resolved_by"),
        Index("ix_service_resolution__decided_by", "decided_by"),
        Index("ix_service_resolution__account", "decided_account_id"),
    )  # fmt: skip


class ServiceEvidence(_RequestRow, AuditedBase):
    __tablename__ = "service_evidence"

    attachment_id: Mapped[str] = mapped_column(GUID(), _fk("attachment.id"), nullable=False)
    visit_id: Mapped[str | None] = mapped_column(GUID(), _fk("service_visit.id"))
    resolution_id: Mapped[str | None] = mapped_column(GUID(), _fk("service_resolution.id"))
    customer_visible: Mapped[bool] = mapped_column(Bool(), nullable=False, default=False, server_default=sa.false())
    caption: Mapped[str | None] = mapped_column(sa.String(160))  # customer-safe when visible

    __table_args__ = (
        Index("ux_service_evidence__attachment", "request_id", "attachment_id", unique=True, **live_where()),
        Index("ix_service_evidence__lead_id", "lead_id"),
        Index("ix_service_evidence__attachment", "attachment_id"),
        Index("ix_service_evidence__visit", "visit_id"),
        Index("ix_service_evidence__resolution", "resolution_id"),
    )  # fmt: skip


class ServiceNote(_RequestRow, AuditedBase):
    __tablename__ = "service_note"

    kind: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    visibility: Mapped[str] = mapped_column(sa.String(8), nullable=False)
    text: Mapped[str] = mapped_column(sa.String(2000), nullable=False)
    account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))  # written by the customer

    __table_args__ = (
        in_check("service_note", "kind", V.NOTE_KINDS),
        in_check("service_note", "visibility", V.NOTE_VISIBILITIES),
        CheckConstraint("kind <> 'INTERNAL' OR visibility = 'INTERNAL'", name="ck_service_note__internal"),
        CheckConstraint("account_id IS NULL OR visibility = 'CUSTOMER'", name="ck_service_note__customer"),
        Index("ix_service_note__request", "request_id", "created_on"),
        Index("ix_service_note__lead_id", "lead_id"),
        Index("ix_service_note__account", "account_id"),
    )  # fmt: skip


class ServiceEvent(_RequestRow, AuditedBase):
    """The immutable timeline: the actor is ``created_by`` (the public principal for a customer, with ``account_id``)."""

    __tablename__ = "service_event"

    event_code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    from_state: Mapped[str | None] = mapped_column(sa.String(32))
    to_state: Mapped[str | None] = mapped_column(sa.String(32))
    account_id: Mapped[str | None] = mapped_column(GUID(), _fk("portal_account.id"))
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)  # codes, ids, digests only

    __table_args__ = (
        in_check("service_event", "event_code", V.EVENTS),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_service_event__immutable_contract"),
        Index("ix_service_event__request", "request_id", "created_on"),
        Index("ix_service_event__lead_id", "lead_id"),
        Index("ix_service_event__account", "account_id"),
    )  # fmt: skip


TABLES = ("warranty_entitlement", "service_request", "service_request_photo", "service_assessment", "service_visit",
          "service_resolution", "service_evidence", "service_note", "service_event")  # fmt: skip
