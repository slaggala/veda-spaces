"""The commercial position: the one calculation of what is owed, paid and outstanding (PCM-010).

Every consumer reads this object: the staff API, the customer portal, the invoice and the receipt. Nothing else sums
money, and the browser formats nothing::

    value        = the current baseline's cumulative value      (accepted base + accepted variations, frozen)
    paid         = Σ amounts of recorded payments with no reversal
    outstanding  = max(value − paid, 0)
    credit       = max(paid − value, 0)                         (only after a variation reduced the value)
    unscheduled  = value − the current schedule's total         (≠ 0: the schedule must be revised)

**Allocation is derived, never stored.** Valid payments are applied to the current schedule in order, the earliest
instalment with a balance first, so revising a schedule or reversing a payment never rewrites a payment: the
allocation follows from the facts. **Instalment status** is derived from the same facts (``state``): PAID, OVERDUE (a
balance and a due date before today), PARTIALLY_PAID, DUE (requested, with a balance), UPCOMING (not requested yet).
No due date is invented: only staff's payment request sets one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db

from . import baseline
from . import vocab as V
from .models import (
    CommercialAccount,
    CommercialBaseline,
    CommercialPayment,
    CommercialPaymentReversal,
    PaymentInstalment,
    PaymentSchedule,
)


@dataclass
class Line:
    instalment: PaymentInstalment
    applied_minor: int
    remaining_minor: int
    state: str

    @property
    def requested(self) -> bool:
        return self.instalment.requested_on is not None


def require_in_balance(p: Position) -> None:
    from veda.kernel.errors import ApiError

    if p.schedule_state == "REVISION_REQUIRED":
        from .money import text

        raise ApiError(409, "SCHEDULE_REVISION_REQUIRED", f"The project value changed; the schedule differs by "
                       f"{text(p.unscheduled_minor)}. Revise the schedule before asking for or invoicing a payment.")  # fmt: skip


@dataclass
class Position:
    account: CommercialAccount
    baseline: CommercialBaseline
    today: date
    value_minor: int
    tax_minor: int | None
    paid_minor: int
    outstanding_minor: int
    credit_minor: int
    schedule: PaymentSchedule | None
    lines: list[Line]
    schedule_total_minor: int
    unscheduled_minor: int
    schedule_state: str
    payments: list[tuple[CommercialPayment, CommercialPaymentReversal | None]] = field(default_factory=list)

    @property
    def next_line(self) -> Line | None:
        """The payment that matters next: a requested instalment with a balance, else the first with a balance."""
        if self.outstanding_minor <= 0:
            return None
        if self.schedule_state == "REVISION_REQUIRED":
            return None  # the schedule no longer adds up to the value: nothing is asked until it is revised
        open_ = [x for x in self.lines if x.remaining_minor > 0]
        requested = [x for x in open_ if x.requested]
        found = requested or open_
        return found[0] if found else None

    def line_of(self, instalment_id: str) -> Line | None:
        return next((x for x in self.lines if x.instalment.id == instalment_id), None)

    @property
    def valid_payments(self) -> list[CommercialPayment]:
        return [p for p, r in self.payments if r is None]

    def due_lines(self) -> list[Line]:
        """Instalments asked of the customer now. None while the schedule does not add up to the value (a variation
        changed it): its balances would not be what is owed (review M2)."""
        if self.schedule_state != "IN_BALANCE" or self.outstanding_minor <= 0:
            return []
        return [x for x in self.lines if x.state in (V.DUE, V.OVERDUE) or (x.state == V.PARTIALLY_PAID and x.requested)]


BUSINESS_TZ = "Asia/Kolkata"  # the business's calendar, as the number sequences use


def local_today(s: Session) -> date:
    """Today in India: what "received today", "due today" and "overdue" mean to staff and customers."""
    from zoneinfo import ZoneInfo

    return db.tx_time(s).astimezone(ZoneInfo(BUSINESS_TZ)).date()


def local_date(instant) -> date:
    from zoneinfo import ZoneInfo

    return instant.astimezone(ZoneInfo(BUSINESS_TZ)).date()


def state(inst: PaymentInstalment, applied: int, today: date) -> str:
    remaining = int(inst.amount_minor) - applied
    if remaining <= 0:
        return V.PAID
    if inst.due_on is not None and inst.due_on < today:
        return V.OVERDUE
    if applied > 0:
        return V.PARTIALLY_PAID
    if inst.requested_on is not None:
        return V.DUE
    return V.UPCOMING


def current_schedule(s: Session, account_id: str) -> PaymentSchedule | None:
    return s.execute(sa.select(PaymentSchedule).where(PaymentSchedule.account_id == account_id,
                                                      PaymentSchedule.status == "CURRENT",
                                                      PaymentSchedule.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip


def instalments(s: Session, schedule_id: str) -> list[PaymentInstalment]:
    return list(s.execute(sa.select(PaymentInstalment).where(PaymentInstalment.schedule_id == schedule_id,
                                                             PaymentInstalment.is_deleted == sa.false())
                          .order_by(PaymentInstalment.position)).scalars())  # fmt: skip


def payments(s: Session, account_id: str) -> list[tuple[CommercialPayment, CommercialPaymentReversal | None]]:
    rows = s.execute(
        sa.select(CommercialPayment, CommercialPaymentReversal)
        .outerjoin(CommercialPaymentReversal, sa.and_(CommercialPaymentReversal.payment_id == CommercialPayment.id,
                                                      CommercialPaymentReversal.is_deleted == sa.false()))
        .where(CommercialPayment.account_id == account_id, CommercialPayment.is_deleted == sa.false())
        .order_by(CommercialPayment.received_on, CommercialPayment.created_on, CommercialPayment.id)
    ).all()  # fmt: skip
    return [(p, r) for p, r in rows]


def allocate(amounts: list[int], paid: int) -> list[int]:
    """Apply ``paid`` to the instalment amounts in order (the earliest with a balance first)."""
    out, left = [], max(paid, 0)
    for a in amounts:
        take = min(a, left)
        out.append(take)
        left -= take
    return out


def compute(s: Session, account: CommercialAccount, *, today: date | None = None) -> Position:
    today = today or local_today(s)
    base = baseline.current(s, account)
    pays = payments(s, account.id)
    paid = sum(int(p.amount_minor) for p, r in pays if r is None)
    value = int(base.value_minor)
    schedule = current_schedule(s, account.id)
    insts = instalments(s, schedule.id) if schedule is not None else []
    applied = allocate([int(i.amount_minor) for i in insts], paid)
    lines = [Line(i, a, int(i.amount_minor) - a, state(i, a, today)) for i, a in zip(insts, applied, strict=True)]
    total = sum(int(i.amount_minor) for i in insts)
    unscheduled = value - total if schedule is not None else value
    sched_state = "NONE" if schedule is None else ("IN_BALANCE" if unscheduled == 0 else "REVISION_REQUIRED")
    return Position(
        account=account, baseline=base, today=today, value_minor=value, tax_minor=base.tax_minor, paid_minor=paid,
        outstanding_minor=max(value - paid, 0), credit_minor=max(paid - value, 0), schedule=schedule, lines=lines,
        schedule_total_minor=total, unscheduled_minor=unscheduled, schedule_state=sched_state, payments=pays,
    )  # fmt: skip


def figures(p: Position) -> dict[str, Any]:
    """The position as integers and as the quotation prints them (both computed here, never in a browser)."""
    from .money import text

    nxt = p.next_line
    return {
        "currency": p.account.currency,
        "value_minor": p.value_minor, "value": text(p.value_minor),
        "tax_minor": p.tax_minor, "tax": text(p.tax_minor),
        "paid_minor": p.paid_minor, "paid": text(p.paid_minor),
        "outstanding_minor": p.outstanding_minor, "outstanding": text(p.outstanding_minor),
        "credit_minor": p.credit_minor, "credit": text(p.credit_minor) if p.credit_minor else None,
        "schedule_state": p.schedule_state,
        "unscheduled_minor": p.unscheduled_minor, "unscheduled": text(p.unscheduled_minor),
        "next_instalment_id": nxt.instalment.id if nxt else None,
        "as_of": p.today.isoformat(),
    }  # fmt: skip
