"""Pricing and package presentation (CQX-05): the frozen amounts, arranged for a customer; nothing recomputed.

Every amount is the frozen document's own text (project total, room subtotals, line and optional amounts, GST when the
owner decided it, the approved discount shown on the document). Milestone amounts are the frozen document's own: since
template 3 the B4 freeze splits the frozen total by the approved shares (whole paise, the leftover paise to the largest
remainders, earlier milestone first), so they always add up to the total (``customer_pack.milestone_amounts``); a
document issued before has none, and the page shows the shares only. No unit rates unless OI-MTQ-10 allows them (they
are then already in the frozen lines).

Packages: the version's package is named only by its approved customer specification. A comparison lists only other
packages that were issued for the same property **and shared with the same recipient kind** (each customer link opens
one version; staff decide what a customer compares). Premium or Luxury therefore never appear unless an approved,
issued quotation for them exists, which itself needs approved rate cards (OI-MTQ-05). Comparison rows carry the
reference, package name and frozen total only; never a link, token or identifier.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation

from . import projection, references
from . import vocab as V
from .models import ProposalAccessGrant


def _package(s: Session, q: Quotation) -> str | None:
    spec = references.pinned_spec(s, q)
    return spec.name if spec is not None else None


def alternatives(s: Session, g: ProposalAccessGrant, q: Quotation) -> list[dict[str, Any]]:
    """Other issued, current base quotations of the property, shared (live link) with the same recipient kind."""
    if q.quotation_kind != "BASE":
        return []
    shared = s.execute(
        sa.select(ProposalAccessGrant.quotation_id).where(
            ProposalAccessGrant.property_id == q.property_id, ProposalAccessGrant.recipient_kind == g.recipient_kind,
            ProposalAccessGrant.status.in_(V.LIVE_GRANT_STATUSES), ProposalAccessGrant.expires_on > db.tx_time(s),
            ProposalAccessGrant.quotation_number != q.quotation_number,
        )
    ).scalars().all()  # fmt: skip
    out: list[dict[str, Any]] = []
    if not shared:
        return out
    for other in s.execute(sa.select(Quotation).where(Quotation.id.in_(shared))).scalars():
        if other.status != "ISSUED" or other.quotation_kind != "BASE":
            continue
        if quotations.latest(s, other.quotation_number, 0).id != other.id:
            continue
        try:
            doc = projection.frozen_document(other)
        except Exception:  # an unverifiable document is never compared
            continue
        out.append({"reference": doc.get("reference"), "package": _package(s, other),
                    "total": (doc.get("summary") or {}).get("total"), "valid_until": doc.get("valid_until")})  # fmt: skip
    return out


def contribute(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> None:
    p = page["proposal"]
    s_ = p["summary"]
    today = db.tx_time(s).date()
    days_left = None
    if p.get("valid_until") and page["state"] == "OPEN":
        from datetime import date

        days_left = (date.fromisoformat(p["valid_until"]) - today).days
    page["pricing"] = {
        "currency": s_.get("currency"),
        "total": s_.get("total"),
        "gst": s_.get("gst"),
        "discount": s_.get("discount"),
        "base_total": s_.get("base_total"),
        "optional_total": s_.get("optional_total"),
        "rooms": [{"ref": r["ref"], "title": r["title"], "subtotal": r["subtotal"]} for r in p["rooms"]],
        "milestones": p["payment_schedule"],
        "valid_until": p.get("valid_until"),
        "days_left": days_left,
        "unit_rates_shown": p["unit_rates_shown"],
        "package": _package(s, q),
        "alternatives": alternatives(s, g, q),
    }


PAGE_FIELDS: dict[str, str] = {
    "pricing.currency": "currency",
    "pricing.total": "frozen total",
    "pricing.gst.status": "GST status",
    "pricing.gst.amount": "GST amount when decided",
    "pricing.discount": "approved discount on the document",
    "pricing.base_total": "total of works",
    "pricing.optional_total": "optional items if all chosen",
    "pricing.rooms[].ref": "room reference",
    "pricing.rooms[].title": "room",
    "pricing.rooms[].subtotal": "frozen subtotal",
    "pricing.milestones[].label": "milestone",
    "pricing.milestones[].share": "approved share",
    "pricing.milestones[].trigger": "approved trigger",
    "pricing.milestones[].amount": "frozen milestone amount (reconciles exactly with the frozen total)",
    "pricing.valid_until": "validity end",
    "pricing.days_left": "days of validity left (live)",
    "pricing.unit_rates_shown": "OI-MTQ-10",
    "pricing.package": "package name from the approved specification",
    "pricing.alternatives[].reference": "another shared package's reference",
    "pricing.alternatives[].package": "its package name",
    "pricing.alternatives[].total": "its frozen total",
    "pricing.alternatives[].valid_until": "its validity",
}
