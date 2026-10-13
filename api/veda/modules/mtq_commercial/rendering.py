"""The customer quotation document (instruction B4.2, B4.7; blueprint §10.1).

``document_model`` builds the customer-facing model: brand, quotation number and version, date, validity, the property
reference, room-wise sections, optional items, totals (GST only when decided), payment milestones, warranty,
assumptions, exclusions and terms. It is built from an allow-list of customer fields, so internal costing never
reaches it: no rate card, tier rate path, unit rate (unless the owner's OI-MTQ-10 decision says so), derivation,
override, discount authority, approver, threshold, margin or staff name.

For an issued version the model is frozen in ``quotation.snapshot`` with its digest and is the only thing rendered.
A draft renders live, marked as a draft that is not a customer document, with what still blocks issuance. The
customer's name is not stored in the snapshot (no personal data in the frozen document); it is added when rendered.
``html`` renders the model as one self-contained, print-ready page (the basis for a later PDF export).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from veda.modules.mtq.models import Property

from . import quotations

DOCUMENT_VERSION = "mtq-quotation-document/1"
UNIT = {"SFT": "sq ft", "RFT": "running ft", "NOS": "nos", "LUMP": "lump sum"}
BRAND = {"name": "Veda Spaces", "tagline": "Interiors, measured and made"}


def _amount(minor: int | None) -> str | None:
    if minor is None:
        return None
    rupees = Decimal(minor) / 100
    return f"{rupees:,.2f}"


def _qty(centi: int | None, uom: str | None) -> str | None:
    if centi is None or uom in (None, "LUMP"):
        return None
    q = (Decimal(centi) / 100).normalize()
    return f"{q:f} {UNIT.get(uom, '')}".strip()


def document_model(s: Session, q: quotations.Quotation, *, frozen: bool = False) -> dict[str, Any]:
    prop = s.get(Property, q.property_id)
    assert prop is not None
    terms = q.terms or {}
    show_rates = bool(terms.get("show_unit_rates"))
    secs = quotations.sections(s, q)
    rows = quotations.lines(s, q)
    beds = int(prop.derived_bedroom_count or 0)
    kind = "Independent house" if prop.property_type_code == "INDEPENDENT_HOUSE" else "Apartment"

    def line(x) -> dict[str, Any]:
        out = {"description": x.description, "detail": x.detail, "quantity": _qty(x.quantity_centi, x.uom_code),
               "amount": _amount(x.amount_minor) if x.is_priced else None, "priced": x.is_priced,
               "status": "Optional" if x.is_optional else ("Mandatory" if x.is_mandatory else "Included")}  # fmt: skip
        if show_rates and x.is_priced and x.rate_minor is not None and x.uom_code != "LUMP":
            out["unit_rate"] = f"{_amount(x.rate_minor)} per {UNIT.get(x.uom_code or '', '')}"
        if q.quotation_kind == "VARIATION":
            out["change"] = x.change_code.replace("_", " ").title()
            out["delta"] = _amount(x.delta_amount_minor)
        return out

    sections = []
    for sec in secs:
        if sec.section_code == "OPTIONAL":
            continue
        sections.append({"title": sec.title, "kind": sec.section_code.title(),
                         "lines": [line(x) for x in rows if x.section_id == sec.id],
                         "subtotal": _amount(sec.subtotal_minor)})  # fmt: skip
    optional = [line(x) for x in rows if x.is_optional]
    gst = (
        {"status": "Included", "amount": _amount(q.tax_minor)}
        if q.tax_status == "APPLIED"
        else {"status": "To be confirmed", "amount": None}
    )
    doc: dict[str, Any] = {
        "document_version": DOCUMENT_VERSION,
        "brand": BRAND,
        "title": "Variation (change order)" if q.quotation_kind == "VARIATION" else "Quotation",
        "quotation_number": q.quotation_number,
        "reference": quotations.number_label(q),
        "version_no": q.version_no,
        "variation_no": q.variation_no,
        "date": (q.issued_on or q.created_on).date().isoformat(),
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "subject": q.title,
        "cover_note": q.cover_note,
        "property": {
            "reference": prop.property_number,
            "configuration": f"{beds} BHK {kind.lower()}",
            "city": prop.city,
        },  # fmt: skip
        "sections": sections,
        "optional_items": optional,
        "summary": {
            "base_total": _amount(q.base_total_minor),
            "discount": _amount(q.discount_minor) if q.discount_minor else None,
            "taxable": _amount(q.taxable_minor),
            "gst": gst,
            "total": _amount(q.total_minor),
            "optional_total": _amount(q.optional_minor) if q.optional_minor else None,
            "currency": q.currency,
        },
        "payment_schedule": [
            {"label": m["label"], "share": f"{Decimal(m['share_bp']) / 100:g}%", "trigger": m["trigger"]}
            for m in terms.get("payment_milestones") or []
        ],
        "warranty": terms.get("warranty") or [],
        "assumptions": terms.get("assumptions") or [],
        "exclusions": terms.get("exclusions") or [],
        "terms": [
            t
            for t in [
                terms.get("change_order_terms"),
                terms.get("cancellation_terms"),
                *(terms.get("general_terms") or []),
            ]
            if t
        ],  # fmt: skip
        "terms_version": terms.get("terms_version"),
    }
    if q.quotation_kind == "VARIATION":
        doc["summary"]["net_change"] = _amount(q.base_total_minor)
    if not frozen:
        doc["draft"] = {"watermark": "DRAFT — not a customer document", "status": q.status,
                        "customer_issuable": not (q.blockers or []),
                        "blockers": [b.get("message", b["code"]) for b in (q.blockers or [])]}  # fmt: skip
    return doc
