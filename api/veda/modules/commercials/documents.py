"""Invoice and receipt documents (PCM-012, PCM-013): built from the position, frozen at issue, served only from the
frozen bytes.

A document's model is an allow-list of customer fields taken from authoritative records: the payment (amount, date,
method, reference, customer note), the instalment, the position (value, paid, outstanding) and the accepted
quotation's references. No staff note, actor identity, estimate figure or internal state reaches it. At issue the model
(with the customer's name as it stood) and its HTML are stored with their SHA-256 digests; a document is only ever
served from those bytes, after both digests verify (``verified``; a mismatch refuses with DOCUMENT_INTEGRITY_FAILED).
The only change ever made to a frozen document is lead erasure (``redact``): the customer's name, the payment
reference and the notes are replaced, the HTML re-rendered, both digests re-sealed, and the previous digests recorded
in a DOCUMENT_REDACTED event. Amounts, numbers and dates stay (the commercial record).
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq.models import Property
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial import rendering as qr
from veda.modules.mtq_commercial.models import Quotation

from . import baseline, events, position
from . import vocab as V
from .money import text

RECEIPT_VERSION = "pcm-receipt/1"
INVOICE_VERSION = "pcm-invoice/1"
REDACTED = "[erased]"
NOT_A_GATEWAY = ("Veda Spaces does not collect payments through this document or the project portal. A payment is "
                 "recorded by Veda Spaces once it has been received.")  # fmt: skip


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _common(s: Session, account, pos: position.Position) -> dict[str, Any]:
    lead = s.get(Lead, account.lead_id)
    prop = s.get(Property, account.property_id)
    base = s.get(Quotation, account.base_quotation_id)
    assert prop is not None and base is not None
    beds = int(prop.derived_bedroom_count or 0)
    kind = "independent house" if prop.property_type_code == "INDEPENDENT_HOUSE" else "apartment"
    variations = [quotations.number_label(q) for q in baseline.accepted_chain(s, account.quotation_number)
                  if q.variation_no > 0]  # fmt: skip
    info = (base.snapshot or {}).get("customer_information") or {}
    return {
        "brand": qr.BRAND,
        "customer": {"name": lead.name if lead else None},
        "property": {"reference": prop.property_number, "configuration": f"{beds} BHK {kind}", "city": prop.city},
        "quotation": {
            "reference": quotations.number_label(base),
            "quotation_number": base.quotation_number,
            "variations": variations,
        },  # fmt: skip
        "currency": account.currency,
        "position": {
            "value": text(pos.value_minor),
            "paid": text(pos.paid_minor),
            "outstanding": text(pos.outstanding_minor),
            "credit": text(pos.credit_minor) if pos.credit_minor else None,
        },  # fmt: skip
        "payment_safety": info.get("payment_safety"),
        "statement": NOT_A_GATEWAY,
    }


def receipt_model(s: Session, account, payment, number: str, before: position.Position,
                  after: position.Position, issued_on) -> dict[str, Any]:  # fmt: skip
    applied_before = {x.instalment.id: x.applied_minor for x in before.lines}
    applied = [{"label": x.instalment.label, "amount": text(x.applied_minor - applied_before.get(x.instalment.id, 0))}
               for x in after.lines if x.applied_minor - applied_before.get(x.instalment.id, 0) > 0]  # fmt: skip
    doc = {
        "document_version": RECEIPT_VERSION, "kind": "RECEIPT", "title": "Payment receipt", "number": number,
        "date": issued_on.date().isoformat(),
        **_common(s, account, after),
        "payment": {"amount": text(payment.amount_minor), "received_on": payment.received_on.isoformat(),
                    "method": V.METHOD_LABELS[payment.method_code], "reference": payment.external_reference,
                    "note": payment.customer_note},  # fmt: skip
        "applied_to": applied,
    }  # fmt: skip
    doc["statement"] = (f"Veda Spaces recorded this payment as received on {payment.received_on.isoformat()}. "
                        + NOT_A_GATEWAY)  # fmt: skip
    return doc


def invoice_model(s: Session, account, invoice, line: position.Line, pos: position.Position, particulars,
                  number: str | None, issued_on) -> dict[str, Any]:  # fmt: skip
    inst = line.instalment
    of = len(pos.lines)
    doc = {
        "document_version": INVOICE_VERSION, "kind": "INVOICE",
        "title": particulars.document_title if particulars else "Invoice", "number": number,
        "date": issued_on.date().isoformat() if issued_on else None,
        "due_on": invoice.due_on.isoformat() if invoice.due_on else None,
        "issuer": ({"legal_name": particulars.legal_name, "address_lines": list(particulars.address_lines),
                    "gstin": particulars.gstin, "sac_code": particulars.sac_code, "footer": list(particulars.footer)}
                   if particulars else None),  # fmt: skip
        **_common(s, account, pos),
        "instalment": {"label": inst.label, "when": inst.when_text, "position": inst.position, "of": of},
        "amounts": {"instalment": text(inst.amount_minor), "gst_included": text(inst.tax_minor),
                    "paid_towards": text(line.applied_minor), "due": text(line.remaining_minor)},  # fmt: skip
        "note": invoice.customer_note,
    }  # fmt: skip
    return doc


# --- HTML ---------------------------------------------------------------------------------------------------------------
_e = qr._e
CSS = qr.CSS + ".amount{font-size:22px;font-weight:bold}.box{border:1px solid var(--line);padding:12px;margin:12px 0}"


def html(doc: dict[str, Any]) -> str:
    """A self-contained, print-ready page of the frozen model (every value escaped)."""
    p = ["<!doctype html><html lang='en'><head><meta charset='utf-8'>",
         f"<title>{_e(doc['title'])} {_e(doc.get('number') or 'draft')}</title><style>{CSS}</style></head><body>"]  # fmt: skip
    meta = f"<h1>{_e(doc['title'])}</h1>{_e(doc.get('number') or 'Draft: not issued')}"
    if doc.get("date"):
        meta += f"<br>Date {_e(doc['date'])}"
    if doc.get("due_on"):
        meta += f"<br>Due by {_e(doc['due_on'])}"
    p.append(f"<header><div class='brand'>{_e(doc['brand']['name'])}<small>{_e(doc['brand']['tagline'])}</small></div>"
             f"<div class='meta'>{meta}</div></header>")  # fmt: skip
    issuer = doc.get("issuer")
    if issuer:
        lines = "<br>".join(_e(x) for x in [issuer["legal_name"], *issuer["address_lines"]])
        extra = "".join(f"<br>{label} {_e(issuer[k])}" for k, label in (("gstin", "GSTIN"), ("sac_code", "SAC"))
                        if issuer.get(k))  # fmt: skip
        p.append(f"<p class='muted'>{lines}{extra}</p>")
    cust, prop, quote = (doc.get("customer") or {}).get("name"), doc["property"], doc["quotation"]
    p.append(f"<p>{_e('For ' + cust) if cust else ''}<br><span class='muted'>Property {_e(prop['reference'])} · "
             f"{_e(prop['configuration'])}{(' · ' + _e(prop['city'])) if prop.get('city') else ''}<br>"
             f"Quotation {_e(quote['reference'])}"
             + (f"; variations {_e(', '.join(quote['variations']))}" if quote.get("variations") else "")
             + "</span></p>")  # fmt: skip
    if doc["kind"] == "RECEIPT":
        pay = doc["payment"]
        p.append(f"<div class='box'><p class='amount'>INR {_e(pay['amount'])}</p><p>Received on {_e(pay['received_on'])}"
                 f" by {_e(pay['method'])}" + (f" (reference {_e(pay['reference'])})" if pay.get("reference") else "")
                 + "</p>" + (f"<p>{_e(pay['note'])}</p>" if pay.get("note") else "") + "</div>")  # fmt: skip
        if doc.get("applied_to"):
            p.append("<h2>Applied to</h2><table>" + "".join(
                f"<tr><td>{_e(a['label'])}</td><td class='num'>{_e(a['amount'])}</td></tr>" for a in doc["applied_to"])
                     + "</table>")  # fmt: skip
    else:
        inst, am = doc["instalment"], doc["amounts"]
        p.append(f"<h2>{_e(inst['label'])} (instalment {inst['position']} of {inst['of']})</h2>"
                 f"<p class='muted'>{_e(inst['when'])}</p><table class='summary'>"
                 f"<tr><td>Instalment</td><td class='num'>{_e(am['instalment'])}</td></tr>"
                 + (f"<tr><td class='muted'>Of which GST (as quoted)</td><td class='num muted'>{_e(am['gst_included'])}</td></tr>"
                    if am.get("gst_included") else "")
                 + f"<tr><td>Paid towards this instalment</td><td class='num'>{_e(am['paid_towards'])}</td></tr>"
                 f"<tr class='total'><td>Amount due (INR)</td><td class='num'>{_e(am['due'])}</td></tr></table>")  # fmt: skip
        if doc.get("note"):
            p.append(f"<p>{_e(doc['note'])}</p>")
    pos = doc["position"]
    p.append("<h2>Your project account</h2><table class='summary'>"
             f"<tr><td>Project value</td><td class='num'>{_e(pos['value'])}</td></tr>"
             f"<tr><td>Paid</td><td class='num'>{_e(pos['paid'])}</td></tr>"
             f"<tr class='total'><td>Outstanding (INR)</td><td class='num'>{_e(pos['outstanding'])}</td></tr></table>")  # fmt: skip
    if doc.get("payment_safety"):
        p.append(f"<div class='box'>{_e(doc['payment_safety'])}</div>")
    p.append(f"<p class='muted'>{_e(doc['statement'])}</p>")
    for line in (issuer or {}).get("footer") or []:
        p.append(f"<p class='muted'>{_e(line)}</p>")
    p.append("</body></html>")
    return "".join(p)


# --- sealing ------------------------------------------------------------------------------------------------------------
def seal(row, doc: dict[str, Any]) -> None:
    page = html(doc)
    row.snapshot, row.snapshot_sha256 = doc, hashlib.sha256(canonical_bytes(doc)).hexdigest()
    row.document_html, row.document_sha256 = page, _sha(page)


def integrity(row) -> bool:
    return (row.snapshot is not None and row.document_html is not None
            and hashlib.sha256(canonical_bytes(row.snapshot)).hexdigest() == row.snapshot_sha256
            and _sha(row.document_html) == row.document_sha256)  # fmt: skip


def verified(row, label: str) -> dict[str, Any]:
    if not integrity(row):
        raise ApiError(409, "DOCUMENT_INTEGRITY_FAILED", f"The frozen {label} does not match its sealed digest; it is "
                       "not shown.", extra={"id": row.id})  # fmt: skip
    return row.snapshot


def redact(s: Session, account, row) -> bool:
    """Lead erasure: replace the personal fields of a frozen document, re-render, re-seal (only a verified one) and
    record the previous digests."""
    if row.snapshot is None:
        return False
    before = (row.snapshot_sha256, row.document_sha256)
    was_verified = integrity(row)
    doc = dict(row.snapshot)
    doc["customer"] = {"name": REDACTED if (doc.get("customer") or {}).get("name") else None}
    if doc.get("note"):
        doc["note"] = REDACTED
    if doc.get("payment"):
        doc["payment"] = {**doc["payment"], "reference": REDACTED if doc["payment"].get("reference") else None,
                          "note": REDACTED if doc["payment"].get("note") else None}  # fmt: skip
    if doc == row.snapshot:
        return False
    if was_verified:
        seal(row, doc)
    else:
        row.snapshot, row.document_html = doc, None  # digests untouched: the document stays refused
    events.record(s, account, "DOCUMENT_REDACTED", row.id, reason_code="LEAD_ERASURE", resealed=was_verified,
                  previous_snapshot_sha256=before[0], previous_document_sha256=before[1])  # fmt: skip
    return True
