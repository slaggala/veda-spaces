"""Whether the customer's commercial obligation on a project is satisfied (owner decision PEX-D02, decision log 46).

Project Commercials is the only source of commercial truth; a consumer (the Project Lifecycle's COMMERCIAL_CONDITION
gate) asks this and never sums money itself. The obligation is satisfied when the record verifies and the one position
calculation (``position.compute``) leaves nothing outstanding:

- the value is the current baseline: the accepted base plus every accepted variation, so a variation that raised or
  reduced the value is already in it;
- only payments with no reversal count, so a reversed payment no longer satisfies anything;
- a credit (paid more than a reduced value) leaves nothing outstanding and satisfies it.

There is no exception or override: a legitimate business exception would need an explicit, authorised, reasoned and
audited mechanism that no owner policy defines yet, so nothing here ever treats an unpaid obligation as satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from . import baseline, payments, position
from .models import CommercialAccount


@dataclass(frozen=True)
class Obligation:
    satisfied: bool
    code: str | None  # why not, when not satisfied
    message: str | None
    position: position.Position | None


def evaluate(s: Session, account: CommercialAccount) -> Obligation:
    if baseline.problems(s, account) or payments.problems(s, account):
        return Obligation(False, "COMMERCIAL_RECORD_UNSOUND", "The commercial record does not verify; it must be "
                          "corrected first.", None)  # fmt: skip
    x = position.compute(s, account)
    if x.outstanding_minor > 0:
        from .money import text

        return Obligation(False, "COMMERCIAL_OBLIGATION_OUTSTANDING", f"{text(x.outstanding_minor)} of the project "
                          "value is still to be paid.", x)  # fmt: skip
    return Obligation(True, None, None, x)
