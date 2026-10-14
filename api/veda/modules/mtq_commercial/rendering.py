"""The customer quotation document (instruction B4.2, B4.7; blueprint §10.1).

``document_model`` builds the customer-facing model: brand, quotation number and version, date, validity, the property
reference, room-wise sections, optional items, totals (GST only when decided), payment milestones, warranty,
assumptions, exclusions and terms. It is built from an allow-list of customer fields, so internal costing never
reaches it: no rate card, tier rate path, unit rate (unless the owner's OI-MTQ-10 decision says so), derivation,
override, discount authority, approver, threshold, margin or staff name.

**Issued versions are reproducible.** At ISSUE the model (with the customer's name as issued) is frozen in
``quotation.snapshot`` and its HTML, rendered by the template version in force, in ``quotation.issued_html``, each with
its digest, and the template version is pinned. An issued version is only ever served from those frozen bytes, never
re-rendered with the current template; if either digest does not match, it is refused (SNAPSHOT_INTEGRITY_FAILED) and
nothing is rendered. Templates are versioned (``TEMPLATES``): a change to the page is a new version, and earlier ones
stay available for redaction. The only change ever made to a frozen document is lead erasure (``redact``), which
replaces the customer-identifying fields, re-renders with the pinned template, re-seals both digests and records a
SNAPSHOT_REDACTED event with the previous digests.

A draft renders live with the current template, marked as a draft that is not a customer document, with what still
blocks issuance. ``html`` renders the model as one self-contained, print-ready page (the basis for a later PDF
export).
"""

from __future__ import annotations

import hashlib
import html as _html
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.crm.leads.models import Lead
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
    # a zero-quantity line (e.g. no new light points) stays in the BOQ, estimate and quotation for the audit trail;
    # the customer document does not print it
    rows = [x for x in quotations.lines(s, q) if not (x.quantity_centi == 0 and not x.amount_minor)]
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
        "service_support": terms.get("service_support") or [],
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


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def freeze(s: Session, q: quotations.Quotation) -> None:
    """The issued document: model (with the customer's name as issued) and HTML from the current template, sealed."""
    doc = document_model(s, q, frozen=True)
    lead = s.get(Lead, q.lead_id)
    doc["customer"] = {"name": lead.name if lead else None}
    page = TEMPLATES[CURRENT_TEMPLATE](doc)
    q.snapshot, q.snapshot_sha256 = doc, hashlib.sha256(canonical_bytes(doc)).hexdigest()
    q.template_version, q.issued_html, q.issued_html_sha256 = CURRENT_TEMPLATE, page, _sha(page)


def integrity(q: quotations.Quotation) -> bool:
    return (
        q.snapshot is not None
        and q.issued_html is not None
        and hashlib.sha256(canonical_bytes(q.snapshot)).hexdigest() == q.snapshot_sha256
        and _sha(q.issued_html) == q.issued_html_sha256
        and q.template_version in TEMPLATES
    )


def rendered(s: Session, q: quotations.Quotation) -> dict[str, Any]:
    """An issued version: exactly its frozen document and HTML, after verifying both digests (fail closed). A draft:
    the live model with the current template, the customer's name added for staff."""
    if q.snapshot is not None or q.issued_html is not None:
        if not integrity(q):
            raise ApiError(409, "SNAPSHOT_INTEGRITY_FAILED", f"The frozen document of {quotations.number_label(q)} "
                           "does not match its sealed digest; it is not rendered.",
                           extra={"quotation_id": q.id})  # fmt: skip
        return {"document": q.snapshot, "html": q.issued_html, "template_version": q.template_version,
                "snapshot_verified": True, "generated_on": clock.to_rfc3339(q.issued_on or clock.now())}  # fmt: skip
    quotations.refresh_blockers(s, q)
    doc = document_model(s, q)
    lead = s.get(Lead, q.lead_id)
    doc["customer"] = {"name": lead.name if lead else None}
    return {"document": doc, "html": TEMPLATES[CURRENT_TEMPLATE](doc), "template_version": CURRENT_TEMPLATE,
            "snapshot_verified": None, "generated_on": clock.to_rfc3339(clock.now())}  # fmt: skip


REDACTED = "[erased]"


def redact(s: Session, q: quotations.Quotation) -> bool:
    """Lead erasure: replace the customer-identifying fields of a frozen document (customer name, subject, cover
    note), re-render with the pinned template, re-seal, and record the previous digests. Amounts, lines, terms, the
    property reference and the quotation number stay (commercial record).

    Only a verified document is re-sealed. A document that already fails its digests is still redacted (erasure is
    never refused) but is not re-sealed: its personal fields are replaced, its HTML is withdrawn and its original
    digests are kept, so it stays SNAPSHOT_INTEGRITY_FAILED and erasure never turns a tampered document into a
    verified one. The event records INTEGRITY_FAILED_BEFORE_REDACTION for the incident."""
    if q.snapshot is None:
        return False
    current = q.snapshot
    if (
        current.get("subject") == REDACTED
        and current.get("cover_note") in (None, REDACTED)
        and ((current.get("customer") or {}).get("name") in (None, REDACTED))
    ):
        return False  # already redacted
    before = (q.snapshot_sha256, q.issued_html_sha256)
    verified = integrity(q)
    doc = dict(q.snapshot)
    doc["customer"] = {"name": REDACTED if (doc.get("customer") or {}).get("name") else None}
    doc["subject"] = REDACTED
    if doc.get("cover_note"):
        doc["cover_note"] = REDACTED
    if not verified:
        q.snapshot, q.issued_html = doc, None  # digests untouched: the document stays refused
        quotations.event(s, q, "SNAPSHOT_REDACTED", q.status, q.status, reason_code="LEAD_ERASURE",
                         integrity="INTEGRITY_FAILED_BEFORE_REDACTION", resealed=False,
                         previous_snapshot_sha256=before[0], previous_html_sha256=before[1])  # fmt: skip
        return True
    render = TEMPLATES.get(q.template_version or "")
    if render is None:
        raise RuntimeError(f"template {q.template_version} of {q.id} is no longer available; keep every version")
    page = render(doc)
    q.snapshot, q.snapshot_sha256 = doc, hashlib.sha256(canonical_bytes(doc)).hexdigest()
    q.issued_html, q.issued_html_sha256 = page, _sha(page)
    quotations.event(s, q, "SNAPSHOT_REDACTED", q.status, q.status, reason_code="LEAD_ERASURE",
                     integrity="VERIFIED_BEFORE_REDACTION", resealed=True, previous_snapshot_sha256=before[0],
                     previous_html_sha256=before[1], snapshot_sha256=q.snapshot_sha256)  # fmt: skip
    return True


def _e(value: Any) -> str:
    return _html.escape("" if value is None else str(value))


CSS = """
:root{--ink:#1f1b16;--muted:#6b6259;--line:#e6dfd6;--accent:#8a5a2b;--bg:#fffdf9}
body{font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:var(--bg);margin:0;padding:32px;line-height:1.45}
header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid var(--accent);padding-bottom:12px}
.brand{font-size:28px;letter-spacing:.04em;color:var(--accent)}.brand small{display:block;font-size:12px;color:var(--muted)}
h1{font-size:20px;margin:0}.meta{text-align:right;font-size:13px;color:var(--muted)}
h2{font-size:16px;margin:28px 0 8px;color:var(--accent)}table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
td.num,th.num{text-align:right;white-space:nowrap}.sub td{font-weight:bold}.muted{color:var(--muted)}
.tag{font-size:11px;padding:1px 6px;border:1px solid var(--line);border-radius:8px}
.summary td{font-size:14px}.total td{font-size:16px;font-weight:bold;border-top:2px solid var(--ink)}
.draft{border:2px dashed #b3261e;color:#b3261e;padding:8px 12px;margin:16px 0;font-family:sans-serif}
ul{margin:4px 0 0 18px;padding:0;font-size:13px}@media print{body{padding:0}.draft{display:block}}
"""


def html(doc: dict[str, Any]) -> str:
    """A self-contained HTML rendering of the document model (every value escaped)."""
    rate_col = any("unit_rate" in x for sec in doc["sections"] for x in sec["lines"])
    var = doc.get("variation_no", 0) > 0
    p: list[str] = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
                    f"<title>{_e(doc['title'])} {_e(doc['reference'])}</title><style>{CSS}</style></head><body>"]  # fmt: skip
    p.append(f"<header><div class='brand'>{_e(doc['brand']['name'])}<small>{_e(doc['brand']['tagline'])}</small></div>"
             f"<div class='meta'><h1>{_e(doc['title'])}</h1>{_e(doc['reference'])}<br>Date {_e(doc['date'])}"
             + (f"<br>Valid until {_e(doc['valid_until'])}" if doc.get("valid_until") else "")
             + "</div></header>")  # fmt: skip
    if doc.get("draft"):
        d = doc["draft"]
        items = "".join(f"<li>{_e(b)}</li>" for b in d["blockers"])
        p.append(f"<div class='draft' role='note'><strong>{_e(d['watermark'])}</strong>"
                 + (f"<ul>{items}</ul>" if items else "") + "</div>")  # fmt: skip
    cust = (doc.get("customer") or {}).get("name")
    prop = doc["property"]
    p.append(f"<p>{_e('For ' + cust) if cust else ''}<br><span class='muted'>Property {_e(prop['reference'])} · "
             f"{_e(prop['configuration'])}{(' · ' + _e(prop['city'])) if prop.get('city') else ''}</span></p>")  # fmt: skip
    p.append(f"<p><strong>{_e(doc['subject'])}</strong></p>")
    if doc.get("cover_note"):
        p.append(f"<p>{_e(doc['cover_note'])}</p>")

    def table(lines: list[dict], subtotal: str | None) -> str:
        head = "<tr><th>Item</th><th>Quantity</th>" + ("<th class='num'>Rate</th>" if rate_col else "")
        head += (
            "<th>Change</th><th class='num'>Change value</th>" if var else ""
        ) + "<th class='num'>Amount (INR)</th></tr>"
        body = []
        for x in lines:
            detail = f"<br><span class='muted'>{_e(x['detail'])}</span>" if x.get("detail") else ""
            amount = _e(x["amount"]) if x["priced"] else "<span class='muted'>to be confirmed</span>"
            body.append(f"<tr><td>{_e(x['description'])}{detail} <span class='tag'>{_e(x['status'])}</span></td>"
                        f"<td>{_e(x['quantity'] or '—')}</td>"
                        + (f"<td class='num'>{_e(x.get('unit_rate', ''))}</td>" if rate_col else "")
                        + (f"<td>{_e(x.get('change'))}</td><td class='num'>{_e(x.get('delta'))}</td>" if var else "")
                        + f"<td class='num'>{amount}</td></tr>")  # fmt: skip
        if subtotal is not None:
            span = 2 + int(rate_col) + 2 * int(var)
            body.append(f"<tr class='sub'><td colspan='{span}'>Subtotal</td><td class='num'>{_e(subtotal)}</td></tr>")
        return f"<table><thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"

    for sec in doc["sections"]:
        p.append(f"<h2>{_e(sec['title'])}</h2>" + table(sec["lines"], sec.get("subtotal")))
    if doc["optional_items"]:
        p.append("<h2>Optional items</h2><p class='muted'>Not included in the total unless you choose them.</p>"
                 + table(doc["optional_items"], None))  # fmt: skip
    s = doc["summary"]
    rows = [("Total before discount" if s.get("discount") else "Total of works", s["base_total"])]
    if s.get("discount"):
        rows += [("Discount", f"− {s['discount']}"), ("Amount after discount", s["taxable"])]
    rows.append(("GST", s["gst"]["amount"] if s["gst"]["amount"] else s["gst"]["status"]))
    p.append("<h2>Summary</h2><table class='summary'>" + "".join(
        f"<tr><td>{_e(k)}</td><td class='num'>{_e(v)}</td></tr>" for k, v in rows)
             + f"<tr class='total'><td>Total</td><td class='num'>{_e(s['total'] or 'to be confirmed')}</td></tr>"
             + (f"<tr><td class='muted'>Optional items (if chosen)</td><td class='num muted'>{_e(s['optional_total'])}</td></tr>"
                if s.get("optional_total") else "") + "</table>")  # fmt: skip
    for title, key in (("Payment schedule", "payment_schedule"), ("Warranty", "warranty"),
                       ("Assumptions", "assumptions"), ("Exclusions", "exclusions"), ("Terms", "terms")):  # fmt: skip
        entries: list[Any] = doc.get(key) or []
        if not entries:
            continue
        if key == "payment_schedule":
            lis = "".join(f"<li>{_e(m['label'])} — {_e(m['share'])}: {_e(m['trigger'])}</li>" for m in entries)
        else:
            lis = "".join(f"<li>{_e(t)}</li>" for t in entries)
        p.append(f"<h2>{_e(title)}</h2><ul>{lis}</ul>")
    if doc.get("terms_version"):
        p.append(f"<p class='muted'>Terms version {_e(doc['terms_version'])}</p>")
    p.append("</body></html>")
    return "".join(p)


def html_v2(doc: dict[str, Any]) -> str:
    """Version 2 (CQX-09): version 1 plus Veda Spaces' service support as its own section after the warranty, so the
    warranty text and the service commitment are never presented as one."""
    page = html({k: v for k, v in doc.items() if k != "service_support"})
    support = doc.get("service_support") or []
    if not support:
        return page
    block = "<h2>Service support (Veda Spaces)</h2><ul>" + "".join(f"<li>{_e(t)}</li>" for t in support) + "</ul>"
    # The warranty list is the only "<h2>Warranty</h2><ul>" (a room titled Warranty is followed by a <table>).
    start = page.find("<h2>Warranty</h2><ul>")
    at = page.find("</ul>", start) + len("</ul>") if start >= 0 else page.rfind("</body>")
    return page[:at] + block + page[at:]


# Every template version ever used for an issued quotation stays here (a new page design is a new key).
TEMPLATES: dict[str, Callable[[dict[str, Any]], str]] = {"mtq-quotation-html/1": html, "mtq-quotation-html/2": html_v2}
CURRENT_TEMPLATE = "mtq-quotation-html/2"
