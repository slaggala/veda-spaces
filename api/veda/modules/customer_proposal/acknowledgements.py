"""Terms and acknowledgements (CQX-09).

The customer-safe sections of a frozen version (scope, assumptions, exclusions, payment milestones, validity, warranty,
Veda Spaces service support, terms including change-order and cancellation treatment) are shown exactly as frozen.
A section with no approved content is shown as "to be confirmed by Veda Spaces", never filled in, and cannot be
acknowledged; client-supplied items have no approved content anywhere and are not presented.

An acknowledgement binds one recipient (their link) to one section of one version **by the section's digest as shown**:
the request carries the digest the page displayed, and a different digest (the document changed, or the customer is
looking at another version) is refused. It records the quotation version, the frozen-document digest, the time and an
evidence digest over all of it; repeating it is idempotent. Which sections must be acknowledged before acceptance is the
owner's decision CQX-D03; until it is recorded acknowledgements are optional and acceptance stays blocked (CQX-10).
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq_commercial.models import Quotation

from . import events, policy, projection
from .models import ProposalAccessGrant, QuotationAcknowledgement
from .selections import require_open

TITLES = {
    "SCOPE": "Scope of work", "ASSUMPTIONS": "Assumptions", "EXCLUSIONS": "Exclusions",
    "PAYMENT_MILESTONES": "Payment milestones", "VALIDITY": "Validity", "WARRANTY": "Warranty",
    "SERVICE_SUPPORT": "Service support (Veda Spaces)", "TERMS": "Terms, changes and cancellation",
}  # fmt: skip
ORDER = ("SCOPE", "ASSUMPTIONS", "EXCLUSIONS", "PAYMENT_MILESTONES", "VALIDITY", "WARRANTY", "SERVICE_SUPPORT", "TERMS")


def _items(p: dict[str, Any], code: str) -> list[str]:
    if code == "SCOPE":
        return [f"{r['title']}: {len(r['lines'])} item{'s' if len(r['lines']) != 1 else ''}" for r in p["rooms"]]
    if code == "PAYMENT_MILESTONES":
        return [f"{m['label']} — {m['share']}: {m['trigger']}" for m in p["payment_schedule"]]
    if code == "VALIDITY":
        return [f"Issued {p['issued_on']}; valid until {p['valid_until']}."] if p.get("valid_until") else []
    key = {"ASSUMPTIONS": "assumptions", "EXCLUSIONS": "exclusions", "WARRANTY": "warranty",
           "SERVICE_SUPPORT": "service_support", "TERMS": "terms"}[code]  # fmt: skip
    return list(p.get(key) or [])


def required_sections() -> tuple[str, ...] | None:
    d = policy.decision("CQX-D03")
    return None if d is None else tuple(d.required_sections)


def existing(s: Session, q: Quotation, g: ProposalAccessGrant) -> dict[str, QuotationAcknowledgement]:
    rows = s.execute(sa.select(QuotationAcknowledgement).where(QuotationAcknowledgement.quotation_id == q.id,
                                                               QuotationAcknowledgement.grant_id == g.id)).scalars()  # fmt: skip
    return {r.section_code: r for r in rows}


def acknowledge(s: Session, g: ProposalAccessGrant, q: Quotation, section: str, shown: str) -> QuotationAcknowledgement:
    from . import grants

    grants.locked(s, g, q)  # lock first, then re-read the link and the quotation (CQX N5)
    p = projection.build(s, q)  # verified frozen document, or a refusal
    require_open(s, q)
    digest = p["sections"].get(section)
    if digest is None:
        raise ApiError(409, "SECTION_NOT_AVAILABLE", "This section has not been confirmed by Veda Spaces yet, so it "
                       "cannot be acknowledged.", extra={"section": section})  # fmt: skip
    if digest != shown:
        raise ApiError(409, "PROPOSAL_CHANGED", "What you acknowledged is not this version's text. Please reload the "
                       "proposal and read it again.")  # fmt: skip
    found = existing(s, q, g).get(section)
    if found is not None:
        return found  # idempotent
    now = db.tx_time(s)
    evidence = {"quotation_number": q.quotation_number, "variation_no": q.variation_no, "version_no": q.version_no,
                "section": section, "section_sha256": digest, "snapshot_sha256": q.snapshot_sha256, "grant_id": g.id,
                "acknowledged_on": clock.to_rfc3339(now)}  # fmt: skip
    row = QuotationAcknowledgement(lead_id=q.lead_id, quotation_id=q.id, grant_id=g.id, section_code=section,
                                   section_sha256=digest, snapshot_sha256=q.snapshot_sha256 or "",
                                   evidence_sha256=hashlib.sha256(canonical_bytes(evidence)).hexdigest())  # fmt: skip
    s.add(row)
    events.record(s, q.id, q.lead_id, "ACKNOWLEDGED", grant=g, section=section, section_sha256=digest)
    s.flush()
    return row


def view(s: Session, g: ProposalAccessGrant, q: Quotation, p: dict[str, Any]) -> dict[str, Any]:
    required = required_sections()
    done = existing(s, q, g)
    sections = []
    for code in ORDER:
        digest = p["sections"].get(code)
        ack = done.get(code)
        sections.append({"code": code, "title": TITLES[code], "items": _items(p, code), "available": digest is not None,
                         "sha256": digest, "required": bool(required and code in required),
                         "acknowledged_on": clock.to_rfc3339(ack.created_on) if ack and ack.section_sha256 == digest else None})  # fmt: skip
    pending = [x["code"] for x in sections if x["required"] and not x["acknowledged_on"]]
    return {"sections": sections, "policy_decided": required is not None, "pending": pending}


def contribute(s: Session, g: ProposalAccessGrant, q: Quotation, page: dict[str, Any]) -> None:
    page["terms"] = view(s, g, q, page["proposal"])
    if page["capabilities"]["interaction"] and page["terms"]["pending"]:
        page["actions"].append(
            {"code": "ACKNOWLEDGE_TERMS", "label": "Read and acknowledge the terms", "target": "terms"}
        )


def staff_view(s: Session, q: Quotation) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(QuotationAcknowledgement, ProposalAccessGrant.recipient_kind)
                     .join(ProposalAccessGrant, ProposalAccessGrant.id == QuotationAcknowledgement.grant_id)
                     .where(QuotationAcknowledgement.quotation_id == q.id)
                     .order_by(QuotationAcknowledgement.created_on)).all()  # fmt: skip
    return [{"section": r.section_code, "recipient_kind": kind, "acknowledged_on": clock.to_rfc3339(r.created_on),
             "section_sha256": r.section_sha256, "evidence_sha256": r.evidence_sha256} for r, kind in rows]  # fmt: skip


PAGE_FIELDS: dict[str, str] = {
    "terms.policy_decided": "whether CQX-D03 is recorded",
    "terms.pending[]": "required sections not yet acknowledged",
    **{
        f"terms.sections[].{k}": "a customer-safe section as frozen"
        for k in ("code", "title", "items[]", "available", "sha256", "required", "acknowledged_on")
    },
}
