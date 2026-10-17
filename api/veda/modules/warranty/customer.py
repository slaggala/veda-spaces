"""The customer's "Warranty & service" view in the Customer Project Portal (WSV-060), allow-listed field by field.

Reached only through the account's authorised property (the portal resolves it); every ACTIVE account of the enquiry
sees the property's warranty and requests (the household), as with project delivery. Shown: the warranty summary of
each handed-over project (statements verbatim, labelled by kind and quotation; recorded coverage classes and their
status; exclusions; the policy link), and each request in plain words: what is happening, who acts next, what Veda
Spaces asked and the customer answered, the coverage explanation, planned visits, the resolution and evidence staff
chose to show. Never: internal notes or reasons, period bases, staff names, assessor or owner identities, digests,
attachment ids, amounts, or a green "covered" for an entitlement as such.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock

from . import access, entitlement, photos, requests
from . import vocab as V
from .models import ServiceNote, ServiceRequest, ServiceResolution

STATUS_WORDS = {
    V.REPORTED: ("Received", "VEDA_SPACES"),
    V.INFORMATION_REQUESTED: ("Waiting for your reply", "YOU"),
    V.TRIAGED: ("Being reviewed", "VEDA_SPACES"),
    V.ASSESSED: ("Reviewed", "VEDA_SPACES"),
    V.AWAITING_COMMERCIAL_AGREEMENT: ("Not covered by your warranty", "VEDA_SPACES"),
    V.IN_PROGRESS: ("Being worked on", "VEDA_SPACES"),
    V.RESOLVED: ("Please confirm it is resolved", "YOU"),
    V.CLOSED: ("Closed", None),
}
CLOSURE_WORDS = {
    "SERVICED": "Resolved", "DUPLICATE": "Closed: already reported", "NOT_COVERED": "Closed: not covered",
    "REFERRED_TO_MANUFACTURER": "Closed: for the manufacturer's warranty", "CHARGEABLE_NOT_AGREED": "Closed",
    "CUSTOMER_WITHDREW": "Withdrawn", "CANNOT_SERVICE": "Closed",
}  # fmt: skip
SOURCE_KINDS = {"warranty": "Warranty", "service_support": "Veda Spaces service support"}
VISIT_WORDS = {"INSPECTION": "Inspection visit", "SERVICE": "Service visit"}
CHARGEABLE_WORDS = ("This is not covered by your warranty. Veda Spaces will contact you about whether it can be done "
                    "as separate, chargeable work; nothing is charged without your agreement.")  # fmt: skip


def projects(s: Session, property_id: str) -> list:
    from veda.modules.project.models import Project

    return list(s.execute(sa.select(Project).where(Project.property_id == property_id, Project.is_deleted == sa.false())
                          .order_by(Project.created_on, Project.id)).scalars())  # fmt: skip


def _warranty(s: Session, p) -> dict[str, Any]:
    e = entitlement.for_project(s, p.id)
    if p.status != "HANDED_OVER":
        return {"state": "BEFORE_HANDOVER", "message": "Warranty details are confirmed at handover."}
    if e is None:
        return {"state": "BEING_PREPARED", "message": "Your warranty summary is being prepared. You can already report a "
                "problem."}  # fmt: skip
    today = entitlement.today(s)
    t = e.terms or {}
    statements: list[dict[str, Any]] = []
    exclusions: list[str] = []
    manufacturer: list[str] = []
    for src in t.get("sources") or []:
        ref = f"{src.get('quotation_number')} v{src.get('version_no')}"
        for key, label in SOURCE_KINDS.items():
            statements += [{"kind": label, "text": x, "source": ref} for x in src.get(key) or []]
        exclusions += [x["text"] for x in src.get("warranty_exclusions") or [] if x.get("text")]
        if src.get("manufacturer_warranty_note"):
            manufacturer.append(src["manufacturer_warranty_note"])
    status = entitlement.overall(e, today)
    return {
        "state": "REGISTERED", "id": e.id, "handed_over_on": e.handover_on.isoformat(),
        "status": status, "status_label": V.COVERAGE_STATUS_WORDS[status],
        "period_note": None if status != V.NOT_RECORDED else "Your warranty period is as stated in your accepted "
        "quotation and the Veda Spaces Warranty, Service & Customer Care Policy.",
        "coverage": [{"label": c["label"], "covers": c["covers"], "exclusions": c["exclusions"], "status": c["status"],
                      "status_label": V.COVERAGE_STATUS_WORDS[c["status"]], "starts_on": c["starts_on"],
                      "ends_on": c["ends_on"]} for c in entitlement.statuses(e, today)],
        "statements": statements, "exclusions": list(dict.fromkeys(exclusions)),
        "manufacturer_notes": list(dict.fromkeys(manufacturer)),
        "policy_url": settings().warranty_policy_url or None,
    }  # fmt: skip


def _notes(s: Session, r: ServiceRequest) -> list[dict[str, Any]]:
    rows = s.execute(sa.select(ServiceNote).where(ServiceNote.request_id == r.id, ServiceNote.visibility == "CUSTOMER",
                                                  ServiceNote.is_deleted == sa.false())
                     .order_by(ServiceNote.created_on, ServiceNote.id)).scalars()  # fmt: skip
    words = {"INFORMATION_REQUEST": "Veda Spaces asked", "CUSTOMER_INFORMATION": "You replied", "REJECTION":
             "You said it is still not right", "CLOSURE": "Veda Spaces", "WITHDRAWAL": "You withdrew it"}  # fmt: skip
    return [{"from": "YOU" if n.account_id else "VEDA_SPACES", "label": words.get(n.kind, "Note"), "text": n.text,
             "on": clock.to_rfc3339(n.created_on)} for n in rows]  # fmt: skip


def request_view(s: Session, r: ServiceRequest) -> dict[str, Any]:
    latest = requests.latest_assessment(s, r)
    label, next_ = STATUS_WORDS[r.status]
    if r.status == V.CLOSED:
        label = CLOSURE_WORDS.get(r.closure_code or "", "Closed")
    coverage = None
    if latest is not None and latest.outcome != V.INSUFFICIENT_INFORMATION:
        coverage = {"outcome": latest.outcome, "label": V.OUTCOME_WORDS[latest.outcome],
                    "explanation": latest.explanation,
                    "chargeable_note": CHARGEABLE_WORDS if latest.service_class == V.CHARGEABLE else None}  # fmt: skip
    pending = requests.pending_resolution(s, r)
    shown = s.execute(sa.select(ServiceResolution).where(ServiceResolution.request_id == r.id,
                                                         ServiceResolution.is_deleted == sa.false())
                      .order_by(ServiceResolution.created_on.desc())).scalars().first()  # fmt: skip
    return {
        "id": r.id, "reference": r.request_number, "status": r.status, "status_label": label, "next": next_,
        "category": V.CATEGORIES[r.category], "description": r.description, "area": r.area,
        "noticed_on": r.noticed_on.isoformat() if r.noticed_on else None, "reported_on": r.reported_on.isoformat(),
        "project_id": r.project_id, "photos": photos.customer_list(s, r),
        "messages": _notes(s, r), "coverage": coverage,
        "visits": [{"kind": VISIT_WORDS[v.kind], "status": v.status, "planned_on": v.planned_on.isoformat(),
                    "done_on": v.done_on.isoformat() if v.done_on else None, "note": v.customer_note}
                   for v in requests.visits(s, r) if v.status != "CANCELLED"],
        "resolution": {"summary": shown.summary, "outcome": shown.outcome} if shown else None,
        "evidence": [{"id": ev.id, "caption": ev.caption} for ev in photos.visible_evidence(s, r)],
        "can_add_information": r.status == V.INFORMATION_REQUESTED,
        "can_add_photos": r.status in photos.CUSTOMER_STATES
        and sum(1 for x in photos.rows(s, r) if x.channel == "PORTAL") < V.MAX_CUSTOMER_PHOTOS,
        "can_confirm": r.status == V.RESOLVED and pending is not None,
        "can_reject": r.status == V.RESOLVED and pending is not None and r.rejections < V.MAX_REJECTIONS,
        "can_withdraw": r.status in V.WITHDRAWABLE,
    }  # fmt: skip


def view(s: Session, property_id: str) -> dict[str, Any] | None:
    if not access.customer_enabled():
        return None
    out = []
    for p in projects(s, property_id):
        rows = s.execute(sa.select(ServiceRequest).where(ServiceRequest.project_id == p.id,
                                                         ServiceRequest.is_deleted == sa.false())
                         .order_by(ServiceRequest.created_on.desc())).scalars()  # fmt: skip
        out.append({"id": p.id, "handed_over": p.status == "HANDED_OVER", "warranty": _warranty(s, p),
                    "requests": [request_view(s, r) for r in rows], "can_report": p.status == "HANDED_OVER"})  # fmt: skip
    return {"available": True, "projects": out,
            "categories": [{"code": k, "label": v} for k, v in V.CATEGORIES.items()],
            "max_photos": V.MAX_CUSTOMER_PHOTOS}  # fmt: skip


def documents(view_: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The warranty summary of each registered entitlement, listed with the property's documents."""
    return [{"kind": "WARRANTY_SUMMARY", "id": p["warranty"]["id"], "title": "Warranty summary",
             "issued_on": p["warranty"]["handed_over_on"], "project_id": p["id"]}
            for p in (view_ or {}).get("projects", []) if p["warranty"].get("state") == "REGISTERED"]  # fmt: skip


def request_for(s: Session, property_id: str, request_id: str) -> ServiceRequest:
    from veda.kernel.errors import not_found

    r = s.get(ServiceRequest, request_id)
    if r is None or r.is_deleted or r.property_id != property_id:
        raise not_found()
    return r
