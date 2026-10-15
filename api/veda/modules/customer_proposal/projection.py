"""The customer-safe proposal projection (CQX-02).

Built from the **frozen** customer document of an issued version (``quotation.snapshot``), after its digests verify
(``rendering.integrity``); a mismatch refuses to render anything (SNAPSHOT_INTEGRITY_FAILED, a safe message). Nothing is
re-derived from live estimate, BOQ, rate-card or policy rows: the B4 document model is already an allow-list of
customer fields, and this projection is a second allow-list over it.

The only live rows read are the version's own ``quotation_line`` rows, never edited after issue, to give each frozen
line a customer-facing reference (``L<position>``: not a database identifier) and to pair optional lines with their
room. Pairing is checked line by line against the frozen text; any disagreement is treated as tampering and refused.

Every key the projection can emit is classified in ``FIELDS`` and every key the frozen document can hold is classified
in ``DOCUMENT_FIELDS`` (projected or excluded): a new field in either fails ``test_cqx_projection`` until it is
classified here. Excluded on purpose: the customer's name (link-forwarding risk: a proposal opens for whoever holds the
link), internal draft notes, and anything the B4 document never carries (rates unless OI-MTQ-10 allows them, margins,
cost, supplier prices, formulas, staff notes, rate-card digests, lineage, approval thresholds, discount authority).
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq_commercial import quotations, rendering
from veda.modules.mtq_commercial.models import Quotation, QuotationLine

SCHEMA = "veda.customer-proposal/1"

# --- classification inventory -----------------------------------------------------------------------------------------
# Projection key paths ("[]" marks a list element). Every emitted path must be listed; each is customer-safe by review.
FIELDS: dict[str, str] = {
    "schema": "projection schema version",
    "kind": "QUOTATION or VARIATION",
    "title": "document title",
    "brand.name": "Veda Spaces brand",
    "brand.tagline": "brand tagline",
    "reference": "quotation number and version label",
    "quotation_number": "the customer's quotation number",
    "version_no": "version shown",
    "variation_no": "0 for the quotation, n for variation n",
    "issued_on": "issue date",
    "valid_until": "validity end date (OI-MTQ-08)",
    "subject": "project summary line",
    "cover_note": "staff's customer-facing cover note",
    "property.reference": "property display reference (not an address)",
    "property.configuration": "e.g. 3 BHK apartment",
    "property.city": "city",
    "snapshot_sha256": "digest of the frozen document the customer is looking at (binds acknowledgements and acceptance)",
    "rooms[].ref": "room reference (R<n>, not an identifier)",
    "rooms[].title": "room or section title",
    "rooms[].kind": "ROOM, PROJECT or CHANGES",
    "rooms[].subtotal": "approved room subtotal",
    "rooms[].included_count": "number of included lines in the room",
    "rooms[].optional_count": "number of optional items offered for the room",
    "rooms[].lines[].ref": "line reference (L<n>, not an identifier)",
    "rooms[].lines[].description": "item name",
    "rooms[].lines[].detail": "customer-friendly detail (finish, room)",
    "rooms[].lines[].quantity": "quantity and unit, where shown",
    "rooms[].lines[].amount": "approved line amount",
    "rooms[].lines[].priced": "whether the line has an approved price",
    "rooms[].lines[].status": "Included, Mandatory or Optional",
    "rooms[].lines[].unit_rate": "unit rate, only when OI-MTQ-10 allows it",
    "rooms[].lines[].change": "variation change type",
    "rooms[].lines[].delta": "variation price change",
    "optional_items[].ref": "line reference",
    "optional_items[].description": "item name",
    "optional_items[].detail": "detail",
    "optional_items[].quantity": "quantity",
    "optional_items[].amount": "approved optional amount",
    "optional_items[].priced": "whether priced",
    "optional_items[].status": "Optional",
    "optional_items[].unit_rate": "unit rate, only when OI-MTQ-10 allows it",
    "optional_items[].price_with_gst": "what choosing the item adds including GST, frozen at issue",
    "optional_items[].room_ref": "the room it belongs to (R<n>), when it is in one",
    "optional_items[].room_title": "that room's title",
    "summary.base_total": "total of works",
    "summary.discount": "approved discount shown on the document",
    "summary.taxable": "amount after discount",
    "summary.gst.status": "Included or To be confirmed (OI-MTQ-07)",
    "summary.gst.amount": "GST amount when decided",
    "summary.total": "total",
    "summary.optional_total": "total of optional items, if all chosen",
    "summary.net_change": "a variation's net change",
    "summary.currency": "currency",
    "payment_schedule[].label": "milestone (OI-MTQ-09)",
    "payment_schedule[].share": "milestone share",
    "payment_schedule[].trigger": "milestone trigger",
    "warranty[]": "warranty text as approved (OI-MTQ-09)",
    "service_support[]": "Veda Spaces service-support text as approved (OI-MTQ-09), distinct from warranty",
    "assumptions[]": "assumptions",
    "exclusions[]": "exclusions",
    "terms[]": "terms (change-order, cancellation, general)",
    "terms_version": "terms version",
    "unit_rates_shown": "whether unit rates appear (OI-MTQ-10)",
    "sections.SCOPE": "digest of the scope as frozen (acknowledgement binding)",
    "sections.ASSUMPTIONS": "digest",
    "sections.EXCLUSIONS": "digest",
    "sections.PAYMENT_MILESTONES": "digest",
    "sections.WARRANTY": "digest",
    "sections.SERVICE_SUPPORT": "digest",
    "sections.TERMS": "digest",
    "sections.VALIDITY": "digest",
    # CQX customer completeness (OI-MTQ-18, template 3): verified dimensions, milestone amounts, customer information
    **{
        f"{where}.dimensions[].{k}": what
        for where in ("rooms[].lines[]", "optional_items[]")
        for k, what in (
            ("label", "dimension name (Width, Height, Total run, Area…)"),
            ("value", "verified value and unit"),
        )
    },
    **{
        f"{where}.dimension_status": "CONFIRMED or TO_BE_CONFIRMED (an assumed or missing size is never shown)"
        for where in ("rooms[].lines[]", "optional_items[]")
    },
    "payment_schedule[].amount": "milestone amount from the frozen total and the approved share (reconciles exactly)",
    "information.content_version": "customer information pack version (OI-MTQ-18), frozen at issue",
    **{
        f"information.contacts.{who}.{k}": f"Veda Spaces business contact ({who}): {k.replace('_', ' ')}"
        for who in ("quotation", "support[]", "service[]")
        for k in ("display_name", "role", "phone", "email", "hours", "channel_note")
    },
    "information.support_escalation": "approved support escalation route",
    **{
        f"information.{sec}[].{k}": f"approved {sec.replace('_', ' ')}: {k}"
        for sec, keys in (
            ("project_inclusions", ("code", "text")),
            ("warranty_exclusions", ("code", "text")),
            ("client_responsibilities", ("code", "category", "text", "status")),
            ("site_readiness", ("code", "category", "text", "status")),
            ("handover", ("code", "category", "text")),
            ("care", ("code", "category", "text")),
            ("next_steps", ("code", "stage", "label", "text", "duration")),
        )
        for k in keys
    },
    "information.site_dependent_work.intro": "approved site-dependent-work explanation",
    "information.site_dependent_work.approval_rule": "approved rule: priced and agreed as a variation first",
    **{
        f"information.site_dependent_work.categories[].{k}": "approved site-dependent work category"
        for k in ("code", "category", "text")
    },
    "information.manufacturer_warranty_note": "approved note on manufacturer-backed warranty",
    **{
        f"information.service_guidance.contact.{k}": f"service contact: {k.replace('_', ' ')}"
        for k in ("display_name", "role", "phone", "email", "hours", "channel_note")
    },
    "information.service_guidance.what_to_provide[]": "what to include in a service request",
    "information.service_guidance.reference_process": "how a service request is referenced",
    "information.service_guidance.escalation": "service escalation route",
    "information.payment_safety": "approved statement of the payment channels Veda Spaces recognises (no account details)",
}

# Every key of the frozen B4 document (rendering.document_model + rendering.freeze): PROJECTED or EXCLUDED, with why.
DOCUMENT_FIELDS: dict[str, str] = {
    "document_version": "EXCLUDED: internal format marker",
    "brand": "PROJECTED",
    "title": "PROJECTED",
    "quotation_number": "PROJECTED",
    "reference": "PROJECTED",
    "version_no": "PROJECTED",
    "variation_no": "PROJECTED",
    "date": "PROJECTED as issued_on",
    "valid_until": "PROJECTED",
    "subject": "PROJECTED",
    "cover_note": "PROJECTED",
    "property": "PROJECTED (reference, configuration, city)",
    "sections": "PROJECTED as rooms",
    "optional_items": "PROJECTED",
    "summary": "PROJECTED",
    "payment_schedule": "PROJECTED",
    "warranty": "PROJECTED",
    "service_support": "PROJECTED",
    "assumptions": "PROJECTED",
    "exclusions": "PROJECTED",
    "terms": "PROJECTED",
    "terms_version": "PROJECTED",
    "customer_information": "PROJECTED as information (OI-MTQ-18 approved copy; contacts are business channels)",
    "customer": "EXCLUDED: the customer's name (a proposal opens for whoever holds the link)",
    "draft": "EXCLUDED: staff-only draft notes and blockers (never in a frozen document)",
}
LINE_FIELDS: dict[str, str] = {
    "description": "PROJECTED",
    "detail": "PROJECTED",
    "quantity": "PROJECTED",
    "amount": "PROJECTED",
    "priced": "PROJECTED",
    "status": "PROJECTED",
    "unit_rate": "PROJECTED (present only when OI-MTQ-10 allows)",
    "change": "PROJECTED",
    "delta": "PROJECTED",
    "price_with_gst": "PROJECTED (optional items only: what choosing it adds, frozen at issue)",
    "dimensions": "PROJECTED (verified sizes only)",
    "dimension_status": "PROJECTED",
}
SUMMARY_FIELDS = ("base_total", "discount", "taxable", "gst", "total", "optional_total", "currency", "net_change")
ROOM_KINDS = {"Space": "ROOM", "Project": "PROJECT", "Variation": "CHANGES"}


def integrity_refused() -> ApiError:
    return ApiError(409, "SNAPSHOT_INTEGRITY_FAILED", "This proposal cannot be shown right now. Please contact your "
                    "Veda Spaces representative.")  # fmt: skip


def frozen_document(q: Quotation) -> dict[str, Any]:
    """The verified frozen document of an issued version, or a refusal (never a re-render)."""
    if q.snapshot is None or not rendering.integrity(q):
        from veda.kernel import metrics

        metrics.emit("ProposalIntegrityRefused", 1)
        raise integrity_refused()
    return q.snapshot


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _line(x: dict[str, Any], ref: str) -> dict[str, Any]:
    out = {"ref": ref, **{k: x[k] for k in ("description", "detail", "quantity", "amount", "priced", "status")}}
    for k in ("unit_rate", "change", "delta", "price_with_gst", "dimensions", "dimension_status"):
        if k in x:
            out[k] = x[k]
    return out


def _pair(s: Session, q: Quotation, doc: dict[str, Any]) -> tuple[list[tuple[Any, list[QuotationLine]]],
                                                                  list[QuotationLine]]:  # fmt: skip
    """The version's own lines in frozen-document order: (DB section, its printed lines) per printed section, and the
    printed optional lines. Refuses if anything disagrees with the frozen text (tampered rows or document)."""
    rows = [x for x in quotations.lines(s, q) if not (x.quantity_centi == 0 and not x.amount_minor)]
    secs = [sec for sec in quotations.sections(s, q) if sec.section_code != "OPTIONAL"]
    printed = doc.get("sections") or []
    if len(secs) != len(printed):
        raise integrity_refused()
    pairs = []
    for sec, frozen in zip(secs, printed, strict=True):
        mine = [x for x in rows if x.section_id == sec.id]
        if sec.title != frozen.get("title") or len(mine) != len(frozen.get("lines") or []):
            raise integrity_refused()
        for x, f in zip(mine, frozen["lines"], strict=True):
            if x.description != f.get("description"):
                raise integrity_refused()
        pairs.append((sec, mine))
    optional = [x for x in rows if x.is_optional]
    frozen_optional = doc.get("optional_items") or []
    if len(optional) != len(frozen_optional) or any(
        x.description != f.get("description") for x, f in zip(optional, frozen_optional, strict=True)
    ):
        raise integrity_refused()
    return pairs, optional


def printed(s: Session, q: Quotation) -> tuple[dict[str, QuotationLine], dict[str, QuotationLine]]:
    """The lines the customer can see in ``q``'s verified frozen document, by reference: (every printed line, the
    printed optional lines). A line the document omits (a zero line) or that another version holds is never in either,
    so a customer can never choose, ask about or accept it (CQX N3)."""
    doc = frozen_document(q) if q.snapshot is not None else None
    if doc is None:
        return {}, {}
    pairs, optional = _pair(s, q, doc)
    shown = {f"L{x.position}": x for _sec, mine in pairs for x in mine}
    opt = {f"L{x.position}": x for x in optional}
    return {**shown, **opt}, opt


def _minor(text: str | None) -> int | None:
    from decimal import Decimal

    return None if text is None else int(Decimal(text.replace(",", "")) * 100)


def frozen_values(s: Session, q: Quotation) -> dict[str, Any]:
    """The acceptance-relevant amounts exactly as frozen: the document's total and each printed optional item's price
    including GST. The live rows are cross-checked against them; any disagreement is tampering and refuses (CQX N1)."""
    doc = frozen_document(q)
    shown, optional = printed(s, q)
    frozen_opt = {f"L{x.position}": f for x, f in zip(optional.values(), doc.get("optional_items") or [], strict=True)}
    total = _minor((doc.get("summary") or {}).get("total"))
    if total is None or q.total_minor != total:
        _tampered()
    printed_lines = {f"L{x.position}": f for (_sec, mine), sec in zip(_pair(s, q, doc)[0], doc.get("sections") or [],
                                                                      strict=True)
                     for x, f in zip(mine, sec["lines"], strict=True)}  # fmt: skip
    printed_lines |= frozen_opt
    for ref, x in shown.items():
        f = printed_lines[ref]
        if (f.get("amount") if f.get("priced") else None) != (_money(x.amount_minor) if x.is_priced else None):
            _tampered()
    values: dict[str, int] = {}
    for ref, f in frozen_opt.items():
        x = optional[ref]
        if f.get("price_with_gst") is None:
            continue
        frozen = _minor(f["price_with_gst"])
        live = int(x.amount_minor or 0) - int(x.discount_minor or 0) + int(x.tax_minor or 0)
        if frozen != live:
            _tampered()
        values[ref] = int(frozen or 0)
    return {"total_minor": total, "optional_minor": values}


def _money(minor: int | None) -> str | None:
    from decimal import Decimal

    return None if minor is None else f"{Decimal(minor) / 100:,.2f}"


def integrity_refused_now() -> None:
    _tampered()


def _tampered() -> None:
    from veda.kernel import metrics

    metrics.emit("ProposalIntegrityRefused", 1)
    raise integrity_refused()


def refs(s: Session, q: Quotation) -> dict[str, QuotationLine]:
    """Customer line reference → the version's quotation line (for choices, questions and acceptance)."""
    return {f"L{x.position}": x for x in quotations.lines(s, q)}


def section_digests(doc: dict[str, Any], rooms: list[dict[str, Any]]) -> dict[str, str | None]:
    """A digest per acknowledgeable section, over exactly what the customer is shown (None: nothing approved to show)."""

    def d(value: Any) -> str | None:
        return digest(value) if value else None

    return {
        "SCOPE": digest(
            {
                "rooms": [
                    {"title": r["title"], "lines": [(x["description"], x["quantity"], x["amount"]) for x in r["lines"]]}
                    for r in rooms
                ]
            }
        ),  # fmt: skip
        "ASSUMPTIONS": d(doc.get("assumptions")),
        "EXCLUSIONS": d(doc.get("exclusions")),
        "PAYMENT_MILESTONES": d(doc.get("payment_schedule")),
        "WARRANTY": d(doc.get("warranty")),
        "SERVICE_SUPPORT": d(doc.get("service_support")),
        "TERMS": d([*(doc.get("terms") or []), doc.get("terms_version")] if doc.get("terms") else None),
        "VALIDITY": d({"issued_on": doc.get("date"), "valid_until": doc.get("valid_until")})
        if doc.get("valid_until")
        else None,
    }


def build(s: Session, q: Quotation, doc: dict[str, Any] | None = None) -> dict[str, Any]:
    """The projection of ``q``: from its verified frozen document, or (staff preview of a draft) the given live one."""
    doc = frozen_document(q) if doc is None else doc
    pairs, optional = _pair(s, q, doc)
    rooms: list[dict[str, Any]] = []
    room_of_space: dict[str, dict[str, Any]] = {}
    for n, ((sec, mine), frozen) in enumerate(zip(pairs, doc.get("sections") or [], strict=True), start=1):
        room = {"ref": f"R{n}", "title": frozen["title"], "kind": ROOM_KINDS.get(frozen.get("kind"), "PROJECT"),
                "subtotal": frozen.get("subtotal"),
                "lines": [_line(f, f"L{x.position}") for x, f in zip(mine, frozen["lines"], strict=True)]}  # fmt: skip
        rooms.append(room)
        if sec.space_id:
            room_of_space[sec.space_id] = room
    optional_items = []
    for x, f in zip(optional, doc.get("optional_items") or [], strict=True):
        item = _line(f, f"L{x.position}")
        home = room_of_space.get(x.space_id or "")
        item["room_ref"], item["room_title"] = (home["ref"], home["title"]) if home else (None, None)
        optional_items.append(item)
    for room in rooms:  # room-card counts (CQX-03), from the frozen lines only
        room["included_count"] = sum(1 for x in room["lines"] if x["status"] != "Optional")
        room["optional_count"] = sum(1 for x in optional_items if x["room_ref"] == room["ref"])
    summary = {k: v for k, v in (doc.get("summary") or {}).items() if k in SUMMARY_FIELDS}
    if "gst" in summary:
        summary["gst"] = {"status": summary["gst"].get("status"), "amount": summary["gst"].get("amount")}
    unit_rates = any("unit_rate" in x for r in rooms for x in r["lines"]) or any(
        "unit_rate" in x for x in optional_items
    )
    return {
        "schema": SCHEMA,
        "kind": "VARIATION" if q.quotation_kind == "VARIATION" else "QUOTATION",
        "title": doc.get("title"),
        "brand": {"name": (doc.get("brand") or {}).get("name"), "tagline": (doc.get("brand") or {}).get("tagline")},
        "reference": doc.get("reference"),
        "quotation_number": doc.get("quotation_number"),
        "version_no": doc.get("version_no"),
        "variation_no": doc.get("variation_no"),
        "issued_on": doc.get("date"),
        "valid_until": doc.get("valid_until"),
        "subject": doc.get("subject"),
        "cover_note": doc.get("cover_note"),
        "property": {k: (doc.get("property") or {}).get(k) for k in ("reference", "configuration", "city")},
        "snapshot_sha256": q.snapshot_sha256,
        "rooms": rooms,
        "optional_items": optional_items,
        "summary": summary,
        "payment_schedule": [{k: m.get(k) for k in ("label", "share", "trigger", "amount")}
                             for m in doc.get("payment_schedule") or []],
        "warranty": list(doc.get("warranty") or []),
        "service_support": list(doc.get("service_support") or []),
        "assumptions": list(doc.get("assumptions") or []),
        "exclusions": list(doc.get("exclusions") or []),
        "terms": list(doc.get("terms") or []),
        "terms_version": doc.get("terms_version"),
        "unit_rates_shown": unit_rates,
        "sections": section_digests(doc, rooms),
        "information": information(doc),
    }  # fmt: skip


_CONTACT = ("display_name", "role", "phone", "email", "hours", "channel_note")


def information(doc: dict[str, Any]) -> dict[str, Any]:
    """The frozen customer information block, allow-listed again key by key. A document issued before template 3 has
    none: every section is then None (shown "to be confirmed"), never filled from the current pack."""
    from veda.modules.mtq_commercial import customer_pack

    info = doc.get("customer_information") or customer_pack.information(None, None)

    def contact(c: dict[str, Any] | None) -> dict[str, Any] | None:
        return {k: c.get(k) for k in _CONTACT} if c else None

    def rows(key: str, keys: tuple[str, ...]) -> list[dict[str, Any]] | None:
        found = info.get(key)
        return [{k: r.get(k) for k in keys} for r in found] if found else None

    contacts = info.get("contacts") or {}
    sdw, sg = info.get("site_dependent_work"), info.get("service_guidance")
    return {
        "content_version": info.get("content_version"),
        "contacts": {
            "quotation": contact(contacts.get("quotation")),
            "support": [contact(c) for c in contacts.get("support") or []],
            "service": [contact(c) for c in contacts.get("service") or []],
        },  # fmt: skip
        "support_escalation": info.get("support_escalation"),
        "project_inclusions": rows("project_inclusions", ("code", "text")),
        "client_responsibilities": rows("client_responsibilities", ("code", "category", "text", "status")),
        "site_readiness": rows("site_readiness", ("code", "category", "text", "status")),
        "site_dependent_work": {
            "intro": sdw.get("intro"),
            "approval_rule": sdw.get("approval_rule"),
            "categories": [{k: c.get(k) for k in ("code", "category", "text")} for c in sdw.get("categories") or []],
        }
        if sdw
        else None,  # fmt: skip
        "manufacturer_warranty_note": info.get("manufacturer_warranty_note"),
        "warranty_exclusions": rows("warranty_exclusions", ("code", "text")),
        "service_guidance": {
            "contact": contact(sg.get("contact")),
            "what_to_provide": list(sg.get("what_to_provide") or []),
            "reference_process": sg.get("reference_process"),
            "escalation": sg.get("escalation"),
        }
        if sg
        else None,  # fmt: skip
        "handover": rows("handover", ("code", "category", "text")),
        "care": rows("care", ("code", "category", "text")),
        "next_steps": rows("next_steps", ("code", "stage", "label", "text", "duration")),
        "payment_safety": info.get("payment_safety"),
    }


def paths(value: Any, prefix: str = "") -> set[str]:
    """Every key path of a projection, lists marked ``[]`` (the classification test walks this)."""
    out: set[str] = set()
    if isinstance(value, dict):
        for k, v in value.items():
            p = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)) and v:
                out |= paths(v, p)
            else:
                out.add(p)
    elif isinstance(value, list):
        for v in value:
            if isinstance(v, (dict, list)):
                out |= paths(v, prefix + "[]")
            else:
                out.add(prefix + "[]")
    return out
