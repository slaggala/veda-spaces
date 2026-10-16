"""Customer invoices (PCM-012).

An invoice requests one instalment of the current schedule: it is a billing event, not a payment, so it never changes
the balance. Lifecycle::

    DRAFT ─issue─► ISSUED ─cancel─► CANCELLED
      └─discard (soft delete; a draft was never a customer document)

A draft is staff-only (previewable, never shown to a customer). Issuing (under the account lock) allocates the number
from the INVOICE sequence under its row lock, freezes the customer document with its digests (``documents``) and marks
the instalment as requested (with the invoice's due date). One live invoice per instalment (a unique index). An issued
invoice never changes; cancelling it records who, when and why, and the frozen document stays, shown as cancelled.

Issuing needs owner decision PCM-D01 (the issuer particulars a customer invoice must carry): until it is recorded,
invoices can be drafted and previewed but not issued (OWNER_DECISION_REQUIRED). Nothing else waits for it.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db, sequences
from veda.kernel.errors import ApiError, field_error

from . import documents, events, payments, policy, position
from .models import CommercialAccount, CommercialInvoice, PaymentInstalment


def _line(s: Session, account: CommercialAccount, instalment_id: str) -> tuple[position.Position, position.Line]:
    pos = position.compute(s, account)
    line = pos.line_of(instalment_id)
    if line is None:
        raise ApiError(409, "INSTALMENT_NOT_CURRENT", "This instalment is not part of the current payment schedule.")
    if line.remaining_minor <= 0:
        raise ApiError(409, "INSTALMENT_PAID", f"{line.instalment.label} is already paid.")
    return pos, line


def draft(s: Session, ctx, account: CommercialAccount, body) -> CommercialInvoice:
    inst = s.get(PaymentInstalment, body.instalment_id)
    if inst is None or inst.is_deleted or inst.account_id != account.id:
        raise ApiError(422, "VALIDATION_FAILED", "Choose an instalment of this payment schedule.",
                       errors=[field_error("instalment_id", "UNKNOWN_INSTALMENT", "Not an instalment here.")])  # fmt: skip
    pos, line = _line(s, account, inst.id)
    if body.due_on is not None and body.due_on < pos.today:
        raise ApiError(422, "VALIDATION_FAILED", "A due date cannot be in the past.",
                       errors=[field_error("due_on", "IN_THE_PAST", "A due date cannot be in the past.")])  # fmt: skip
    live = s.execute(sa.select(CommercialInvoice).where(CommercialInvoice.instalment_id == inst.id,
                                                        CommercialInvoice.status.in_(("DRAFT", "ISSUED")),
                                                        CommercialInvoice.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip
    if live is not None:
        raise ApiError(409, "INVOICE_EXISTS", f"{inst.label} already has a {live.status.lower()} invoice.",
                       extra={"invoice_id": live.id})  # fmt: skip
    inv = CommercialInvoice(account_id=account.id, lead_id=account.lead_id, schedule_id=inst.schedule_id,
                            instalment_id=inst.id, status="DRAFT", amount_minor=int(inst.amount_minor),
                            tax_minor=inst.tax_minor, due_on=body.due_on, customer_note=body.customer_note)  # fmt: skip
    s.add(inv)
    s.flush()
    events.record(s, account, "INVOICE_DRAFTED", inv.id, instalment_id=inst.id, amount_minor=inv.amount_minor)
    return inv


def preview(s: Session, account: CommercialAccount, inv: CommercialInvoice) -> dict:
    """What issuing would freeze now (staff only; marked as a draft)."""
    pos = position.compute(s, account)
    line = pos.line_of(inv.instalment_id)
    if line is None:
        return {"draft": True, "available": False}
    doc = documents.invoice_model(s, account, inv, line, pos, policy.decision("PCM-D01"), None, None)
    return {"draft": True, "available": True, "document": doc, "html": documents.html(doc)}


def issue(s: Session, ctx, account: CommercialAccount, inv: CommercialInvoice) -> CommercialInvoice:
    if inv.status != "DRAFT":
        raise ApiError(409, "INVALID_STATE", f"This invoice is {inv.status.lower()}; only a draft is issued.",
                       extra={"status": inv.status})  # fmt: skip
    particulars = policy.decision("PCM-D01")
    if particulars is None:
        raise ApiError(409, "OWNER_DECISION_REQUIRED", "Invoices cannot be issued until the invoice issuer particulars "
                       "are recorded (owner decision PCM-D01).", extra={"decision": "PCM-D01"})  # fmt: skip
    payments.require_sound(s, account)
    pos, line = _line(s, account, inv.instalment_id)
    if inv.due_on is not None and inv.due_on < pos.today:
        raise ApiError(409, "DUE_DATE_PASSED", "The due date of this draft has passed; set a new one first.")
    now = db.tx_time(s)
    number = sequences.next_number(s, "INVOICE")
    inst = line.instalment
    if inst.requested_on is None:
        inst.requested_on, inst.requested_by = now, ctx.user.id
    if inv.due_on is not None:
        inst.due_on = inv.due_on
    inv.amount_minor, inv.tax_minor = int(inst.amount_minor), inst.tax_minor
    inv.invoice_number, inv.issued_on, inv.issued_by, inv.status = number, now, ctx.user.id, "ISSUED"
    documents.seal(inv, documents.invoice_model(s, account, inv, line, pos, particulars, number, now))
    s.flush()
    events.record(s, account, "INVOICE_ISSUED", inv.id, invoice_number=number, instalment_id=inst.id,
                  amount_minor=inv.amount_minor, due_minor=line.remaining_minor, due_on=inv.due_on,
                  snapshot_sha256=inv.snapshot_sha256)  # fmt: skip
    events.notify_invoice(s, inv)
    return inv


def cancel(s: Session, ctx, account: CommercialAccount, inv: CommercialInvoice, reason: str) -> CommercialInvoice:
    if inv.status != "ISSUED":
        raise ApiError(409, "INVALID_STATE", f"This invoice is {inv.status.lower()}; only an issued invoice is "
                       "cancelled.", extra={"status": inv.status})  # fmt: skip
    inv.status, inv.cancelled_on, inv.cancelled_by, inv.cancel_reason = "CANCELLED", db.tx_time(s), ctx.user.id, reason
    events.record(s, account, "INVOICE_CANCELLED", inv.id, invoice_number=inv.invoice_number)
    return inv


def discard(s: Session, ctx, account: CommercialAccount, inv: CommercialInvoice) -> None:
    if inv.status != "DRAFT":
        raise ApiError(409, "INVALID_STATE", "Only a draft is discarded; an issued invoice is cancelled.")
    inv.is_deleted = True
    events.record(s, account, "INVOICE_DISCARDED", inv.id, reason_code="STAFF_DISCARDED")
