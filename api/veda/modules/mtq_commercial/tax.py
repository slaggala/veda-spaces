"""GST on an estimate (instruction B3.7; owner decision OI-MTQ-07).

The architecture keeps taxable value, tax rate, tax amount and final amount explicit per line and in total. The
treatment itself is the owner's: while OI-MTQ-07 is not recorded, no tax is computed (``tax_minor`` and
``total_minor`` stay NULL, the status is GST_POLICY_REQUIRED) and the estimate cannot become customer-issuable. The
public estimator's 18 % display (ADR-012 §3.3) is not a quotation tax policy and is not reused.

Recorded treatment (SINGLE_RATE): each included priced line's taxable value is its amount less its allocated discount;
its tax is taxable × rate, half up to the paisa; the totals are the sums of the lines (so the document reconciles).
"""

from __future__ import annotations

from decimal import Decimal

from veda.modules.estimator import engine

from . import policy
from .models import CostEstimate, CostEstimateLine


def apply(est: CostEstimate, rows: list[CostEstimateLine]) -> None:
    decided = policy.decision("OI-MTQ-07")
    for x in rows:
        x.taxable_minor = (int(x.amount_minor) - int(x.discount_minor or 0)) if x.amount_minor is not None else None
        x.tax_rate_bp = None
        x.tax_minor = None
    if decided is None:
        est.tax_status, est.tax_minor, est.total_minor = "GST_POLICY_REQUIRED", None, None
        return
    tax_total = 0
    for x in rows:
        if x.taxable_minor is None:
            continue
        x.tax_rate_bp = decided.rate_bp
        x.tax_minor = engine.paise(Decimal(x.taxable_minor) * Decimal(decided.rate_bp) / Decimal(10_000))
        if not x.is_optional and x.rate_status == "PRICED":
            tax_total += x.tax_minor
    est.tax_status, est.tax_minor = "APPLIED", tax_total
    est.total_minor = est.taxable_minor + tax_total
