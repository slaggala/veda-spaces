"""The customer quotation document (instruction B4.2, B4.7; blueprint §10.1).

``document_model`` builds the customer-facing model: brand, quotation number and version, date, validity, the property
reference, room-wise sections (each line with its verified dimensions), optional items, totals (GST only when decided),
payment milestones (with their amounts from the frozen total), warranty, assumptions, exclusions, terms, and the
customer information pack (OI-MTQ-18: contacts, responsibilities, site readiness, site-dependent work, warranty
exclusions, service guidance, handover, care, next steps, payment safety; each section absent until the owner records
it). It is built from an allow-list of customer fields, so internal costing never
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

from . import customer_pack, quotations

# 2: lines carry dimensions, milestones their amounts, and the document the customer information block (template 3).
DOCUMENT_VERSION = "mtq-quotation-document/2"
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
    inputs_of = _formula_inputs(s, rows)

    def line(x) -> dict[str, Any]:
        out = {"description": x.description, "detail": x.detail, "quantity": _qty(x.quantity_centi, x.uom_code),
               "amount": _amount(x.amount_minor) if x.is_priced else None, "priced": x.is_priced,
               "status": "Optional" if x.is_optional else ("Mandatory" if x.is_mandatory else "Included")}  # fmt: skip
        if show_rates and x.is_priced and x.rate_minor is not None and x.uom_code != "LUMP":
            out["unit_rate"] = f"{_amount(x.rate_minor)} per {UNIT.get(x.uom_code or '', '')}"
        if q.quotation_kind == "VARIATION":
            out["change"] = x.change_code.replace("_", " ").title()
            out["delta"] = _amount(x.delta_amount_minor)
        dims, dim_status = customer_pack.dimensions(inputs_of.get(x.id))
        if dim_status is not None:
            out["dimensions"], out["dimension_status"] = dims, dim_status
        if x.is_optional and x.is_priced and q.tax_status == "APPLIED":
            # What choosing this item adds, as the B4 decision adds it (taxable amount plus its GST), frozen with the
            # document so a customer's acceptance total never depends on mutable line rows (CQX N1).
            out["price_with_gst"] = _amount(
                int(x.amount_minor or 0) - int(x.discount_minor or 0) + int(x.tax_minor or 0)
            )
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
        "payment_schedule": _schedule(q, terms),
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
        "customer_information": customer_pack.information(terms.get("customer_pack"), q.customer_inputs),
    }
    if q.quotation_kind == "VARIATION":
        doc["summary"]["net_change"] = _amount(q.base_total_minor)
    if not frozen:
        doc["draft"] = {"watermark": "DRAFT — not a customer document", "status": q.status,
                        "customer_issuable": not (q.blockers or []),
                        "blockers": [b.get("message", b["code"]) for b in (q.blockers or [])]}  # fmt: skip
    return doc


def _formula_inputs(s: Session, rows: list) -> dict[str, dict]:
    """Quotation line id → its BOQ line's resolved inputs (estimate line → BOQ line), for the line's dimensions."""
    import sqlalchemy as sa

    from .models import BoqLine, CostEstimateLine

    ids = [x.cost_estimate_line_id for x in rows if x.cost_estimate_line_id]
    if not ids:
        return {}
    boq_of = dict(s.execute(sa.select(CostEstimateLine.id, CostEstimateLine.boq_line_id)
                            .where(CostEstimateLine.id.in_(ids))).all())  # fmt: skip
    boq_ids = [b for b in boq_of.values() if b]
    inputs = (
        dict(s.execute(sa.select(BoqLine.id, BoqLine.formula_inputs).where(BoqLine.id.in_(boq_ids))).all())
        if boq_ids
        else {}
    )
    return {x.id: inputs.get(boq_of.get(x.cost_estimate_line_id)) for x in rows if x.cost_estimate_line_id}


def _schedule(q: quotations.Quotation, terms: dict[str, Any]) -> list[dict[str, Any]]:
    """The approved milestones with their amounts: the frozen total split by the approved shares, reconciling exactly
    (customer_pack.milestone_amounts). A variation's schedule is its base quotation's; it carries no amounts here."""
    milestones = terms.get("payment_milestones") or []
    amounts = None
    if q.quotation_kind != "VARIATION":
        amounts = customer_pack.milestone_amounts(q.total_minor, [int(m["share_bp"]) for m in milestones])
    return [
        {"label": m["label"], "share": f"{Decimal(m['share_bp']) / 100:g}%", "trigger": m["trigger"],
         "amount": customer_pack.money(amounts[i]) if amounts else None}
        for i, m in enumerate(milestones)
    ]  # fmt: skip


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


TBC = "To be confirmed by Veda Spaces."
STATUS_TEXT = {"REQUIRED": "Required", "NOT_REQUIRED": "Not required", "TO_BE_CONFIRMED": "To be confirmed",
               "READY": "Ready", "NOT_READY": "Not ready", "CUSTOMER_ACTION_REQUIRED": "Your action needed",
               "NOT_APPLICABLE": "Not applicable"}  # fmt: skip


def _dims_text(x: dict[str, Any]) -> str | None:
    if "dimension_status" not in x:
        return None
    sizes = " · ".join(f"{d['label']} {d['value']}" for d in x.get("dimensions") or [])
    if x["dimension_status"] == "CONFIRMED":
        return sizes
    return f"{sizes} · dimension to be confirmed" if sizes else "Dimension to be confirmed"


def _contact_html(c: dict[str, Any] | None) -> str:
    if not c:
        return "<p class='muted'>Contact details to be confirmed.</p>"
    parts = [f"<strong>{_e(c['display_name'])}</strong>, {_e(c['role'])}"]
    parts += [_e(v) for v in (c.get("phone"), c.get("email"), c.get("hours")) if v]
    return (
        "<p>"
        + "<br>".join(parts)
        + (f"<br><span class='muted'>{_e(c['channel_note'])}</span>" if c.get("channel_note") else "")
        + "</p>"
    )


def html_v3(doc: dict[str, Any]) -> str:
    """Version 3 (CQX customer completeness): version 2, with each line's verified dimensions under its detail, each
    milestone's amount, the Veda Spaces contact after the heading, and the customer information sections (what is
    included, what is not, what the customer arranges, site-dependent work, before we start, warranty exclusions,
    service, handover, care, what happens next, payment safety). A section the owner has not approved says so."""
    info = doc.get("customer_information") or {}
    base = {k: v for k, v in doc.items() if k != "customer_information"}

    def with_dims(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out = []
        for x in lines:
            extra = _dims_text(x)
            out.append({**x, "detail": " · ".join(t for t in (x.get("detail"), extra) if t) or None})
        return out

    base["sections"] = [{**sec, "lines": with_dims(sec["lines"])} for sec in doc["sections"]]
    base["optional_items"] = with_dims(doc["optional_items"])
    base["payment_schedule"] = [{**m, "trigger": f"{m['trigger']} ({m['amount']})" if m.get("amount") else m["trigger"]}
                                for m in doc.get("payment_schedule") or []]  # fmt: skip
    page = html_v2(base)
    contacts = info.get("contacts") or {}
    head = "<h2>Your Veda Spaces contact</h2>" + _contact_html(contacts.get("quotation"))
    at = page.find("</header>") + len("</header>")
    page = page[:at] + head + page[at:]

    def items(rows: list[dict[str, Any]] | None, status: bool = False) -> str:
        if not rows:
            return f"<p class='muted'>{_e(TBC)}</p>"
        return "<ul>" + "".join(f"<li>{_e(r['text'])}" + (f" <span class='tag'>{_e(STATUS_TEXT.get(r['status'], r['status']))}</span>"
                                                           if status else "") + "</li>" for r in rows) + "</ul>"  # fmt: skip

    blocks = ["<h2>What is included</h2>" + items(info.get("project_inclusions")),
              "<h2>What you arrange</h2>" + items(info.get("client_responsibilities"), status=True)]  # fmt: skip
    sdw = info.get("site_dependent_work")
    blocks.append("<h2>Site-dependent work</h2>" + (
        f"<p>{_e(sdw['intro'])}</p>" + items(sdw.get("categories") or None) + f"<p>{_e(sdw['approval_rule'])}</p>"
        if sdw else f"<p class='muted'>{_e(TBC)}</p>"))  # fmt: skip
    blocks.append("<h2>Before we start</h2>" + items(info.get("site_readiness"), status=True))
    note = info.get("manufacturer_warranty_note")
    blocks.append(
        "<h2>Manufacturer warranty</h2>" + (f"<p>{_e(note)}</p>" if note else f"<p class='muted'>{_e(TBC)}</p>")
    )
    blocks.append("<h2>What the warranty does not cover</h2>" + items(info.get("warranty_exclusions")))
    sg = info.get("service_guidance")
    if sg:
        body = _contact_html(sg.get("contact")) if sg.get("contact") else ""
        body += (
            ("<ul>" + "".join(f"<li>{_e(t)}</li>" for t in sg.get("what_to_provide") or []) + "</ul>")
            if sg.get("what_to_provide")
            else ""
        )
        body += "".join(f"<p>{_e(sg[k])}</p>" for k in ("reference_process", "escalation") if sg.get(k))
    else:
        body = f"<p class='muted'>{_e(TBC)}</p>"
    blocks.append("<h2>Need help after handover?</h2>" + body)
    blocks.append("<h2>Handover</h2>" + items(info.get("handover")))
    blocks.append("<h2>Care and maintenance</h2>" + items(info.get("care")))
    steps = info.get("next_steps")
    blocks.append("<h2>What happens after you accept</h2>" + (
        "<ol>" + "".join(f"<li><strong>{_e(x['label'])}</strong>: {_e(x['text'])}"
                         + (f" <span class='muted'>({_e(x['duration'])})</span>" if x.get("duration") else "") + "</li>"
                         for x in steps) + "</ol>" if steps else f"<p class='muted'>{_e(TBC)}</p>"))  # fmt: skip
    support = contacts.get("support") or []
    blocks.append("<h2>Support</h2>" + ("".join(_contact_html(c) for c in support) if support else f"<p class='muted'>{_e(TBC)}</p>")
                  + (f"<p>{_e(info['support_escalation'])}</p>" if info.get("support_escalation") else ""))  # fmt: skip
    blocks.append("<h2>Payments</h2>" + (f"<p>{_e(info['payment_safety'])}</p>" if info.get("payment_safety")
                                         else f"<p class='muted'>{_e(TBC)}</p>"))  # fmt: skip
    if info.get("content_version"):
        blocks.append(f"<p class='muted'>Customer information version {_e(info['content_version'])}</p>")
    end = page.rfind("</body>")
    return page[:end] + "".join(blocks) + page[end:]


# Every template version ever used for an issued quotation stays here (a new page design is a new key).
TEMPLATES: dict[str, Callable[[dict[str, Any]], str]] = {"mtq-quotation-html/1": html, "mtq-quotation-html/2": html_v2,
                                                         "mtq-quotation-html/3": html_v3}  # fmt: skip
CURRENT_TEMPLATE = "mtq-quotation-html/3"
