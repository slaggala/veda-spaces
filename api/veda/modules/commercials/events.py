"""The commercial timeline and the customer notifications (PCM-030, PCM-031).

``record`` appends a ``commercial_event`` row: the actor (``created_by``), the time, a code, the entity and a detail of
codes, ids, dates and amounts only. Free text never enters the timeline (``_check`` refuses it), so an event never needs
erasing and can be immutable (migration 0210 triggers refuse UPDATE and DELETE).

Customers are told, by email through the outbox, only that a document is waiting in their portal: an invoice was
issued, or a payment was recorded and its receipt issued. The email carries no amount, no bank detail and no way to
pay; it links to the portal, where the customer signs in. The outbox row is written in the same transaction as the
financial record, and a retried or duplicated request returns the record already made without writing another row, so
one financial event gives one email at most. The handler sends nothing unless both the commercials and the portal
features are on, the document is still valid, and the enquiry has a primary customer with ACTIVE portal access.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import outbox
from veda.platform.notifications.handlers import app_link, handler, send
from veda.platform.notifications.models import OutboxEvent

from .models import CommercialAccount, CommercialEvent, CommercialInvoice, CommercialPaymentReversal, CommercialReceipt

_SAFE = re.compile(r"^[A-Za-z0-9_.:>+-]{0,80}$")
INVOICE_ISSUED = "commercials.invoice_issued"
RECEIPT_ISSUED = "commercials.receipt_issued"
EVENT_TYPES = (INVOICE_ISSUED, RECEIPT_ISSUED)


def _check(value: Any, key: str) -> None:
    if value is None or isinstance(value, bool | int):
        return
    if isinstance(value, date):
        return
    if isinstance(value, str):
        if not _SAFE.match(value):
            raise ValueError(f"commercial_event detail {key!r} must be a code, id, amount or date, never free text")
        return
    if isinstance(value, list | tuple):
        for v in value:
            _check(v, key)
        return
    raise ValueError(f"commercial_event detail {key!r} has an unsupported type {type(value).__name__}")


def record(s: Session, account: CommercialAccount, code: str, entity_id: str | None = None,
           **detail: Any) -> CommercialEvent:  # fmt: skip
    clean = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in {"entity": entity_id, **detail}.items()
             if v is not None}  # fmt: skip
    for k, v in clean.items():
        _check(v, k)
    e = CommercialEvent(account_id=account.id, lead_id=account.lead_id, event_code=code, detail=clean)
    s.add(e)
    return e


def notify_invoice(s: Session, invoice: CommercialInvoice) -> None:
    outbox.enqueue(s, INVOICE_ISSUED, "commercial_invoice", invoice.id, invoice_id=invoice.id)


def notify_receipt(s: Session, receipt: CommercialReceipt) -> None:
    outbox.enqueue(s, RECEIPT_ISSUED, "commercial_receipt", receipt.id, receipt_id=receipt.id)


def _recipients(s: Session, lead_id: str) -> list[tuple[str, str]]:
    """(email, name) of the enquiry's primary customers with ACTIVE portal access (the person billed)."""
    from veda.modules.crm.leads.models import Lead
    from veda.modules.portal.models import PortalAccess, PortalAccount

    lead = s.get(Lead, lead_id)
    if lead is None or lead.is_deleted or lead.anonymized_on is not None:
        return []
    rows = s.execute(
        sa.select(PortalAccount.email_normalized, PortalAccount.display_name)
        .join(PortalAccess, PortalAccess.account_id == PortalAccount.id)
        .where(
            PortalAccess.lead_id == lead_id,
            PortalAccess.status == "ACTIVE",
            PortalAccess.is_deleted == sa.false(),
            PortalAccess.relationship == "PRIMARY_CUSTOMER",
            PortalAccount.status == "ACTIVE",
            PortalAccount.erased_on.is_(None),
        )  # fmt: skip
    ).all()
    return [(e, n) for e, n in rows]


def _deliver(s: Session, event: OutboxEvent, account: CommercialAccount, kind: str, number: str) -> None:
    if not (settings().project_commercials_enabled and settings().customer_portal_enabled):
        return  # no portal to point to: nothing is sent (the record itself is unaffected)
    link = app_link(f"/portal/properties/{account.property_id}#payments")
    for email, name in _recipients(s, account.lead_id):
        send("commercial_document", [email], event, name=name, kind=kind, number=number, link=link)


@handler(INVOICE_ISSUED)
def _invoice_issued(s: Session, event: OutboxEvent) -> None:
    inv = s.get(CommercialInvoice, event.payload.get("invoice_id"))
    if inv is None or inv.is_deleted or inv.status != "ISSUED" or inv.invoice_number is None:
        return  # cancelled before the worker ran: send nothing
    account = s.get(CommercialAccount, inv.account_id)
    if account is not None:
        _deliver(s, event, account, "invoice", inv.invoice_number)


@handler(RECEIPT_ISSUED)
def _receipt_issued(s: Session, event: OutboxEvent) -> None:
    r = s.get(CommercialReceipt, event.payload.get("receipt_id"))
    if r is None or r.is_deleted:
        return
    reversed_ = s.execute(sa.select(CommercialPaymentReversal.id)
                          .where(CommercialPaymentReversal.payment_id == r.payment_id)).first()  # fmt: skip
    if reversed_ is not None:
        return  # the payment was reversed before the worker ran
    account = s.get(CommercialAccount, r.account_id)
    if account is not None:
        _deliver(s, event, account, "receipt", r.receipt_number)
