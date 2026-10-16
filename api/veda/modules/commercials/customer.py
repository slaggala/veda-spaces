"""What a customer sees of their project's commercials (PCM-014 … PCM-017), through the Customer Project Portal.

Authorisation is the portal's: the portal reaches a property only through the account's ACTIVE ``portal_access`` rows
and calls ``for_property`` with that property; documents are reached by id through ``invoice_for`` / ``receipt_for``,
which re-check the same access and answer 404 for anything else (a guessed id discloses nothing).

Everything comes from ``position.compute``, the one calculation, and is built from an allow-list: value, paid,
outstanding, the next payment, the schedule (what each instalment is for, when, how much, paid, remaining, state),
recorded payments (amount, date, method, reference, the customer note, the receipt, a correction in customer words),
issued invoices and receipts (number, date, status). Staff notes, reversal notes, cancellation reasons, actor
identities, internal ids other than the documents', digests and anything of the estimate are never read into it. A
record that does not verify is not shown at all ("not available right now"). There is no way to pay here: Veda Spaces
collects nothing online, and the page says so.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock
from veda.kernel.errors import not_found

from . import baseline, documents, payments, position
from . import vocab as V
from .models import CommercialAccount, CommercialInvoice, CommercialReceipt
from .money import text

ACTION_REQUIRED, INFORMATION = "ACTION_REQUIRED", "INFORMATION"
HOW_TO_PAY = ("Pay using the payment details Veda Spaces gave you in writing. Your payment appears here once Veda "
              "Spaces has recorded it.")  # fmt: skip


def enabled() -> bool:
    return bool(settings().project_commercials_enabled)


def account_for_property(s: Session, property_id: str) -> CommercialAccount | None:
    return s.execute(sa.select(CommercialAccount).where(CommercialAccount.property_id == property_id,
                                                        CommercialAccount.is_deleted == sa.false())
                     .order_by(CommercialAccount.created_on.desc()).limit(1)).scalar_one_or_none()  # fmt: skip


def _sound(s: Session, account: CommercialAccount) -> bool:
    return not baseline.problems(s, account) and not payments.problems(s, account)


def _invoices(s: Session, account_id: str) -> list[CommercialInvoice]:
    return list(s.execute(sa.select(CommercialInvoice).where(
        CommercialInvoice.account_id == account_id, CommercialInvoice.is_deleted == sa.false(),
        CommercialInvoice.status.in_(("ISSUED", "CANCELLED"))).order_by(CommercialInvoice.issued_on.desc())).scalars())  # fmt: skip


def _receipts(s: Session, account_id: str) -> dict[str, CommercialReceipt]:
    rows = s.execute(sa.select(CommercialReceipt).where(CommercialReceipt.account_id == account_id,
                                                        CommercialReceipt.is_deleted == sa.false())).scalars()  # fmt: skip
    return {r.payment_id: r for r in rows}


UPDATING = ("UPDATING", "Being updated")


def _line(x: position.Line, in_balance: bool = True) -> dict[str, Any]:
    i = x.instalment
    if not in_balance and x.state != V.PAID:  # the schedule no longer adds up to the value: no balance is shown (M2)
        return {"label": i.label, "when": i.when_text, "amount": text(i.amount_minor), "gst_included": text(i.tax_minor),
                "paid": text(x.applied_minor), "remaining": None, "state": UPDATING[0], "state_label": UPDATING[1],
                "requested": False, "due_on": None}  # fmt: skip
    return {"label": i.label, "when": i.when_text, "amount": text(i.amount_minor), "gst_included": text(i.tax_minor),
            "paid": text(x.applied_minor), "remaining": text(x.remaining_minor), "state": x.state,
            "state_label": V.INSTALMENT_LABELS[x.state], "requested": x.requested,
            "due_on": i.due_on.isoformat() if i.due_on else None}  # fmt: skip


def invoice_state(pos: position.Position, inv: CommercialInvoice) -> tuple[str, str]:
    if inv.status == "CANCELLED":
        return "CANCELLED", "Cancelled"
    if pos.schedule_state != "IN_BALANCE":
        return "ISSUED", "Issued"
    line = pos.line_of(inv.instalment_id)
    if line is None:
        return "ISSUED", "Issued"
    return line.state, V.INSTALMENT_LABELS[line.state]


def for_property(s: Session, prop) -> dict[str, Any] | None:
    """The property's commercial view, or None when there is no commercial record (or the feature is off)."""
    if not enabled():
        return None
    account = account_for_property(s, prop.id)
    if account is None:
        return None
    if not _sound(s, account):
        return {"available": False, "message": "Your payment details are not available right now. Please contact "
                "Veda Spaces."}  # fmt: skip
    pos = position.compute(s, account)
    receipts = _receipts(s, account.id)
    nxt = pos.next_line
    history: list[dict[str, Any]] = []
    for p, r in reversed(pos.payments):
        rc = receipts.get(p.id)
        history.append({
            "amount": text(p.amount_minor), "received_on": p.received_on.isoformat(),
            "method": V.METHOD_LABELS[p.method_code], "reference": p.external_reference, "note": p.customer_note,
            "status": "CORRECTED" if r is not None else "RECORDED",
            "status_label": "Corrected" if r is not None else "Recorded",
            "correction": V.REVERSAL_CUSTOMER_TEXT[r.reason_code] if r is not None else None,
            "receipt": {"id": rc.id, "number": rc.receipt_number,
                        "status": "CANCELLED" if r is not None else "VALID"} if rc else None,
        })  # fmt: skip
    invoices, issued = [], {}
    for inv in _invoices(s, account.id):
        if inv.status == "ISSUED":
            issued[inv.instalment_id] = inv.id
        st, label = invoice_state(pos, inv)
        snap = inv.snapshot or {}
        invoices.append({"id": inv.id, "number": inv.invoice_number, "issued_on": (snap.get("date")),
                         "due_on": inv.due_on.isoformat() if inv.due_on else None,
                         "label": (snap.get("instalment") or {}).get("label"), "amount": text(inv.amount_minor),
                         "status": st, "status_label": label})  # fmt: skip
    receipt_list = [{"id": h["receipt"]["id"], "number": h["receipt"]["number"], "issued_on": h["received_on"],
                     "amount": h["amount"], "status": h["receipt"]["status"],
                     "status_label": "Cancelled" if h["receipt"]["status"] == "CANCELLED" else "Valid"}
                    for h in history if h["receipt"]]  # fmt: skip
    notices = []
    if pos.schedule_state == "REVISION_REQUIRED":
        notices.append({"code": "SCHEDULE_UPDATING", "message": "Your project value changed after an accepted variation. "
                        "Veda Spaces is updating your payment schedule."})  # fmt: skip
    if pos.schedule_state == "NONE":
        notices.append({"code": "SCHEDULE_PENDING", "message": "Your payment schedule will appear here once Veda Spaces "
                        "has set it up."})  # fmt: skip
    if pos.credit_minor:
        notices.append({"code": "CREDIT", "message": f"Your payments are {text(pos.credit_minor)} more than the current "
                        "project value. Your Veda Spaces contact will talk to you about it."})  # fmt: skip
    return {
        "available": True,
        "summary": {
            "currency": account.currency,
            "total_value": text(pos.value_minor),
            "includes_gst": text(pos.tax_minor),
            "paid": text(pos.paid_minor),
            "outstanding": text(pos.outstanding_minor),
            "credit": text(pos.credit_minor) if pos.credit_minor else None,
            "next_payment": (
                {
                    "label": nxt.instalment.label,
                    "amount": text(nxt.remaining_minor),
                    "when": nxt.instalment.when_text,
                    "state": nxt.state,
                    "state_label": V.INSTALMENT_LABELS[nxt.state],
                    "due_on": nxt.instalment.due_on.isoformat() if nxt.instalment.due_on else None,
                }
                if nxt
                else None
            ),
            "as_of": pos.today.isoformat(),
        },  # fmt: skip
        "schedule": [_line(x, pos.schedule_state == "IN_BALANCE") for x in pos.lines],
        "payments": history,
        "invoices": invoices,
        "receipts": receipt_list,
        "notices": notices,
        "how_to_pay": HOW_TO_PAY,
        "attention": attention(pos, issued),
    }


def attention(pos: position.Position, issued: dict[str, str]) -> list[dict[str, Any]]:
    """An instalment Veda Spaces has asked for, with a balance: the portal's Action Required. Never a Pay button.
    ``issued``: instalment id → its issued invoice's id."""
    out = []
    for x in pos.due_lines():
        i = x.instalment
        overdue = x.state == V.OVERDUE
        out.append({
            "kind": "PAYMENT_DUE", "status": ACTION_REQUIRED,
            "title": f"{'Payment overdue' if overdue else 'Payment due'}: {i.label}",
            "text": f"{text(x.remaining_minor)} is {'overdue' if overdue else 'due'}. {HOW_TO_PAY}",
            "due": i.due_on.isoformat() if i.due_on else None, "amount": text(x.remaining_minor),
            "invoice_id": issued.get(i.id),
        })  # fmt: skip
    return out


# --- documents ---------------------------------------------------------------------------------------------------------
def _allowed_leads(s: Session, account_id: str) -> set[str]:
    from veda.modules.portal import projection

    return set(projection.leads(s, account_id))


def _property_live(s: Session, account: CommercialAccount) -> bool:
    from veda.modules.mtq.models import Property

    prop = s.get(Property, account.property_id)
    return prop is not None and not prop.is_deleted


def invoice_for(s: Session, portal_account_id: str, invoice_id: str) -> tuple[CommercialAccount, CommercialInvoice]:
    if not enabled():
        raise not_found()
    inv = s.get(CommercialInvoice, invoice_id)
    if inv is None or inv.is_deleted or inv.status not in ("ISSUED", "CANCELLED"):
        raise not_found()
    if inv.lead_id not in _allowed_leads(s, portal_account_id):
        raise not_found()
    account = s.get(CommercialAccount, inv.account_id)
    if account is None or account.is_deleted or not _property_live(s, account) or not _sound(s, account):
        raise not_found()
    return account, inv


def receipt_for(s: Session, portal_account_id: str, receipt_id: str) -> tuple[CommercialAccount, CommercialReceipt]:
    if not enabled():
        raise not_found()
    r = s.get(CommercialReceipt, receipt_id)
    if r is None or r.is_deleted or r.lead_id not in _allowed_leads(s, portal_account_id):
        raise not_found()
    account = s.get(CommercialAccount, r.account_id)
    if account is None or account.is_deleted or not _property_live(s, account) or not _sound(s, account):
        raise not_found()
    return account, r


def invoice_page(s: Session, account: CommercialAccount, inv: CommercialInvoice, *, with_html: bool = False) -> dict:
    doc = documents.verified(inv, "invoice")
    pos = position.compute(s, account)
    st, label = invoice_state(pos, inv)
    notices = []
    if inv.status == "CANCELLED":
        notices.append({"code": "CANCELLED", "message": f"Veda Spaces cancelled this invoice on "
                        f"{position.local_date(inv.cancelled_on).isoformat() if inv.cancelled_on else ''}. Nothing is due on it."})  # fmt: skip
    out = {"kind": "INVOICE", "id": inv.id, "number": inv.invoice_number, "status": st, "status_label": label,
           "property_id": account.property_id, "document": doc, "notices": notices}  # fmt: skip
    if with_html:
        out["html"] = inv.document_html
        out["filename"] = f"{inv.invoice_number}.html"
    return out


def receipt_page(s: Session, account: CommercialAccount, r: CommercialReceipt, *, with_html: bool = False) -> dict:
    doc = documents.verified(r, "receipt")
    rev = payments.reversal_of(s, r.payment_id)
    notices = []
    if rev is not None:
        notices.append(
            {"code": "CANCELLED", "message": f"This receipt is cancelled. {V.REVERSAL_CUSTOMER_TEXT[rev.reason_code]}"}
        )
    out = {"kind": "RECEIPT", "id": r.id, "number": r.receipt_number,
           "status": "CANCELLED" if rev is not None else "VALID",
           "status_label": "Cancelled" if rev is not None else "Valid", "property_id": account.property_id,
           "document": doc, "notices": notices, "issued_on": clock.to_rfc3339(r.issued_on)}  # fmt: skip
    if with_html:
        out["html"] = r.document_html
        out["filename"] = f"{r.receipt_number}.html"
    return out
