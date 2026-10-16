"""Staff views of Project Commercials. Every figure comes from ``position.compute``; the page formats nothing."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq.models import Property
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation
from veda.platform.identity.models import User

from . import access, baseline, payments, policy, position
from . import vocab as V
from .models import CommercialAccount, CommercialEvent, CommercialInvoice, CommercialReceipt, PaymentSchedule
from .money import text


class People:
    def __init__(self, s: Session):
        self.s = s
        self._names: dict[str, str | None] = {}

    def __call__(self, uid: str | None) -> dict[str, Any] | None:
        if not uid:
            return None
        if uid not in self._names:
            u = self.s.get(User, uid)
            self._names[uid] = (u.display_name or u.full_name) if u else None
        return {"id": uid, "display_name": self._names[uid]}


def _when(value) -> str | None:
    return clock.to_rfc3339(value) if value else None


def _day(value) -> str | None:
    return value.isoformat() if value else None


def _header(s: Session, account: CommercialAccount) -> dict[str, Any]:
    lead = s.get(Lead, account.lead_id)
    prop = s.get(Property, account.property_id)
    base = s.get(Quotation, account.base_quotation_id)
    return {"id": account.id, "version": account.version, "quotation_number": account.quotation_number,
            "base_quotation": {"id": account.base_quotation_id, "reference": quotations.number_label(base) if base else None},
            "lead": {"id": account.lead_id, "name": lead.name if lead else None,
                     "reference": lead.public_reference if lead else None,
                     "erased": bool(lead is None or lead.anonymized_on is not None)},
            "property": {"id": account.property_id, "reference": prop.property_number if prop else None,
                         "city": prop.city if prop else None},
            "opened_on": _when(account.created_on)}  # fmt: skip


def summary(s: Session, account: CommercialAccount) -> dict[str, Any]:
    pos = position.compute(s, account)
    nxt = pos.next_line
    return {**_header(s, account), "position": position.figures(pos),
            "next": {"label": nxt.instalment.label, "amount": text(nxt.remaining_minor), "state": nxt.state,
                     "due_on": _day(nxt.instalment.due_on)} if nxt else None,
            "overdue": sum(1 for x in pos.lines if x.state == V.OVERDUE)}  # fmt: skip


def _invoice(inv: CommercialInvoice, people: People, pos: position.Position | None = None) -> dict[str, Any]:
    out = {"id": inv.id, "version": inv.version, "status": inv.status, "number": inv.invoice_number,
           "instalment_id": inv.instalment_id, "schedule_id": inv.schedule_id,
           "label": ((inv.snapshot or {}).get("instalment") or {}).get("label"),
           "amount_minor": inv.amount_minor, "amount": text(inv.amount_minor), "gst_included": text(inv.tax_minor),
           "due_on": _day(inv.due_on), "customer_note": inv.customer_note,
           "drafted_on": _when(inv.created_on), "drafted_by": people(inv.created_by),
           "issued_on": _when(inv.issued_on), "issued_by": people(inv.issued_by),
           "cancelled_on": _when(inv.cancelled_on), "cancelled_by": people(inv.cancelled_by),
           "cancel_reason": inv.cancel_reason}  # fmt: skip
    if pos is not None and out["label"] is None:
        line = pos.line_of(inv.instalment_id)
        out["label"] = line.instalment.label if line else None
    return out


def detail(s: Session, ctx, account: CommercialAccount) -> dict[str, Any]:
    pos = position.compute(s, account)
    people = People(s)
    receipts = {r.payment_id: r for r in s.execute(sa.select(CommercialReceipt).where(
        CommercialReceipt.account_id == account.id, CommercialReceipt.is_deleted == sa.false())).scalars()}  # fmt: skip
    invoices = list(s.execute(sa.select(CommercialInvoice).where(CommercialInvoice.account_id == account.id,
                                                                 CommercialInvoice.is_deleted == sa.false())
                              .order_by(CommercialInvoice.created_on.desc())).scalars())  # fmt: skip
    live = {inv.instalment_id: inv for inv in invoices if inv.status in V.LIVE_INVOICE_STATUSES}
    lines = []
    for x in pos.lines:
        i = x.instalment
        inv = live.get(i.id)
        lines.append({"id": i.id, "position": i.position, "label": i.label, "when": i.when_text,
                      "amount_minor": i.amount_minor, "amount": text(i.amount_minor), "gst_included": text(i.tax_minor),
                      "share": f"{i.share_bp / 100:g}%" if i.share_bp else None,
                      "applied_minor": x.applied_minor, "applied": text(x.applied_minor),
                      "remaining_minor": x.remaining_minor, "remaining": text(x.remaining_minor),
                      "state": x.state, "state_label": V.INSTALMENT_LABELS[x.state],
                      "requested_on": _when(i.requested_on), "requested_by": people(i.requested_by),
                      "due_on": _day(i.due_on),
                      "invoice": {"id": inv.id, "number": inv.invoice_number, "status": inv.status} if inv else None})  # fmt: skip
    revisions = [{"id": r.id, "revision_no": r.revision_no, "status": r.status, "source": r.source, "reason": r.reason,
                  "total": text(r.total_minor), "basis_baseline_seq": r.basis_baseline_seq,
                  "created_on": _when(r.created_on), "created_by": people(r.created_by),
                  "superseded_on": _when(r.superseded_on)}
                 for r in s.execute(sa.select(PaymentSchedule).where(PaymentSchedule.account_id == account.id)
                                    .order_by(PaymentSchedule.revision_no.desc())).scalars()]  # fmt: skip
    pays = []
    for p, r in reversed(pos.payments):
        rc = receipts.get(p.id)
        pays.append({"id": p.id, "amount_minor": p.amount_minor, "amount": text(p.amount_minor),
                     "received_on": p.received_on.isoformat(), "method_code": p.method_code,
                     "method": V.METHOD_LABELS[p.method_code], "external_reference": p.external_reference,
                     "customer_note": p.customer_note, "internal_note": p.internal_note,
                     "recorded_on": _when(p.created_on), "recorded_by": people(p.created_by),
                     "status": "REVERSED" if r else "RECORDED",
                     "reversal": {"reason_code": r.reason_code, "note": r.note, "reversed_on": _when(r.created_on),
                                  "reversed_by": people(r.created_by)} if r else None,
                     "receipt": {"id": rc.id, "number": rc.receipt_number} if rc else None})  # fmt: skip
    chain = [{"sequence_no": b.sequence_no, "kind": b.kind, "quotation_id": b.quotation_id,
              "reference": f"{b.quotation_number}{f'-V{b.variation_no:02d}' if b.variation_no else ''} v{b.version_no}",
              "accepted_total": text(b.accepted_total_minor), "accepted_gst": text(b.accepted_tax_minor),
              "value": text(b.value_minor), "decided_on": _when(b.decided_on), "baseline_sha256": b.baseline_sha256,
              "snapshot_sha256": b.snapshot_sha256}
             for b in baseline.rows(s, account.id)]  # fmt: skip
    problems = baseline.problems(s, account) + payments.problems(s, account)
    lead = s.get(Lead, account.lead_id)
    writable = lead is not None and not lead.is_deleted and lead.anonymized_on is None
    can = lambda code: access.can(s, ctx, account, code)  # noqa: E731
    return {
        **_header(s, account),
        "position": position.figures(pos),
        "baseline": chain,
        "schedule": (
            {
                "id": pos.schedule.id,
                "revision_no": pos.schedule.revision_no,
                "source": pos.schedule.source,
                "reason": pos.schedule.reason,
                "total": text(pos.schedule_total_minor),
                "lines": lines,
            }
            if pos.schedule
            else None
        ),  # fmt: skip
        "revisions": revisions,
        "payments": pays,
        "invoices": [_invoice(inv, people, pos) for inv in invoices],
        "problems": problems,
        "policy": policy.view(),
        "capabilities": {
            "writable": writable and not problems,
            "manage_schedule": can("commercials.schedule.manage"),
            "record_payment": can("commercials.payment.record"),
            "reverse_payment": can("commercials.payment.reverse"),
            "issue_invoice": can("commercials.invoice.issue"),
            "view_audit": can("commercials.audit.view"),
            "invoice_issuable": policy.decision("PCM-D01") is not None,
        },  # fmt: skip
        "methods": [{"code": c, "label": V.METHOD_LABELS[c]} for c in V.PAYMENT_METHODS],
        "reversal_reasons": list(V.REVERSAL_REASONS),
    }


def history(s: Session, account: CommercialAccount) -> list[dict[str, Any]]:
    people = People(s)
    rows = s.execute(sa.select(CommercialEvent).where(CommercialEvent.account_id == account.id)
                     .order_by(CommercialEvent.created_on.desc(), CommercialEvent.id.desc())).scalars()  # fmt: skip
    return [{"id": e.id, "code": e.event_code, "entity_id": (e.detail or {}).get("entity"), "detail": e.detail, "at": _when(e.created_on),
             "by": people(e.created_by)} for e in rows]  # fmt: skip


def candidate(s: Session, q: Quotation) -> dict[str, Any]:
    lead = s.get(Lead, q.lead_id)
    prop = s.get(Property, q.property_id)
    return {"quotation_id": q.id, "reference": quotations.number_label(q), "quotation_number": q.quotation_number,
            "lead": {"id": q.lead_id, "name": lead.name if lead else None},
            "property": {"id": q.property_id, "reference": prop.property_number if prop else None},
            "accepted_total": text(q.accepted_total_minor), "decided_on": _when(q.decided_on)}  # fmt: skip
