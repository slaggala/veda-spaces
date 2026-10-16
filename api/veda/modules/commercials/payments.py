"""Recorded payments, their receipts and their reversals (PCM-009, PCM-011, PCM-013).

**What a payment is.** Staff's record that the customer's money reached Veda Spaces outside this system: by bank
transfer, UPI, cheque, cash or another way. Veda Spaces processes nothing here and no bank or provider is asked, so a
recorded payment is never presented as a bank confirmation. Record one only once the money has been received.

**Never double-counted.** Every recording carries a client key (the ``Idempotency-Key`` header, required) stored with
the payment as a SHA-256, unique per account, with the SHA-256 of the canonical request. Under the account lock:

- the same key and the same request return the payment already recorded (no new row, no new receipt, no new email);
- the same key with a different request is refused (IDEMPOTENCY_KEY_REUSED);
- a live payment with the same method and reference is refused (DUPLICATE_PAYMENT_REFERENCE): two people recording
  one bank transfer;
- an amount above the outstanding balance is refused (OVERPAYMENT), so the balance can never go below zero by a
  payment.

**Never rewritten.** A payment row is never updated (lead erasure redacts its free text only), and a digest seals its
financial facts. An incorrect record is corrected by a **reversal**: its own row (reason, note, who, when), one per
payment, never by the person who recorded the payment. The payment stays in the history as reversed, its receipt stays
and is shown as cancelled, and the balance follows from the facts.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db, sequences
from veda.kernel.errors import ApiError, field_error
from veda.kernel.jcs import canonical_bytes

from . import baseline, documents, events, position
from .models import CommercialAccount, CommercialPayment, CommercialPaymentReversal, CommercialReceipt

EARLIEST = date(2000, 1, 1)


def key_digest(key: str) -> str:
    return hashlib.sha256(f"pcm-payment:{key}".encode()).hexdigest()


def normalise_reference(value: str | None) -> str | None:
    return "".join(value.split()).upper()[:100] if value else None


def request_digest(body) -> str:
    doc = {"amount_minor": int(body.amount_minor), "received_on": body.received_on.isoformat(),
           "method_code": body.method_code, "external_reference": body.external_reference,
           "customer_note": body.customer_note, "internal_note": body.internal_note}  # fmt: skip
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def record_digest(p: CommercialPayment) -> str:
    """Over the financial facts (not the free text erasure may redact): account, amount, currency, date, method."""
    doc = {"account_id": p.account_id, "amount_minor": int(p.amount_minor), "currency": p.currency,
           "received_on": p.received_on.isoformat(), "method_code": p.method_code,
           "client_key_sha256": p.client_key_sha256}  # fmt: skip
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def problems(s: Session, account: CommercialAccount) -> list[dict[str, Any]]:
    out = []
    for p, _ in position.payments(s, account.id):
        if record_digest(p) != p.record_sha256:
            out.append({"code": "PAYMENT_TAMPERED", "message": "A recorded payment no longer matches its sealed digest.",
                        "payment_id": p.id})  # fmt: skip
    return out


def require_sound(s: Session, account: CommercialAccount) -> None:
    """Fail closed: no new financial record while the baseline or a payment does not verify."""
    found = baseline.problems(s, account) + problems(s, account)
    if found:
        raise ApiError(409, "COMMERCIAL_INTEGRITY_FAILED", "This commercial record does not verify; nothing new can be "
                       "recorded until it is investigated.", extra={"problems": [p["code"] for p in found]})  # fmt: skip


def receipt_of(s: Session, payment_id: str) -> CommercialReceipt | None:
    return s.execute(sa.select(CommercialReceipt).where(CommercialReceipt.payment_id == payment_id,
                                                        CommercialReceipt.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip


def reversal_of(s: Session, payment_id: str) -> CommercialPaymentReversal | None:
    return s.execute(sa.select(CommercialPaymentReversal).where(
        CommercialPaymentReversal.payment_id == payment_id, CommercialPaymentReversal.is_deleted == sa.false()
    )).scalar_one_or_none()  # fmt: skip


def record(s: Session, ctx, account: CommercialAccount, body, key: str) -> tuple[CommercialPayment, bool]:
    """Record a payment and issue its receipt (the caller holds the account lock). Returns (payment, created)."""
    digest, canonical = key_digest(key), request_digest(body)
    found = s.execute(sa.select(CommercialPayment).where(CommercialPayment.account_id == account.id,
                                                         CommercialPayment.client_key_sha256 == digest)
                      ).scalar_one_or_none()  # fmt: skip
    if found is not None:
        if found.request_sha256 == canonical:
            return found, False  # an identical retry: the payment already recorded, nothing new
        raise ApiError(422, "IDEMPOTENCY_KEY_REUSED", "This request key was already used for a different payment.")
    baseline.sync(s, account)
    require_sound(s, account)
    today = db.tx_time(s).date()
    if body.received_on > today or body.received_on < EARLIEST:
        raise ApiError(422, "VALIDATION_FAILED", "The date received cannot be in the future.",
                       errors=[field_error("received_on", "OUT_OF_RANGE", "Not a past date.")])  # fmt: skip
    ref = normalise_reference(body.external_reference)
    if ref is not None:
        for p, r in position.payments(s, account.id):
            if r is None and p.method_code == body.method_code and p.reference_norm == ref:
                raise ApiError(409, "DUPLICATE_PAYMENT_REFERENCE", "A payment with this method and reference is "
                               "already recorded.", extra={"payment_id": p.id})  # fmt: skip
    before = position.compute(s, account)
    if int(body.amount_minor) > before.outstanding_minor:
        raise ApiError(409, "OVERPAYMENT", f"The outstanding balance is {documents.text(before.outstanding_minor)}; a "
                       "larger payment cannot be recorded.", extra={"outstanding_minor": before.outstanding_minor})  # fmt: skip
    p = CommercialPayment(account_id=account.id, lead_id=account.lead_id, amount_minor=int(body.amount_minor),
                          currency=account.currency, received_on=body.received_on, method_code=body.method_code,
                          external_reference=body.external_reference, reference_norm=ref,
                          customer_note=body.customer_note, internal_note=body.internal_note,
                          client_key_sha256=digest, request_sha256=canonical, record_sha256="0" * 64)  # fmt: skip
    p.record_sha256 = record_digest(p)
    s.add(p)
    s.flush()
    after = position.compute(s, account)
    now = db.tx_time(s)
    number = sequences.next_number(s, "RECEIPT")
    receipt = CommercialReceipt(account_id=account.id, lead_id=account.lead_id, payment_id=p.id, receipt_number=number,
                                amount_minor=p.amount_minor, issued_on=now)  # fmt: skip
    documents.seal(receipt, documents.receipt_model(s, account, p, number, before, after, now))
    s.add(receipt)
    s.flush()
    events.record(s, account, "PAYMENT_RECORDED", p.id, amount_minor=p.amount_minor, method_code=p.method_code,
                  received_on=p.received_on, outstanding_minor=after.outstanding_minor)  # fmt: skip
    events.record(s, account, "RECEIPT_ISSUED", receipt.id, payment_id=p.id, receipt_number=number,
                  snapshot_sha256=receipt.snapshot_sha256)  # fmt: skip
    events.notify_receipt(s, receipt)
    return p, True


def reverse(s: Session, ctx, account: CommercialAccount, payment: CommercialPayment, body) -> CommercialPaymentReversal:
    """Reverse ``payment`` (the caller holds the account lock): the correction is its own row."""
    if reversal_of(s, payment.id) is not None:
        raise ApiError(409, "ALREADY_REVERSED", "This payment has already been reversed.")
    if payment.created_by == ctx.user.id:
        raise ApiError(409, "FOUR_EYES_REQUIRED", "A payment is reversed by someone other than the person who "
                       "recorded it.")  # fmt: skip
    r = CommercialPaymentReversal(account_id=account.id, lead_id=account.lead_id, payment_id=payment.id,
                                  reason_code=body.reason_code, note=body.note)  # fmt: skip
    s.add(r)
    s.flush()
    after = position.compute(s, account)
    receipt = receipt_of(s, payment.id)
    events.record(s, account, "PAYMENT_REVERSED", payment.id, reversal_id=r.id, reason_code=r.reason_code,
                  amount_minor=payment.amount_minor, receipt_id=receipt.id if receipt else None,
                  outstanding_minor=after.outstanding_minor)  # fmt: skip
    return r
