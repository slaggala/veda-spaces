"""Project Commercials lead-erasure cascade (07 §8.2) and its retention boundary: the repository's policy for
commercial records (as for quotations, ``mtq_commercial.erasure``) applied to payments, invoices and receipts.

Erased: every free-text field that may describe the customer: payment references (a UPI reference can carry a personal
address), customer notes and staff notes, reversal notes, invoice notes and cancellation reasons, schedule revision
reasons; in a frozen invoice or receipt the customer's name, the payment reference and the notes are redacted and the
document re-sealed (``documents.redact``, DOCUMENT_REDACTED with the previous digests).

Retained (the financial record, describing money and work, not a person): amounts, currency, dates, methods, reversal
reason codes, statuses, document numbers, instalment labels, actor ids, digests and the baseline lineage. Nothing is
deleted: an issued invoice, a receipt or a payment is never removed because a lead is erased. Every touched row joins
the transaction's erasure set so the erasure-audit job rewrites its audit payloads. After erasure the commercial record
is closed to writes (``access.writable``).
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import documents
from .models import (
    CommercialAccount,
    CommercialInvoice,
    CommercialPayment,
    CommercialPaymentReversal,
    CommercialReceipt,
    PaymentInstalment,
    PaymentSchedule,
)

ERASED = "[erased]"
TEXT_FIELDS: list[tuple] = [
    (CommercialPayment, ("external_reference", "reference_norm", "customer_note", "internal_note")),
    (CommercialPaymentReversal, ("note",)),
    (CommercialInvoice, ("customer_note", "cancel_reason")),
    (CommercialReceipt, ()),
    (PaymentSchedule, ("reason",)),
    (PaymentInstalment, ()),
    (CommercialAccount, ()),
]


def _rows(s: Session, model, lead_id: str):
    return (
        s.execute(sa.select(model).where(model.lead_id == lead_id).execution_options(include_deleted=True))
        .scalars()
        .all()
    )


def erase_for_lead(s: Session, lead) -> int:
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    accounts = {a.id: a for a in _rows(s, CommercialAccount, lead.id)}
    for model, fields in TEXT_FIELDS:
        for row in _rows(s, model, lead.id):
            erasure.add(row.id)
            for f in fields:
                if getattr(row, f):
                    setattr(row, f, ERASED)
            if isinstance(row, CommercialPayment):  # its request digest covered the erased text: replace it
                row.request_sha256 = hashlib.sha256(f"erased:{row.id}".encode()).hexdigest()
            if isinstance(row, CommercialInvoice | CommercialReceipt) and row.snapshot is not None:
                documents.redact(s, accounts[row.account_id], row)
            touched += 1
    s.flush()
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    return [row.id for model, _ in TEXT_FIELDS for row in _rows(s, model, lead_id)]
