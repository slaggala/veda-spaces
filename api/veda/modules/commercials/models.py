"""Project Commercials tables (migration 0210_project_commercials).

Money is integer paise (``*_minor``, BigInteger), never a float; the currency is explicit and INR only. Every row
carries ``account_id`` and the account's ``lead_id`` (scope and erasure follow the lead, as for every MTQ row).

- ``commercial_account``: the commercial record of one accepted quotation chain (a quotation number). Opened by staff
  from an ACCEPTED base quotation; references it, copies nothing of it.
- ``commercial_baseline``: append-only, immutable (database triggers): the accepted base, then each accepted variation,
  with the frozen digests, the accepted total and GST, the cumulative value and a digest over the reference that also
  covers the previous row's digest.
- ``payment_schedule`` / ``payment_instalment``: schedule revisions (one CURRENT per account); instalment amounts add
  up exactly to the value the revision was built for. Status and allocation are derived, never stored.
- ``commercial_payment``: staff's record of money received outside the system. Never updated (erasure redacts its free
  text only); a digest seals its financial facts; the client key and request digests make it idempotent.
- ``commercial_payment_reversal``: the correction of one payment (the payment row itself never changes).
- ``commercial_receipt``: the frozen receipt of one payment (document and HTML, each with its SHA-256).
- ``commercial_invoice``: DRAFT → ISSUED (frozen document) → CANCELLED; one live invoice per instalment.
- ``commercial_event``: the immutable timeline (codes, ids and amounts only; triggers refuse update and delete).
"""

from __future__ import annotations

from datetime import date, datetime

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


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


class _AccountRow:
    """The two columns every row under an account carries."""

    account_id: Mapped[str] = mapped_column(GUID(), _fk("commercial_account.id"), nullable=False)
    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)


class CommercialAccount(AuditedBase):
    __tablename__ = "commercial_account"

    lead_id: Mapped[str] = mapped_column(GUID(), _fk("lead.id"), nullable=False)
    property_id: Mapped[str] = mapped_column(GUID(), _fk("property.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)  # the accepted chain
    base_quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, default="INR", server_default="INR")
    baseline_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1)  # the current baseline row

    __table_args__ = (
        in_check("commercial_account", "currency", V.CURRENCIES),
        CheckConstraint("baseline_seq >= 1", name="ck_commercial_account__baseline_seq"),
        # one commercial record per accepted chain
        Index("ux_commercial_account__quotation_number", "quotation_number", unique=True, **live_where()),
        Index("ux_commercial_account__base_quotation", "base_quotation_id", unique=True, **live_where()),
        Index("ix_commercial_account__lead_id", "lead_id"),
        Index("ix_commercial_account__property_id", "property_id"),
    )


class CommercialBaseline(_AccountRow, AuditedBase):
    """Immutable: one ACCEPTED quotation version of the chain, as the commercial value was built from it."""

    __tablename__ = "commercial_baseline"

    sequence_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    kind: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    previous_baseline_id: Mapped[str | None] = mapped_column(GUID(), _fk("commercial_baseline.id"))
    quotation_id: Mapped[str] = mapped_column(GUID(), _fk("quotation.id"), nullable=False)
    quotation_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    variation_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    version_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    snapshot_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    accepted_baseline_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    accepted_total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)  # may be negative (a variation)
    accepted_tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)  # null: GST not recorded on that version
    value_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)  # cumulative accepted value
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)  # cumulative GST; null once any version's is unknown
    decided_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    baseline_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    __table_args__ = (
        in_check("commercial_baseline", "kind", V.BASELINE_KINDS),
        CheckConstraint(
            "sequence_no >= 1 AND (kind = 'ORIGINAL') = (sequence_no = 1) "
            "AND (sequence_no = 1) = (previous_baseline_id IS NULL) AND (kind = 'ORIGINAL') = (variation_no = 0)",
            name="ck_commercial_baseline__lineage",
        ),
        CheckConstraint("value_minor >= 0", name="ck_commercial_baseline__value"),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_commercial_baseline__immutable_contract"),
        *(
            CheckConstraint(f"length({c}) = 64", name=f"ck_commercial_baseline__{c}_len")
            for c in ("snapshot_sha256", "accepted_baseline_sha256", "baseline_sha256")
        ),  # fmt: skip
        Index("ux_commercial_baseline__sequence", "account_id", "sequence_no", unique=True, **live_where()),
        Index("ux_commercial_baseline__quotation", "quotation_id", unique=True, **live_where()),
        Index("ix_commercial_baseline__lead_id", "lead_id"),
        Index("ix_commercial_baseline__previous", "previous_baseline_id"),
    )


class PaymentSchedule(_AccountRow, AuditedBase):
    __tablename__ = "payment_schedule"

    revision_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="CURRENT")
    source: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    basis_baseline_seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # the value it was built for
    total_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    reason: Mapped[str | None] = mapped_column(sa.String(1000))  # why staff revised it
    superseded_on: Mapped[datetime | None] = mapped_column(UTCDateTime())

    __table_args__ = (
        in_check("payment_schedule", "status", V.SCHEDULE_STATUSES),
        in_check("payment_schedule", "source", V.SCHEDULE_SOURCES),
        CheckConstraint(
            "revision_no >= 1 AND basis_baseline_seq >= 1 AND total_minor >= 0", name="ck_payment_schedule__numbers"
        ),  # fmt: skip
        CheckConstraint(
            "(status = 'SUPERSEDED') = (superseded_on IS NOT NULL)", name="ck_payment_schedule__superseded"
        ),
        CheckConstraint("source = 'QUOTATION_MILESTONES' OR reason IS NOT NULL", name="ck_payment_schedule__reason"),
        Index("ux_payment_schedule__revision", "account_id", "revision_no", unique=True, **live_where()),
        Index(
            "ux_payment_schedule__current",
            "account_id",
            unique=True,
            **where("status = 'CURRENT' AND is_deleted = 0", "status = 'CURRENT' AND is_deleted = false"),
        ),  # fmt: skip
        Index("ix_payment_schedule__lead_id", "lead_id"),
    )


class PaymentInstalment(_AccountRow, AuditedBase):
    __tablename__ = "payment_instalment"

    schedule_id: Mapped[str] = mapped_column(GUID(), _fk("payment_schedule.id"), nullable=False)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    label: Mapped[str] = mapped_column(sa.String(120), nullable=False)  # what this payment is for
    when_text: Mapped[str] = mapped_column(sa.String(200), nullable=False)  # when / on what condition it is due
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)  # the GST it includes (apportioned; null: unknown)
    share_bp: Mapped[int | None] = mapped_column(sa.Integer)  # the frozen milestone share it came from
    # the payment request: staff asked the customer for this instalment (optionally by a date they set)
    requested_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    requested_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    due_on: Mapped[date | None] = mapped_column(sa.Date)
    carried_from_id: Mapped[str | None] = mapped_column(
        GUID(), _fk("payment_instalment.id")
    )  # same instalment, earlier revision

    __table_args__ = (
        CheckConstraint("position >= 1 AND amount_minor > 0", name="ck_payment_instalment__amount"),
        CheckConstraint(
            "tax_minor IS NULL OR (tax_minor >= 0 AND tax_minor <= amount_minor)", name="ck_payment_instalment__tax"
        ),  # fmt: skip
        CheckConstraint("share_bp IS NULL OR share_bp BETWEEN 1 AND 10000", name="ck_payment_instalment__share"),
        CheckConstraint(
            "(requested_on IS NULL) = (requested_by IS NULL) AND (due_on IS NULL OR requested_on IS NOT NULL)",
            name="ck_payment_instalment__request",
        ),  # fmt: skip
        Index("ux_payment_instalment__position", "schedule_id", "position", unique=True, **live_where()),
        Index("ix_payment_instalment__account_id", "account_id"),
        Index("ix_payment_instalment__lead_id", "lead_id"),
        Index("ix_payment_instalment__carried_from", "carried_from_id"),
    )


class CommercialPayment(_AccountRow, AuditedBase):
    """Money staff recorded as received outside the system. Never updated (erasure redacts its free text only)."""

    __tablename__ = "commercial_payment"

    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(sa.String(3), nullable=False, default="INR", server_default="INR")
    received_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    method_code: Mapped[str] = mapped_column(sa.String(16), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(sa.String(100))  # as staff entered it
    reference_norm: Mapped[str | None] = mapped_column(sa.String(100))  # upper case, no spaces: duplicate detection
    customer_note: Mapped[str | None] = mapped_column(sa.String(300))  # customer-safe
    internal_note: Mapped[str | None] = mapped_column(sa.String(1000))  # staff only, never shown to a customer
    client_key_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    request_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    record_sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # over the financial facts

    __table_args__ = (
        in_check("commercial_payment", "currency", V.CURRENCIES),
        in_check("commercial_payment", "method_code", V.PAYMENT_METHODS),
        CheckConstraint("amount_minor > 0", name="ck_commercial_payment__amount"),
        CheckConstraint(
            "(external_reference IS NULL) = (reference_norm IS NULL)", name="ck_commercial_payment__reference"
        ),
        *(
            CheckConstraint(f"length({c}) = 64", name=f"ck_commercial_payment__{c}_len")
            for c in ("client_key_sha256", "request_sha256", "record_sha256")
        ),  # fmt: skip
        Index("ux_commercial_payment__client_key", "account_id", "client_key_sha256", unique=True, **live_where()),
        Index("ix_commercial_payment__account", "account_id", "received_on"),
        Index("ix_commercial_payment__reference", "account_id", "method_code", "reference_norm"),
        Index("ix_commercial_payment__lead_id", "lead_id"),
    )


class CommercialPaymentReversal(_AccountRow, AuditedBase):
    __tablename__ = "commercial_payment_reversal"

    payment_id: Mapped[str] = mapped_column(GUID(), _fk("commercial_payment.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(sa.String(500))  # staff only

    __table_args__ = (
        in_check("commercial_payment_reversal", "reason_code", V.REVERSAL_REASONS),
        Index("ux_commercial_payment_reversal__payment", "payment_id", unique=True, **live_where()),
        Index("ix_commercial_payment_reversal__account_id", "account_id"),
        Index("ix_commercial_payment_reversal__lead_id", "lead_id"),
    )


class _Document:
    """A frozen customer document: the model and its HTML, each sealed by its SHA-256."""

    snapshot: Mapped[dict | None] = mapped_column(JSONType())
    snapshot_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    document_html: Mapped[str | None] = mapped_column(sa.Text)
    document_sha256: Mapped[str | None] = mapped_column(sa.String(64))


class CommercialReceipt(_AccountRow, _Document, AuditedBase):
    __tablename__ = "commercial_receipt"

    payment_id: Mapped[str] = mapped_column(GUID(), _fk("commercial_payment.id"), nullable=False)
    receipt_number: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    issued_on: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)

    __table_args__ = (
        CheckConstraint("amount_minor > 0", name="ck_commercial_receipt__amount"),
        CheckConstraint(
            "snapshot_sha256 IS NOT NULL AND document_sha256 IS NOT NULL", name="ck_commercial_receipt__frozen"
        ),
        _sha("commercial_receipt", "snapshot_sha256"),
        _sha("commercial_receipt", "document_sha256"),
        Index("ux_commercial_receipt__payment", "payment_id", unique=True, **live_where()),
        Index("ux_commercial_receipt__number", "receipt_number", unique=True, **live_where()),
        Index("ix_commercial_receipt__account_id", "account_id"),
        Index("ix_commercial_receipt__lead_id", "lead_id"),
    )


_ISSUED = "status IN ('ISSUED', 'CANCELLED')"


class CommercialInvoice(_AccountRow, _Document, AuditedBase):
    __tablename__ = "commercial_invoice"

    schedule_id: Mapped[str] = mapped_column(GUID(), _fk("payment_schedule.id"), nullable=False)
    instalment_id: Mapped[str] = mapped_column(GUID(), _fk("payment_instalment.id"), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(10), nullable=False, default="DRAFT")
    invoice_number: Mapped[str | None] = mapped_column(sa.String(24))
    amount_minor: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    tax_minor: Mapped[int | None] = mapped_column(sa.BigInteger)
    due_on: Mapped[date | None] = mapped_column(sa.Date)
    customer_note: Mapped[str | None] = mapped_column(sa.String(500))
    issued_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    issued_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    cancelled_on: Mapped[datetime | None] = mapped_column(UTCDateTime())
    cancelled_by: Mapped[str | None] = mapped_column(GUID(), _fk("app_user.id"))
    cancel_reason: Mapped[str | None] = mapped_column(sa.String(500))

    __table_args__ = (
        in_check("commercial_invoice", "status", V.INVOICE_STATUSES),
        CheckConstraint(
            "amount_minor > 0 AND (tax_minor IS NULL OR (tax_minor >= 0 AND tax_minor <= amount_minor))",
            name="ck_commercial_invoice__amount",
        ),  # fmt: skip
        CheckConstraint(
            f"(status = 'DRAFT' AND invoice_number IS NULL AND issued_on IS NULL AND snapshot_sha256 IS NULL) OR "
            f"({_ISSUED} AND invoice_number IS NOT NULL AND issued_on IS NOT NULL AND issued_by IS NOT NULL "
            "AND snapshot_sha256 IS NOT NULL AND document_sha256 IS NOT NULL)",
            name="ck_commercial_invoice__issued_frozen",
        ),
        CheckConstraint(
            "(status = 'CANCELLED') = (cancelled_on IS NOT NULL AND cancelled_by IS NOT NULL AND cancel_reason IS NOT NULL)",
            name="ck_commercial_invoice__cancelled",
        ),
        _sha("commercial_invoice", "snapshot_sha256"),
        _sha("commercial_invoice", "document_sha256"),
        Index("ux_commercial_invoice__number", "invoice_number", unique=True, **live_where()),
        # one live (draft or issued) invoice per instalment
        Index(
            "ux_commercial_invoice__live_instalment",
            "instalment_id",
            unique=True,
            **where(
                f"status IN ({_quoted(V.LIVE_INVOICE_STATUSES)}) AND is_deleted = 0",
                f"status IN ({_quoted(V.LIVE_INVOICE_STATUSES)}) AND is_deleted = false",
            ),
        ),  # fmt: skip
        Index("ix_commercial_invoice__account_id", "account_id"),
        Index("ix_commercial_invoice__schedule_id", "schedule_id"),
        Index("ix_commercial_invoice__lead_id", "lead_id"),
    )


class CommercialEvent(_AccountRow, AuditedBase):
    """Immutable: the actor is ``created_by``; detail holds codes, ids, dates and amounts only (the entity under ``entity``)."""

    __tablename__ = "commercial_event"

    event_code: Mapped[str] = mapped_column(sa.String(24), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    __table_args__ = (
        in_check("commercial_event", "event_code", V.EVENTS),
        CheckConstraint("is_deleted = false AND version = 1", name="ck_commercial_event__immutable_contract"),
        Index("ix_commercial_event__account", "account_id", "created_on"),
        Index("ix_commercial_event__lead_id", "lead_id"),
    )


TABLES = ("commercial_account", "commercial_baseline", "payment_schedule", "payment_instalment", "commercial_payment",
          "commercial_payment_reversal", "commercial_receipt", "commercial_invoice", "commercial_event")  # fmt: skip
IMMUTABLE = ("commercial_baseline", "commercial_event")
