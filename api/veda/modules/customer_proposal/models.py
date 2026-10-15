"""CQX tables (migration 0205_customer_proposal).

Nothing here copies frozen quotation content: every row references one quotation version (``quotation_id``) and, where
it concerns a document part, the digest of that part as frozen. The quotation, its lines and its frozen document stay
the B4 rows; a customer action never writes to them except through the B4 decision service at acceptance.

Personal data: only free text the customer or staff typed (a request body, a staff response, an optional recipient
label) and, if the owner's policy CQX-D04 permits it, network/device evidence of an acceptance. All of it is erased
with the lead (``erasure.erase_for_lead``). No name, email or phone number is ever stored on these rows.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where, where
from veda.kernel.types import GUID, JSONType, UTCDateTime

from . import vocab as V


def _fk(target: str):
    return ForeignKey(target, ondelete="RESTRICT")


def _sha(table: str, col: str) -> CheckConstraint:
    return CheckConstraint(f"{col} IS NULL OR length({col}) = 64", name=f"ck_{table}__{col}_len")


_LIVE = "status IN ('CREATED', 'ACTIVE')"


class ProposalAccessGrant(AuditedBase):
    """One secure link to one issued quotation version for one recipient. Only the token's SHA-256 is stored."""

    __tablename__ = "proposal_access_grant"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    recipient_kind: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    recipient_label: Mapped[str | None] = mapped_column(sa.String(80))  # staff's own note, e.g. "site contact"
    token_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="CREATED")
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    first_viewed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_viewed_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    view_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0, server_default="0")
    revoked_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    revoke_reason_code: Mapped[str | None] = mapped_column(sa.String(16))
    replaces_grant_id: Mapped[str | None] = mapped_column(GUID(), _fk("proposal_access_grant.id"))

    __table_args__ = (
        in_check("proposal_access_grant", "status", V.GRANT_STATUSES),
        in_check("proposal_access_grant", "recipient_kind", V.RECIPIENT_KINDS),
        in_check("proposal_access_grant", "revoke_reason_code", V.REVOKE_REASONS, nullable=True),
        CheckConstraint("length(token_sha256) = 64", name="ck_proposal_access_grant__token_len"),
        CheckConstraint(
            "view_count >= 0 AND version_no >= 1 AND variation_no >= 0", name="ck_proposal_access_grant__counts"
        ),  # fmt: skip
        CheckConstraint(
            "(status = 'REVOKED') = (revoked_on IS NOT NULL AND revoke_reason_code IS NOT NULL)",
            name="ck_proposal_access_grant__revoked",
        ),
        CheckConstraint("status <> 'ACTIVE' OR first_viewed_on IS NOT NULL", name="ck_proposal_access_grant__active"),
        CheckConstraint(
            "replaces_grant_id IS NULL OR replaces_grant_id <> id", name="ck_proposal_access_grant__not_self"
        ),
        Index("ux_proposal_access_grant__token", "token_sha256", unique=True, **live_where()),
        # One live link per recipient kind and quotation version: a second share rotates, never duplicates.
        Index(
            "ux_proposal_access_grant__one_live",
            "quotation_id",
            "recipient_kind",
            unique=True,
            **where(f"{_LIVE} AND is_deleted = 0", f"{_LIVE} AND is_deleted = false"),
        ),
        Index("ix_proposal_access_grant__quotation_id", "quotation_id"),
        Index("ix_proposal_access_grant__lead_id", "lead_id"),
        Index("ix_proposal_access_grant__property_id", "property_id"),
        Index("ix_proposal_access_grant__number", "quotation_number", "variation_no"),
        Index("ix_proposal_access_grant__replaces", "replaces_grant_id"),
        Index("ix_proposal_access_grant__status_expires", "status", "expires_on"),
    )


class ProposalEvent(AuditedBase):
    """What happened to a shared proposal (shared, viewed, selection, request, acknowledgement, decision, revocation).
    Append-only by service rule; ids and codes only, never customer text or a token."""

    __tablename__ = "proposal_event"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    grant_id: Mapped[str | None] = mapped_column(GUID(), _fk("proposal_access_grant.id"))
    event_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    __table_args__ = (
        in_check("proposal_event", "event_code", V.PROPOSAL_EVENTS),
        Index("ix_proposal_event__quotation", "quotation_id", "created_on"),
        Index("ix_proposal_event__grant_id", "grant_id"),
        Index("ix_proposal_event__lead_id", "lead_id"),
    )


class CustomerOptionalSelection(AuditedBase):
    """The customer's current choice for one optional line of one version (history: FULL audit + proposal events).
    A selection is a proposal: it never changes the quotation; at acceptance it becomes part of the accepted baseline."""

    __tablename__ = "customer_optional_selection"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_line_id: Mapped[str] = mapped_column(GUID(), _fk("quotation_line.id"), nullable=False)
    line_ref: Mapped[str] = mapped_column(sa.String(12), nullable=False)  # the customer-facing reference ("L12")
    line_key: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    state: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    changed_by_grant_id: Mapped[str] = mapped_column(GUID(), _fk("proposal_access_grant.id"), nullable=False)
    change_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default="1")

    __table_args__ = (
        in_check("customer_optional_selection", "state", V.SELECTION_STATES),
        CheckConstraint("change_no >= 1", name="ck_customer_optional_selection__change_no"),
        Index(
            "ux_customer_optional_selection__line", "quotation_id", "quotation_line_id", unique=True, **live_where()
        ),  # fmt: skip
        Index("ix_customer_optional_selection__line_id", "quotation_line_id"),
        Index("ix_customer_optional_selection__grant_id", "changed_by_grant_id"),
        Index("ix_customer_optional_selection__lead_id", "lead_id"),
    )


class CustomerProposalRequest(AuditedBase):
    """A customer's question or structured change request on one version. Its text never becomes scope: staff decide,
    and a change only ever reaches the customer as a new quotation version or a variation (resulting_quotation_id)."""

    __tablename__ = "customer_proposal_request"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    grant_id: Mapped[str] = mapped_column(GUID(), _fk("proposal_access_grant.id"), nullable=False)
    request_kind: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    category_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    quotation_line_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation_line.id"))
    line_ref: Mapped[str | None] = mapped_column(sa.String(12))
    space_id: Mapped[str | None] = mapped_column(GUID(), _fk("property_space.id"))
    room_label: Mapped[str | None] = mapped_column(sa.String(120))  # the section title as frozen (not personal)
    requested_quantity: Mapped[str | None] = mapped_column(sa.String(40))  # what the customer asked for, as text
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)  # plain text, sanitised, never rendered as HTML
    status: Mapped[str] = mapped_column(sa.String(24), nullable=False, default="OPEN")
    staff_response: Mapped[str | None] = mapped_column(sa.Text)
    responded_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    responded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resulting_quotation_id: Mapped[str | None] = mapped_column(GUID(), _fk("quotation.id"))
    client_key_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # Idempotency-Key digest

    __table_args__ = (
        in_check("customer_proposal_request", "request_kind", V.REQUEST_KINDS),
        in_check("customer_proposal_request", "category_code", V.REQUEST_CATEGORIES),
        in_check("customer_proposal_request", "status", V.REQUEST_STATUSES),
        CheckConstraint(
            "(request_kind = 'QUESTION') = (category_code IN ('LINE_QUESTION', 'GENERAL_QUESTION'))",
            name="ck_customer_proposal_request__kind",
        ),
        CheckConstraint(
            "category_code NOT IN ('LINE_QUESTION', 'REMOVE_ITEM', 'CHANGE_QUANTITY', 'CHANGE_MATERIAL', "
            "'CHANGE_FINISH') OR quotation_line_id IS NOT NULL",
            name="ck_customer_proposal_request__line",
        ),
        CheckConstraint(
            "status NOT IN ('DECLINED', 'RESOLVED', 'NEEDS_CLARIFICATION', 'ACCEPTED_FOR_REVISION') "
            "OR (responded_by IS NOT NULL AND responded_on IS NOT NULL)",
            name="ck_customer_proposal_request__responded",
        ),
        _sha("customer_proposal_request", "client_key_sha256"),
        Index(
            "ux_customer_proposal_request__client_key", "grant_id", "client_key_sha256", unique=True, **live_where()
        ),  # fmt: skip
        Index("ix_customer_proposal_request__quotation", "quotation_id", "created_on"),
        Index("ix_customer_proposal_request__lead_id", "lead_id"),
        Index("ix_customer_proposal_request__property_id", "property_id"),
        Index("ix_customer_proposal_request__grant_id", "grant_id"),
        Index("ix_customer_proposal_request__line_id", "quotation_line_id"),
        Index("ix_customer_proposal_request__space_id", "space_id"),
        Index("ix_customer_proposal_request__resulting", "resulting_quotation_id"),
        Index("ix_customer_proposal_request__status", "status"),
    )


class QuotationAcknowledgement(AuditedBase):
    """The recipient acknowledged one customer-safe section of one frozen version (bound to that section's digest)."""

    __tablename__ = "quotation_acknowledgement"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    grant_id: Mapped[str] = mapped_column(GUID(), _fk("proposal_access_grant.id"), nullable=False)
    section_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    section_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    __table_args__ = (
        in_check("quotation_acknowledgement", "section_code", V.ACK_SECTIONS),
        _sha("quotation_acknowledgement", "section_sha256"),
        _sha("quotation_acknowledgement", "snapshot_sha256"),
        _sha("quotation_acknowledgement", "evidence_sha256"),
        Index(
            "ux_quotation_acknowledgement__section",
            "quotation_id",
            "grant_id",
            "section_code",
            unique=True,
            **live_where(),
        ),  # fmt: skip
        Index("ix_quotation_acknowledgement__grant_id", "grant_id"),
        Index("ix_quotation_acknowledgement__lead_id", "lead_id"),
    )


class QuotationAcceptanceEvidence(AuditedBase):
    """The evidence of a customer's digital decision on one frozen version: what they saw (digests, displayed total,
    chosen optional items, acknowledged sections), when, through which link, and the evidence digest over all of it."""

    __tablename__ = "quotation_acceptance_evidence"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    grant_id: Mapped[str] = mapped_column(GUID(), _fk("proposal_access_grant.id"), nullable=False)
    decision: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    method: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # CUSTOMER_DIGITAL
    verification_method: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # the owner's CQX-D01 method
    snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    issued_html_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    displayed_total_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    selected_line_refs: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    acknowledgements: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    decided_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    request_trace: Mapped[str | None] = mapped_column(sa.String(64))  # the request id of the decision (log trace)
    client_key_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    request_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # canonical request (idempotency)
    network: Mapped[dict | None] = mapped_column(JSONType())  # only what CQX-D04 permits; erased with the lead
    evidence: Mapped[dict] = mapped_column(JSONType(), nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    __table_args__ = (
        in_check("quotation_acceptance_evidence", "decision", V.ACCEPTANCE_DECISIONS),
        CheckConstraint("method = 'CUSTOMER_DIGITAL'", name="ck_quotation_acceptance_evidence__method"),
        _sha("quotation_acceptance_evidence", "snapshot_sha256"),
        _sha("quotation_acceptance_evidence", "issued_html_sha256"),
        _sha("quotation_acceptance_evidence", "client_key_sha256"),
        _sha("quotation_acceptance_evidence", "request_sha256"),
        _sha("quotation_acceptance_evidence", "evidence_sha256"),
        # One customer decision per version: a repeat is idempotent, never a second record.
        Index("ux_quotation_acceptance_evidence__quotation", "quotation_id", unique=True, **live_where()),
        Index("ix_quotation_acceptance_evidence__grant_id", "grant_id"),
        Index("ix_quotation_acceptance_evidence__lead_id", "lead_id"),
    )


CQX_TABLES = (
    "proposal_access_grant",
    "proposal_event",
    "customer_optional_selection",
    "customer_proposal_request",
    "quotation_acknowledgement",
    "quotation_acceptance_evidence",
)
