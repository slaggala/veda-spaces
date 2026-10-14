"""Discounts on a draft estimate (instruction B3.6; blueprint §4.2 ``cost_estimate_adjustment``; OI-MTQ-06).

Line, category and project discounts, each with its pre-discount value, discount, post-discount value, reason, actor,
authority and approval. A discount never touches a rate or a line amount: it is allocated beside them, pro rata to
the lines' remaining value (largest remainder, to the paisa), and only APPROVED discounts count.

The authority model is the owner's (OI-MTQ-06). While it is not recorded every discount action is refused
(OWNER_DECISION_REQUIRED). Once recorded: a proposer may apply up to ``self_limit_bp`` of the subtotal (cumulative) on
their own authority (WITHIN_LIMIT); above it, up to ``max_bp``, a discount waits for an approver holding
``cost_estimate.discount.approve`` who is not its proposer (APPROVER); above ``max_bp`` nothing is accepted.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error
from veda.modules.estimator import engine

from . import policy
from .models import CostEstimate, CostEstimateAdjustment, CostEstimateLine

LIVE = ("PROPOSED", "APPROVED")


def policy_view() -> dict[str, Any]:
    d = policy.decision("OI-MTQ-06")
    if d is None:
        return {"enabled": False, "decision": "OI-MTQ-06", "message": "Discount authority is not decided (OI-MTQ-06); "
                "discount actions are disabled."}  # fmt: skip
    return {"enabled": True, "decision": "OI-MTQ-06", "self_limit_bp": d.self_limit_bp, "max_bp": d.max_bp,
            "four_eyes": d.four_eyes, "policy_version": policy.current().version}  # fmt: skip


def _require_policy():
    d = policy.decision("OI-MTQ-06")
    if d is None:
        raise ApiError(409, "OWNER_DECISION_REQUIRED", "Discounts are disabled: the discount authority (OI-MTQ-06) "
                       "is not decided.", extra={"decision": "OI-MTQ-06"})  # fmt: skip
    return d


def _targets(rows: list[CostEstimateLine], scope_code: str, line_id: str | None, category: str | None):
    eligible = [x for x in rows if not x.is_optional and x.rate_status == "PRICED"]
    if scope_code == "LINE":
        return [x for x in eligible if x.id == line_id]
    if scope_code == "CATEGORY":
        return [x for x in eligible if x.category_code == category]
    return eligible


def _spread(total: int, targets: list[CostEstimateLine], remaining: dict[str, int]) -> dict[str, int]:
    """Largest-remainder allocation of ``total`` paise, pro rata to each target's remaining value."""
    pool = sum(remaining[x.id] for x in targets)
    if pool <= 0 or total <= 0:
        return {}
    shares = {x.id: Decimal(total) * remaining[x.id] / pool for x in targets}
    out = {k: int(v) for k, v in shares.items()}
    left = total - sum(out.values())
    for k in sorted(shares, key=lambda k: (shares[k] - out[k], k), reverse=True)[:left]:
        out[k] += 1
    return {k: min(v, remaining[k]) for k, v in out.items()}


def allocate(est: CostEstimate, rows: list[CostEstimateLine], approved: list[CostEstimateAdjustment]) -> None:
    remaining = {x.id: int(x.amount_minor or 0) for x in rows}
    for x in rows:
        x.discount_minor = 0
    for adj in approved:
        targets = _targets(rows, adj.scope_code, adj.target_line_id, adj.target_category)
        for line_id, amount in _spread(adj.discount_minor, targets, remaining).items():
            remaining[line_id] -= amount
            next(x for x in rows if x.id == line_id).discount_minor += amount


def propose(s: Session, ctx, est: CostEstimate, body) -> CostEstimateAdjustment:
    from . import estimates

    if est.status != "DRAFT":
        raise ApiError(409, "ESTIMATE_FROZEN", "Discounts change only on a draft estimate.")
    d = _require_policy()
    rows = estimates.lines(s, est)
    live = [a for a in estimates.adjustments(s, est) if a.status in LIVE]
    remaining = {x.id: int(x.amount_minor or 0) for x in rows}
    for a in live:  # value already promised to earlier discounts is not discounted twice
        for line_id, amount in _spread(a.discount_minor, _targets(rows, a.scope_code, a.target_line_id,
                                                                   a.target_category), remaining).items():  # fmt: skip
            remaining[line_id] -= amount
    targets = _targets(rows, body.scope_code, body.target_line_id, body.target_category)
    if not targets:
        raise ApiError(422, "VALIDATION_FAILED", "Nothing priced and included matches this discount's target.",
                       errors=[field_error("scope_code", "NO_TARGET", "No priced included line.")])  # fmt: skip
    base = sum(remaining[x.id] for x in targets)
    if body.kind_code == "PERCENT":
        discount = engine.paise(Decimal(base) * Decimal(body.value_bp) / Decimal(10_000))
    else:
        discount = int(body.amount_minor)
    if discount <= 0 or discount > base:
        raise ApiError(422, "VALIDATION_FAILED", "A discount is more than nothing and at most its target's value.",
                       errors=[field_error("amount_minor", "OUT_OF_RANGE", "Between 1 paisa and the target value.")])  # fmt: skip
    subtotal = est.subtotal_minor or 1
    total_bp = (sum(a.discount_minor for a in live) + discount) * 10_000 / subtotal
    if total_bp > d.max_bp:
        raise ApiError(422, "DISCOUNT_LIMIT_EXCEEDED", f"Discounts would reach {total_bp / 100:.2f} % of the subtotal; "
                       f"the maximum is {d.max_bp / 100:.2f} %.", extra={"max_bp": d.max_bp})  # fmt: skip
    within = total_bp <= d.self_limit_bp
    now = db.tx_time(s)
    adj = CostEstimateAdjustment(
        estimate_id=est.id, scope_code=body.scope_code, target_line_id=body.target_line_id,
        target_category=body.target_category, kind_code=body.kind_code, value_bp=body.value_bp,
        amount_minor=body.amount_minor, base_minor=base, discount_minor=discount, post_minor=base - discount,
        reason=body.reason, status="APPROVED" if within else "PROPOSED",
        authority_code="WITHIN_LIMIT" if within else None, policy_version=policy.current().version,
        decided_by=ctx.user.id if within else None, decided_on=now if within else None,
        decision_note="Within the proposer's own authority" if within else None,
    )  # fmt: skip
    s.add(adj)
    s.flush()
    estimates.recompute(s, est)
    return adj


def decide(s: Session, ctx, est: CostEstimate, adj: CostEstimateAdjustment, body) -> CostEstimateAdjustment:
    from . import estimates

    d = _require_policy()
    if est.status != "DRAFT" or adj.status != "PROPOSED":
        raise ApiError(409, "INVALID_STATE", "Only a proposed discount on a draft estimate is decided.")
    if d.four_eyes and adj.created_by == ctx.user.id:
        raise ApiError(409, "FOUR_EYES_REQUIRED", "A discount is approved by someone other than its proposer.")
    adj.status = "APPROVED" if body.decision == "APPROVE" else "REJECTED"
    adj.authority_code = "APPROVER" if body.decision == "APPROVE" else None
    adj.decided_by, adj.decided_on, adj.decision_note = ctx.user.id, db.tx_time(s), body.note
    s.flush()
    estimates.recompute(s, est)
    return adj


def withdraw(s: Session, ctx, est: CostEstimate, adj: CostEstimateAdjustment) -> CostEstimateAdjustment:
    from . import estimates

    if est.status != "DRAFT" or adj.status not in LIVE:
        raise ApiError(409, "INVALID_STATE", "Only a live discount on a draft estimate is withdrawn.")
    adj.status, adj.decided_by, adj.decided_on = "WITHDRAWN", ctx.user.id, db.tx_time(s)
    s.flush()
    estimates.recompute(s, est)
    return adj


def present(a: CostEstimateAdjustment) -> dict[str, Any]:
    return {
        "id": a.id, "version": a.version, "estimate_id": a.estimate_id, "scope_code": a.scope_code,
        "target_line_id": a.target_line_id, "target_category": a.target_category, "kind_code": a.kind_code,
        "value_bp": a.value_bp, "amount_minor": a.amount_minor, "base_minor": a.base_minor,
        "discount_minor": a.discount_minor, "post_minor": a.post_minor, "reason": a.reason, "status": a.status,
        "authority_code": a.authority_code, "policy_version": a.policy_version, "proposed_by": a.created_by,
        "proposed_on": clock.to_rfc3339(a.created_on), "decided_by": a.decided_by,
        "decided_on": clock.to_rfc3339(a.decided_on) if a.decided_on else None, "decision_note": a.decision_note,
    }  # fmt: skip
