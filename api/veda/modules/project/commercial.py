"""COMMERCIAL_CONDITION (PEX-045): the commercial position a handover needs, exactly as owner decision PEX-D02 says.

The Project Lifecycle never prices, never records money and never writes to Project Commercials: this reads the one
position calculation (``commercials.position.compute``) of the commercial record of **this project's quotation chain**
(``quotation_number``; never "the latest record of the property", review D3).

- PEX-D02 unrecorded: fails closed (OWNER_DECISION_REQUIRED). The position is still shown for information.
- COMMERCIAL_OBLIGATION_SATISFIED (the owner's decision, decision log 46): Project Commercials says the obligation is
  satisfied (``commercials.obligation``: the record verifies and nothing is outstanding after accepted variations,
  reversals and any credit). No override exists; nothing else counts.
- NONE: no condition.
- NO_AMOUNT_DUE: a schedule exists and is in balance, and no instalment requested from the customer is unpaid (DUE,
  OVERDUE, or PARTIALLY_PAID after a request).
- FULLY_PAID: nothing is outstanding.

Unless the decision is NONE, it fails closed when Project Commercials is off, when the chain has no commercial record,
or when the record does not verify; NO_AMOUNT_DUE also when there is no schedule or it needs revision.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings

from . import delivery_policy
from .models import Project

GATE = "COMMERCIAL_CONDITION"


def _b(code: str, message: str, party: str = "VEDA", **extra: Any) -> dict[str, Any]:
    return {"gate": GATE, "code": code, "message": message, "responsible_party": party, **extra}


def account(s: Session, p: Project):
    from veda.modules.commercials.models import CommercialAccount

    return s.execute(sa.select(CommercialAccount).where(CommercialAccount.quotation_number == p.quotation_number,
                                                        CommercialAccount.is_deleted == sa.false())
                     ).scalar_one_or_none()  # fmt: skip


def position(s: Session, p: Project) -> dict[str, Any] | None:
    """The position for information (staff only), or None when there is no commercial record to read."""
    if not settings().project_commercials_enabled:
        return None
    acc = account(s, p)
    if acc is None:
        return None
    from veda.modules.commercials import money
    from veda.modules.commercials import position as pos

    x = pos.compute(s, acc)
    return {"account_id": acc.id, "value": money.text(x.value_minor), "paid": money.text(x.paid_minor),
            "outstanding": money.text(x.outstanding_minor), "schedule_state": x.schedule_state,
            "lines_due": sum(1 for line in x.lines if _requested_unpaid(line))}  # fmt: skip


def _requested_unpaid(line) -> bool:
    from veda.modules.commercials import vocab as CV

    if line.state in (CV.DUE, CV.OVERDUE):
        return True
    return line.state == CV.PARTIALLY_PAID and line.instalment.requested_on is not None


def blockers(s: Session, p: Project) -> list[dict[str, Any]]:
    od = delivery_policy.decision("PEX-D02")
    if od is None:
        r = delivery_policy.required("PEX-D02")
        return [_b(r["code"], r["message"], decision="PEX-D02")]
    if od.condition == "NONE":
        return []
    if not settings().project_commercials_enabled:
        return [_b("COMMERCIAL_POSITION_UNAVAILABLE", "Project Commercials is not enabled, so the commercial "
                   "condition for handover cannot be confirmed.")]  # fmt: skip
    acc = account(s, p)
    if acc is None:
        return [_b("COMMERCIAL_RECORD_MISSING", "This project's quotation has no commercial record, so the commercial "
                   "condition for handover cannot be confirmed.")]  # fmt: skip
    if od.condition == "COMMERCIAL_OBLIGATION_SATISFIED":
        from veda.modules.commercials import obligation

        ob = obligation.evaluate(s, acc)
        if ob.satisfied:
            return []
        party = "VEDA" if ob.code == "COMMERCIAL_RECORD_UNSOUND" else "CUSTOMER"
        return [_b(ob.code or "COMMERCIAL_OBLIGATION_OUTSTANDING", ob.message or "", party,
                   entity={"type": "commercial_account", "id": acc.id})]  # fmt: skip
    from veda.modules.commercials import baseline as cbase
    from veda.modules.commercials import payments as cpay
    from veda.modules.commercials import position as pos

    if cbase.problems(s, acc) or cpay.problems(s, acc):
        return [_b("COMMERCIAL_RECORD_UNSOUND", "The commercial record does not verify; it must be corrected first.",
                   entity={"type": "commercial_account", "id": acc.id})]  # fmt: skip
    x = pos.compute(s, acc)
    if od.condition == "FULLY_PAID":
        if x.outstanding_minor > 0:
            return [_b("AMOUNT_OUTSTANDING", "An amount is still outstanding on this project.", "CUSTOMER",
                       entity={"type": "commercial_account", "id": acc.id})]  # fmt: skip
        return []
    if x.schedule_state != "IN_BALANCE":
        return [_b("COMMERCIAL_SCHEDULE_NOT_IN_BALANCE", "The payment schedule is missing or needs revision, so what "
                   "is due cannot be confirmed.", entity={"type": "commercial_account", "id": acc.id})]  # fmt: skip
    due = [line for line in x.lines if _requested_unpaid(line)]
    if due:
        return [_b("AMOUNT_DUE", f"{len(due)} requested payment(s) are unpaid.", "CUSTOMER",
                   entity={"type": "commercial_account", "id": acc.id})]  # fmt: skip
    return []
