"""Variations (change orders) after acceptance (instruction B4.4; B1-SCOPE §2.7 frozen design; OI-MTQ-13).

An accepted quotation never changes. A change after acceptance is a VARIATION: its own quotation row under the same
quotation number (``VS-Q-…-V01``, ``-V02`` …), with its own versions and lifecycle, priced from a newly approved
estimate of the changed scope and compared, line by line, with the **accepted baseline**: the estimate behind the
latest accepted quotation in the chain (the base, or the last accepted variation).

Lines are deltas keyed by requirement and catalogue line: ADD, OMIT, CHANGE_QUANTITY, CHANGE_FINISH, CHANGE_RATE, and
CHANGE_MATERIAL when the same requirement moves to different catalogue lines (an option or material change). Values are
taxable values (amount less allocated discount), so a variation's net change is what the customer pays or saves before
GST; GST on it follows the decided treatment. The accepted value of the job is the base's accepted total plus every
accepted variation's total. Whether variations, and rate changes in them, are permitted is the owner's (OI-MTQ-13):
until decided a variation can be drafted and reviewed but not issued.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.modules.crm.leads.models import OPEN_STATUSES, Lead
from veda.modules.mtq.models import Property

from . import estimates, policy, quotations, requirements
from .models import CostEstimate, CostEstimateLine, Quotation, QuotationLine, QuotationSection


def _taxable(x: CostEstimateLine) -> int:
    return int(x.amount_minor or 0) - int(x.discount_minor or 0)


def baseline_of(s: Session, base: Quotation) -> Quotation:
    """The latest accepted quotation in the chain of ``base``: the base itself or its last accepted variation."""
    accepted = s.execute(
        sa.select(Quotation)
        .where(Quotation.quotation_number == base.quotation_number, Quotation.status == "ACCEPTED")
        .order_by(Quotation.variation_no.desc(), Quotation.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()
    if accepted is None:
        raise ApiError(409, "BASE_NOT_ACCEPTED", "A variation is raised against an accepted quotation.")
    return accepted


def _included(s: Session, est: CostEstimate) -> dict[str, CostEstimateLine]:
    return {quotations.line_key(x): x for x in estimates.lines(s, est) if not x.is_optional}


def _deltas(old: dict[str, CostEstimateLine], new: dict[str, CostEstimateLine]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    added = {k: x for k, x in new.items() if k not in old}
    omitted = {k: x for k, x in old.items() if k not in new}
    moved = {x.requirement_id for x in added.values() if x.requirement_id} & {
        x.requirement_id for x in omitted.values() if x.requirement_id
    }
    for k, x in new.items():
        before = old.get(k)
        if before is None:
            code = "CHANGE_MATERIAL" if x.requirement_id in moved else "ADD"
            out.append({"key": k, "line": x, "code": code, "baseline": 0, "amount": _taxable(x)})
            continue
        if x.finish_code != before.finish_code:
            code = "CHANGE_FINISH"
        elif x.quantity_centi != before.quantity_centi:
            code = "CHANGE_QUANTITY"
        elif x.rate_minor != before.rate_minor or x.rate_status != before.rate_status:
            code = "CHANGE_RATE"
        elif _taxable(x) != _taxable(before):
            code = "CHANGE_RATE"  # same quantity and rate, a different discount: a price change all the same
        else:
            continue
        out.append({"key": k, "line": x, "code": code, "baseline": _taxable(before), "amount": _taxable(x)})
    for k, x in omitted.items():
        code = "CHANGE_MATERIAL" if x.requirement_id in moved else "OMIT"
        out.append({"key": k, "line": x, "code": code, "baseline": _taxable(x), "amount": 0, "omitted": True})
    return out


def _build(s: Session, q: Quotation, baseline: Quotation, est: CostEstimate) -> None:
    base_est = s.get(CostEstimate, baseline.cost_estimate_id)
    assert base_est is not None
    rows = _deltas(_included(s, base_est), _included(s, est))
    prop = s.get(Property, q.property_id)
    assert prop is not None
    spaces = requirements.spaces_of(s, prop)
    sec = QuotationSection(
        quotation_id=q.id, position=1, section_code="VARIATION", title="Changes to the accepted scope"
    )
    s.add(sec)
    s.flush()
    net = 0
    unpriced = False
    for n, d in enumerate(rows, start=1):
        x: CostEstimateLine = d["line"]
        priced = d.get("omitted") or x.rate_status == "PRICED"
        unpriced = unpriced or not priced
        delta = d["amount"] - d["baseline"] if priced else None
        net += delta or 0
        room = spaces[x.space_id].label if x.space_id in spaces else "Project-wide"
        s.add(QuotationLine(
            quotation_id=q.id, section_id=sec.id, cost_estimate_line_id=None if d.get("omitted") else x.id,
            requirement_id=x.requirement_id, space_id=x.space_id, position=n, line_key=d["key"][:200],
            description=x.label[:300], detail=room, uom_code=x.uom_code,
            quantity_centi=None if d.get("omitted") else x.quantity_centi, finish_code=x.finish_code,
            rate_minor=None if d.get("omitted") else x.rate_minor, amount_minor=d["amount"] if priced else None,
            discount_minor=0, is_priced=bool(priced), is_optional=False, is_mandatory=False, change_code=d["code"],
            baseline_amount_minor=d["baseline"], delta_amount_minor=delta,
        ))  # fmt: skip
    sec.subtotal_minor = net
    q.base_total_minor, q.optional_minor, q.discount_minor, q.taxable_minor = net, 0, 0, net
    tax = policy.decision("OI-MTQ-07")
    if tax is None:
        q.tax_status, q.tax_minor, q.total_minor = "GST_POLICY_REQUIRED", None, None
    else:
        from decimal import Decimal

        from veda.modules.estimator import engine

        q.tax_status = "APPLIED"
        q.tax_minor = engine.paise(Decimal(net) * Decimal(tax.rate_bp) / Decimal(10_000))
        q.total_minor = net + q.tax_minor
    s.flush()


def create(s: Session, ctx, base: Quotation, est: CostEstimate, prop: Property, body) -> Quotation:
    if base.quotation_kind != "BASE":
        raise ApiError(422, "VALIDATION_FAILED", "Raise a variation on the base quotation.")
    baseline = baseline_of(s, base)
    quotations.require_estimate_ready(s, est)
    if est.property_id != base.property_id:
        raise ApiError(422, "VALIDATION_FAILED", "The estimate belongs to another property.")
    if est.id == baseline.cost_estimate_id:
        raise ApiError(422, "NO_CHANGE", "This is the accepted estimate; price the changed scope first.")
    open_ = s.execute(
        sa.select(Quotation).where(
            Quotation.quotation_number == base.quotation_number,
            Quotation.variation_no > 0,
            Quotation.status.in_(("DRAFT", "INTERNAL_REVIEW", "APPROVED", "ISSUED")),
        )  # fmt: skip
    ).first()
    if open_ is not None:
        raise ApiError(409, "VARIATION_OPEN", "A variation is still open; decide it before raising another.",
                       extra={"quotation_id": open_[0].id})  # fmt: skip
    top = s.execute(
        sa.select(sa.func.max(Quotation.variation_no)).where(Quotation.quotation_number == base.quotation_number)
    ).scalar()
    q = quotations._new(s, est, prop, number=base.quotation_number, version_no=1, kind="VARIATION",
                        variation_no=int(top or 0) + 1, variation_of=base.id, baseline=baseline.id,
                        title=(body.title if body and body.title else f"Variation to {base.quotation_number}"))  # fmt: skip
    q.cover_note = body.cover_note if body else None
    _build(s, q, baseline, est)
    quotations.event(s, q, "VARIATION_CREATED", None, "DRAFT", base_quotation_id=base.id,
                     baseline_quotation_id=baseline.id, cost_estimate_id=est.id)  # fmt: skip
    quotations.refresh_blockers(s, q)
    return q


def new_version(s: Session, ctx, q: Quotation, est: CostEstimate, prop: Property) -> Quotation:
    quotations.require_estimate_ready(s, est)
    baseline = s.get(Quotation, q.baseline_quotation_id)
    assert baseline is not None
    if q.status in ("DRAFT", "INTERNAL_REVIEW", "APPROVED"):
        quotations._supersede(s, q)
    nq = quotations._new(s, est, prop, number=q.quotation_number, version_no=q.version_no + 1, kind="VARIATION",
                         variation_no=q.variation_no, supersedes=q, title=q.title,
                         variation_of=q.variation_of_quotation_id, baseline=baseline.id)  # fmt: skip
    _build(s, nq, baseline, est)
    quotations.event(s, nq, "VERSION_CREATED", None, "DRAFT", supersedes_quotation_id=q.id, cost_estimate_id=est.id)
    quotations.refresh_blockers(s, nq)
    return nq


def accepted_value(s: Session, number: str) -> int | None:
    """The job's accepted value: the base's accepted total plus every accepted variation's total."""
    rows = (
        s.execute(sa.select(Quotation).where(Quotation.quotation_number == number, Quotation.status == "ACCEPTED"))
        .scalars()
        .all()
    )
    if not any(r.variation_no == 0 for r in rows):
        return None
    return sum(int(r.accepted_total_minor or 0) for r in rows)


def on_accepted(s: Session, q: Quotation) -> None:
    """The base stays ACCEPTED and untouched; the lead's quoted amount follows the job's accepted value."""
    value = accepted_value(s, q.quotation_number)
    lead = s.get(Lead, q.lead_id)
    if value is not None and lead is not None and lead.status in OPEN_STATUSES:
        lead.quoted_amount_minor = max(0, value)
    s.flush()


def chain(s: Session, number: str) -> list[dict[str, Any]]:
    rows = s.execute(
        sa.select(Quotation)
        .where(Quotation.quotation_number == number)
        .order_by(Quotation.variation_no, Quotation.version_no)  # fmt: skip
    ).scalars()
    return [{"id": r.id, "label": quotations.number_label(r), "kind": r.quotation_kind, "status": r.status,
             "total_minor": r.total_minor, "accepted_total_minor": r.accepted_total_minor} for r in rows]  # fmt: skip
