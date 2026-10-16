"""Exact money for Project Commercials: integer paise only, never a float (the quotation's representation).

``apportion`` splits a total over positive weights by the largest-remainder method the quotation's milestone amounts
use (``mtq_commercial.customer_pack.milestone_amounts``): floors first, then the paise left over one each to the largest
remainders, the earlier part first on a tie. The parts always add up to the total, and the same inputs always give the
same parts. ``parse_rupees`` reads a staff-entered rupee string exactly (no float) for request bodies that use rupees.
"""

from __future__ import annotations

import re
from decimal import Decimal

from veda.modules.mtq_commercial import customer_pack

RUPEES_RE = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$")


def apportion(total: int, weights: list[int]) -> list[int] | None:
    """``total`` split over ``weights`` (each > 0), reconciling exactly; None when there is nothing to weigh by."""
    if not weights or any(w <= 0 for w in weights):
        return None
    whole = sum(weights)
    raw = [total * w for w in weights]
    floors = [r // whole for r in raw]
    left = total - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i] % whole), i))
    for i in order[:left]:
        floors[i] += 1
    return floors


def by_shares(total: int, shares_bp: list[int]) -> list[int] | None:
    """The quotation's own milestone split (shares in basis points adding up to 10 000)."""
    return customer_pack.milestone_amounts(total, shares_bp)


def text(minor: int | None) -> str | None:
    """The figure as the quotation document prints it (``123,456.00``), so the same amount reads the same everywhere."""
    return customer_pack.money(minor)


def parse_rupees(value: str) -> int:
    v = value.strip().replace(",", "")
    if not RUPEES_RE.match(v):
        raise ValueError("not a rupee amount")
    return int((Decimal(v) * 100).to_integral_exact())
