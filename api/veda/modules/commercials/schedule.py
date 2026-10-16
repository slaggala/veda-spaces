"""Payment schedules (PCM-005 … PCM-008).

A schedule revision is a list of instalments whose amounts add up **exactly** to the current commercial value; nothing
else changes instalments. Revision 1 is built when the record is opened, from the accepted base quotation's frozen
payment milestones (OI-MTQ-09: label, share, trigger): amounts split the accepted value by the frozen shares with the
quotation's own largest-remainder function, so they always add up. (The issued document printed its milestone amounts
from the total without optional items; the accepted value includes the items the customer chose, so the shares, not
the printed amounts, are the contractual basis. The issued document is never changed.) A quotation that froze no
milestones gets no schedule until staff create one.

Each instalment's GST is the baseline's frozen GST apportioned over the instalment amounts (largest remainder): never a
rate applied anew. Unknown GST stays unknown.

A revision (staff, with a reason, under the account lock) supersedes the current schedule; payments are never touched,
because allocation is derived (``position``). An instalment that carries an issued invoice must survive a revision
unchanged (same label and amount); it is carried over with its payment request and due date, and the invoice follows
it. A payment request marks an instalment as asked of the customer, optionally by a date staff set (never in the past).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError, field_error
from veda.modules.mtq_commercial.models import Quotation

from . import events, money, position
from . import vocab as V
from .models import CommercialAccount, CommercialInvoice, PaymentInstalment, PaymentSchedule


def _taxes(tax_total: int | None, amounts: list[int]) -> list[int | None]:
    if tax_total is None or not amounts:
        return [None] * len(amounts)
    parts = money.apportion(tax_total, amounts)
    if parts is None or any(t < 0 or t > a for t, a in zip(parts, amounts, strict=True)):
        return [None] * len(amounts)
    return list(parts)


def _new(s: Session, account: CommercialAccount, pos: position.Position, *, source: str, reason: str | None,
         items: list[dict[str, Any]]) -> PaymentSchedule:  # fmt: skip
    revision = (s.execute(sa.select(sa.func.max(PaymentSchedule.revision_no))
                          .where(PaymentSchedule.account_id == account.id)).scalar() or 0) + 1  # fmt: skip
    amounts = [int(x["amount_minor"]) for x in items]
    taxes = _taxes(pos.tax_minor, amounts)
    sched = PaymentSchedule(account_id=account.id, lead_id=account.lead_id, revision_no=revision, status="CURRENT",
                            source=source, basis_baseline_seq=pos.baseline.sequence_no, total_minor=sum(amounts),
                            tax_minor=pos.tax_minor if all(t is not None for t in taxes) else None,
                            reason=reason)  # fmt: skip
    s.add(sched)
    s.flush()
    for n, (x, tax) in enumerate(zip(items, taxes, strict=True), start=1):
        s.add(PaymentInstalment(
            account_id=account.id, lead_id=account.lead_id, schedule_id=sched.id, position=n, label=x["label"],
            when_text=x["when"], amount_minor=int(x["amount_minor"]), tax_minor=tax, share_bp=x.get("share_bp"),
            requested_on=x.get("requested_on"), requested_by=x.get("requested_by"), due_on=x.get("due_on"),
            carried_from_id=x.get("carried_from_id"),
        ))  # fmt: skip
    s.flush()
    return sched


def initial(s: Session, account: CommercialAccount, base: Quotation) -> PaymentSchedule | None:
    """Revision 1 from the accepted base quotation's frozen milestones (None when it froze none)."""
    milestones = (base.terms or {}).get("payment_milestones") or []
    pos = position.compute(s, account)
    shares = [int(m["share_bp"]) for m in milestones]
    amounts = money.by_shares(pos.value_minor, shares) if milestones else None
    if not amounts or any(a <= 0 for a in amounts):
        return None
    items = [{"label": m["label"], "when": m["trigger"], "amount_minor": a, "share_bp": int(m["share_bp"])}
             for m, a in zip(milestones, amounts, strict=True)]  # fmt: skip
    sched = _new(s, account, pos, source="QUOTATION_MILESTONES", reason=None, items=items)
    events.record(s, account, "SCHEDULE_CREATED", sched.id, revision_no=sched.revision_no, source=sched.source,
                  total_minor=sched.total_minor, instalments=len(items), quotation_id=base.id)  # fmt: skip
    return sched


def _issued_invoices(s: Session, schedule_id: str) -> list[CommercialInvoice]:
    return list(s.execute(sa.select(CommercialInvoice).where(CommercialInvoice.schedule_id == schedule_id,
                                                             CommercialInvoice.status == "ISSUED",
                                                             CommercialInvoice.is_deleted == sa.false())).scalars())  # fmt: skip


def revise(s: Session, ctx, account: CommercialAccount, body) -> PaymentSchedule:
    """Replace the current schedule with ``body.instalments`` (amounts in paise, adding up to the current value)."""
    pos = position.compute(s, account)
    items = list(body.instalments)
    errors = []
    total = sum(int(x.amount_minor) for x in items)
    if total != pos.value_minor:
        errors.append(field_error("instalments", "TOTAL_MISMATCH", f"The instalments add up to {money.text(total)}; the "
                                  f"project value is {money.text(pos.value_minor)}."))  # fmt: skip
    today = pos.today
    for n, x in enumerate(items):
        if x.due_on is not None and x.due_on < today:
            errors.append(field_error(f"instalments[{n}].due_on", "IN_THE_PAST", "A due date cannot be in the past."))
    if errors:
        raise ApiError(422, "VALIDATION_FAILED", "The schedule does not add up to the project value.", errors=errors)
    current = pos.schedule
    previous: dict[tuple[str, int], list[PaymentInstalment]] = {}
    for i in position.instalments(s, current.id) if current else []:
        previous.setdefault((i.label, int(i.amount_minor)), []).append(i)
    out: list[dict[str, Any]] = []
    for x in items:
        same = previous.get((x.label, int(x.amount_minor))) or []
        before = same.pop(0) if same else None
        requested = before is not None and before.requested_on is not None
        row: dict[str, Any] = {"label": x.label, "when": x.when, "amount_minor": int(x.amount_minor),
                               "share_bp": before.share_bp if before else None,
                               "carried_from_id": before.id if before else None}  # fmt: skip
        if x.requested or x.due_on is not None or requested:
            row["requested_on"] = before.requested_on if requested else db.tx_time(s)
            row["requested_by"] = before.requested_by if requested else ctx.user.id
            row["due_on"] = x.due_on if x.due_on is not None else (before.due_on if requested else None)
        out.append(row)
    if current is not None:
        dropped = {i.id for rest in previous.values() for i in rest}
        blocking = [inv.invoice_number for inv in _issued_invoices(s, current.id) if inv.instalment_id in dropped]
        if blocking:
            raise ApiError(409, "INVOICE_BLOCKS_REVISION", "An issued invoice requests an instalment this revision "
                           f"changes or removes ({', '.join(b or '' for b in blocking)}). Cancel the invoice first, or "
                           "keep that instalment's label and amount.", extra={"invoices": blocking})  # fmt: skip
        current.status, current.superseded_on = "SUPERSEDED", db.tx_time(s)
        s.flush()
    sched = _new(s, account, pos, source="REVISION", reason=body.reason, items=out)
    carried = {r["carried_from_id"]: r for r in out if r.get("carried_from_id")}
    if current is not None and carried:
        new_of = {i.carried_from_id: i for i in position.instalments(s, sched.id) if i.carried_from_id}
        for inv in s.execute(sa.select(CommercialInvoice).where(CommercialInvoice.schedule_id == current.id,
                                                                CommercialInvoice.status.in_(V.LIVE_INVOICE_STATUSES),
                                                                CommercialInvoice.is_deleted == sa.false())).scalars():  # fmt: skip
            target = new_of.get(inv.instalment_id)
            if target is not None:
                inv.schedule_id, inv.instalment_id = sched.id, target.id
            elif inv.status == "DRAFT":  # a draft for a removed instalment is discarded with the old schedule
                inv.is_deleted = True
                events.record(s, account, "INVOICE_DISCARDED", inv.id, reason_code="SCHEDULE_REVISED")
    events.record(s, account, "SCHEDULE_REVISED", sched.id, revision_no=sched.revision_no,
                  previous_revision_no=current.revision_no if current else None, total_minor=sched.total_minor,
                  instalments=len(out), basis_baseline_seq=sched.basis_baseline_seq)  # fmt: skip
    return sched


def request(s: Session, ctx, account: CommercialAccount, inst: PaymentInstalment, due_on: date | None) -> None:
    """Ask the customer for ``inst`` (of the current schedule, with a balance), optionally by ``due_on``."""
    pos = position.compute(s, account)
    line = pos.line_of(inst.id)
    if line is None or pos.schedule is None or inst.schedule_id != pos.schedule.id:
        raise ApiError(409, "INSTALMENT_NOT_CURRENT", "This instalment belongs to an earlier schedule.")
    if line.remaining_minor <= 0:
        raise ApiError(409, "INSTALMENT_PAID", f"{inst.label} is already paid.")
    if due_on is not None and due_on < pos.today:
        raise ApiError(422, "VALIDATION_FAILED", "A due date cannot be in the past.",
                       errors=[field_error("due_on", "IN_THE_PAST", "A due date cannot be in the past.")])  # fmt: skip
    first = inst.requested_on is None
    if first:
        inst.requested_on, inst.requested_by = db.tx_time(s), ctx.user.id
    inst.due_on = due_on
    events.record(s, account, "PAYMENT_REQUESTED", inst.id, position=inst.position, amount_minor=line.remaining_minor,
                  due_on=due_on, first_request=first)  # fmt: skip
