"""Variation preview and version comparison (CQX-08). Customer-safe, from frozen data only, using the B4 model.

**Variation preview.** A variation (B4 ``variations``) is priced as line deltas against the *effective accepted
baseline* frozen, with its digest, when the customer accepted (included lines plus the optional items they chose). The
preview sets that baseline beside the proposed variation: what is added, removed, or changes in quantity, material,
finish or price, each with its approved before and after amount and the delta, and the net impact. It also states the
cumulative position: the accepted value of the job so far (the base plus every accepted variation) and the value if this
variation is accepted. Nothing is recomputed: amounts are the variation's own lines (frozen at issue) and the baseline's
own entries (digest-verified; a mismatch refuses the preview). Optional items the customer already chose are listed as
kept: B4 compares by line key, so a chosen item still offered is never added a second time.

A variation is issued only when the owner's variation policy allows it (OI-MTQ-13, enforced by B4 issuance). Until
then the preview is staff-only (``/quotations/<id>/variation-preview``); a customer sees it only through a link to an
issued variation.

**Version comparison.** For a revised version, the customer can compare it with the version issued before it: lines
added, removed or changed (paired by their stable B4 line key), and both totals, each side from its own verified
frozen document.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq_commercial import quotations, variations
from veda.modules.mtq_commercial.models import Quotation, QuotationLine

from . import projection
from .selections import money

CHANGE_LABEL = {"ADD": "Added", "OMIT": "Removed", "CHANGE_QUANTITY": "Quantity changed",
                "CHANGE_MATERIAL": "Material changed", "CHANGE_FINISH": "Finish changed", "CHANGE_RATE": "Price changed"}  # fmt: skip
UNIT = {"SFT": "sq ft", "RFT": "running ft", "NOS": "nos"}


def _qty(centi: int | None, uom: str | None) -> str | None:
    if centi is None or uom in (None, "LUMP"):
        return None
    return f"{(Decimal(centi) / 100).normalize():f} {UNIT.get(uom, '')}".strip()


def _baseline(base: Quotation) -> dict[str, dict[str, Any]]:
    entries = base.accepted_baseline or []
    if base.accepted_baseline_sha256 != hashlib.sha256(canonical_bytes(entries)).hexdigest():
        raise ApiError(409, "SNAPSHOT_INTEGRITY_FAILED", "The accepted baseline does not match its digest; no "
                       "comparison is shown.")  # fmt: skip
    return {e["key"]: e for e in entries}


def variation_preview(s: Session, q: Quotation) -> dict[str, Any]:
    if q.quotation_kind != "VARIATION" or not q.baseline_quotation_id:
        raise ApiError(422, "NOT_A_VARIATION", "Only a variation has a baseline comparison.")
    base = s.get(Quotation, q.baseline_quotation_id)
    assert base is not None
    baseline = _baseline(base)
    if q.snapshot is not None:
        projection.frozen_document(q)  # an issued variation is compared only while its frozen document verifies
    changes = []
    for x in s.execute(sa.select(QuotationLine).where(QuotationLine.quotation_id == q.id)
                       .order_by(QuotationLine.position)).scalars():  # fmt: skip
        before = baseline.get(x.line_key)
        changes.append({
            "ref": f"L{x.position}", "description": x.description, "room": x.detail, "change": x.change_code,
            "change_label": CHANGE_LABEL.get(x.change_code, x.change_code.title()),
            "quantity_before": _qty(before["quantity_centi"], before["uom_code"]) if before else None,
            "quantity_after": None if x.change_code == "OMIT" else _qty(x.quantity_centi, x.uom_code),
            "amount_before": money(x.baseline_amount_minor) if x.baseline_amount_minor else None,
            "amount_after": money(x.amount_minor) if x.is_priced else None,
            "delta": money(x.delta_amount_minor), "priced": x.is_priced,
        })  # fmt: skip
    kept = [{"description": e["label"], "amount": money(e["taxable_minor"])}
            for e in baseline.values() if e.get("selected_optional")]  # fmt: skip
    accepted_value = variations.accepted_value(s, q.quotation_number)
    after = None if accepted_value is None or q.total_minor is None else accepted_value + q.total_minor
    return {
        "reference": quotations.number_label(q),
        "baseline_reference": quotations.number_label(base),
        "status": q.status,
        "changes": changes,
        "net_change": money(q.base_total_minor),
        "gst": {"status": "Included" if q.tax_status == "APPLIED" else "To be confirmed", "amount": money(q.tax_minor)},
        "net_change_with_gst": money(q.total_minor),
        "kept_choices": kept,
        "accepted_value": money(accepted_value),
        "value_if_accepted": money(after),
        "issuable": not (q.blockers or [])
        if q.status in ("DRAFT", "INTERNAL_REVIEW", "APPROVED")
        else q.snapshot is not None,
    }


def _issued_versions(s: Session, q: Quotation) -> list[Quotation]:
    return list(s.execute(
        sa.select(Quotation).where(Quotation.quotation_number == q.quotation_number,
                                   Quotation.variation_no == q.variation_no, Quotation.version_no < q.version_no,
                                   Quotation.issued_on.is_not(None)).order_by(Quotation.version_no.desc())
    ).scalars())  # fmt: skip


def _keyed(s: Session, q: Quotation) -> dict[str, dict[str, Any]]:
    """Each customer line of ``q``'s verified projection, by its stable B4 line key."""
    page = projection.build(s, q)
    printed = {x["ref"]: {**x, "room": r["title"]} for r in page["rooms"] for x in r["lines"]}
    printed |= {x["ref"]: {**x, "room": x.get("room_title")} for x in page["optional_items"]}
    refs = projection.refs(s, q)
    return {refs[ref].line_key: line for ref, line in printed.items() if ref in refs}


def version_comparison(s: Session, q: Quotation) -> dict[str, Any] | None:
    """The version issued before ``q`` beside ``q`` (None when ``q`` is the first)."""
    earlier = _issued_versions(s, q)
    if not earlier:
        return None
    prev = earlier[0]
    old, new = _keyed(s, prev), _keyed(s, q)
    rows = []
    for key, line in new.items():
        was = old.get(key)
        if was is None:
            rows.append({"change": "ADDED", "description": line["description"], "room": line["room"],
                         "before": None, "after": line["amount"], "status": line["status"]})  # fmt: skip
        elif (was["amount"], was["quantity"], was["status"]) != (line["amount"], line["quantity"], line["status"]):
            rows.append({"change": "CHANGED", "description": line["description"], "room": line["room"],
                         "before": was["amount"], "after": line["amount"], "quantity_before": was["quantity"],
                         "quantity_after": line["quantity"], "status": line["status"]})  # fmt: skip
    for key, was in old.items():
        if key not in new:
            rows.append({"change": "REMOVED", "description": was["description"], "room": was["room"],
                         "before": was["amount"], "after": None, "status": was["status"]})  # fmt: skip
    before_doc, after_doc = projection.frozen_document(prev), projection.frozen_document(q)
    return {"from_version": prev.version_no, "to_version": q.version_no, "changes": rows,
            "total_before": (before_doc.get("summary") or {}).get("total"),
            "total_after": (after_doc.get("summary") or {}).get("total")}  # fmt: skip


def contribute(s: Session, g, q: Quotation, page: dict[str, Any]) -> None:
    page["comparison_available"] = bool(_issued_versions(s, q))
    if q.quotation_kind == "VARIATION":
        page["variation"] = variation_preview(s, q)


_VARIATION_KEYS = ("reference", "baseline_reference", "status", "net_change", "gst.status", "gst.amount",
                   "net_change_with_gst", "accepted_value", "value_if_accepted", "issuable", "kept_choices[].description",
                   "kept_choices[].amount", *(f"changes[].{k}" for k in (
                       "ref", "description", "room", "change", "change_label", "quantity_before", "quantity_after",
                       "amount_before", "amount_after", "delta", "priced")))  # fmt: skip
PAGE_FIELDS: dict[str, str] = {
    "comparison_available": "an earlier issued version exists to compare with",
    **{f"variation.{k}": "variation against the accepted baseline (frozen data)" for k in _VARIATION_KEYS},
}
COMPARISON_FIELDS = ("from_version", "to_version", "total_before", "total_after", *(f"changes[].{k}" for k in (
    "change", "description", "room", "before", "after", "status", "quantity_before", "quantity_after")))  # fmt: skip
