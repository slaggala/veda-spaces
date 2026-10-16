"""Staff projections of entitlements and service requests (WSV-050). Never served to customers (``customer`` is the
customer-safe projection). Internal notes and reasons are shown here; the full timeline only with
``warranty.service.audit``."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.modules.project.present import People

from . import access, entitlement, photos, policy, requests
from . import vocab as V
from .models import (
    ServiceAssessment,
    ServiceEvent,
    ServiceEvidence,
    ServiceNote,
    ServiceRequest,
    ServiceResolution,
    WarrantyEntitlement,
)


def _when(v) -> str | None:
    return clock.to_rfc3339(v) if v else None


def _day(v) -> str | None:
    return v.isoformat() if v else None


def entitlement_view(s: Session, e: WarrantyEntitlement | None, *, project_id: str | None = None) -> dict[str, Any]:
    today = entitlement.today(s)
    if e is None:
        return {"registered": False, "project_id": project_id, "status": V.NOT_RECORDED,
                "status_label": V.COVERAGE_STATUS_WORDS[V.NOT_RECORDED], "policy": policy.public_view()}  # fmt: skip
    t = e.terms or {}
    return {
        "registered": True, "id": e.id, "version": e.version, "project_id": e.project_id,
        "handover_on": _day(e.handover_on), "registered_on": _when(e.created_on), "registered_via": e.registered_via,
        "terms_sha256": e.terms_sha256, "policy_version": e.policy_version,
        "status": entitlement.overall(e, today), "status_label": V.COVERAGE_STATUS_WORDS[entitlement.overall(e, today)],
        "coverage": entitlement.statuses(e, today), "sources": t.get("sources") or [], "handover": t.get("handover"),
        "policy": policy.public_view(),
    }  # fmt: skip


def _row(s: Session, r: ServiceRequest, people: People) -> dict[str, Any]:
    latest = requests.latest_assessment(s, r)
    return {"id": r.id, "version": r.version, "request_number": r.request_number, "status": r.status,
            "category": r.category, "category_label": V.CATEGORIES[r.category], "priority": r.priority,
            "channel": r.channel, "reported_on": _day(r.reported_on), "property_id": r.property_id,
            "project_id": r.project_id, "owner": people(r.owner_user_id), "service_class": r.service_class,
            "outcome": latest.outcome if latest else None, "closure_code": r.closure_code,
            "cycle": r.cycle, "updated_on": _when(r.updated_on)}  # fmt: skip


def listing(s: Session, ctx, q) -> list[dict[str, Any]]:
    people = People(s)
    stmt = sa.select(ServiceRequest).where(ServiceRequest.is_deleted == sa.false(),
                                           access.request_condition(ctx, "warranty.service.view"))  # fmt: skip
    filters = {
        "OPEN": ServiceRequest.status.in_(V.OPEN_STATES), "CLOSED": ServiceRequest.status == V.CLOSED, "ALL": sa.true(),
        "MINE": sa.and_(ServiceRequest.owner_user_id == ctx.user.id, ServiceRequest.status.in_(V.OPEN_STATES)),
        "WAITING_FOR_CUSTOMER": ServiceRequest.status.in_((V.INFORMATION_REQUESTED, V.RESOLVED)),
        "AWAITING_VERIFICATION": ServiceRequest.status == V.RESOLVED,
        "AWAITING_COMMERCIAL_AGREEMENT": ServiceRequest.status == V.AWAITING_COMMERCIAL_AGREEMENT,
    }  # fmt: skip
    stmt = stmt.where(filters[q.status])
    if q.project_id:
        stmt = stmt.where(ServiceRequest.project_id == q.project_id)
    rows = s.execute(stmt.order_by(ServiceRequest.created_on.desc()).limit(200)).scalars()
    return [_row(s, r, people) for r in rows]


def _actions(s: Session, ctx, r: ServiceRequest) -> dict[str, bool]:
    def can(code: str) -> bool:
        return access.can(s, ctx, r, code)

    latest = requests.latest_assessment(s, r)
    pending = requests.pending_resolution(s, r)
    owner = r.owner_user_id == ctx.user.id
    st = r.status
    return {
        "request_information": can("warranty.service.triage") and st in V.INFORMATION_FROM,
        "add_information": can("warranty.service.triage") and st == V.INFORMATION_REQUESTED,
        "triage": can("warranty.service.triage") and st == V.REPORTED,
        "assess": can("warranty.service.assess") and (st == V.TRIAGED or (
            st in (V.ASSESSED, V.IN_PROGRESS) and latest is not None and latest.outcome == V.INSPECTION_REQUIRED)),
        "assign": can("warranty.service.assign") and st in (V.TRIAGED, V.ASSESSED, V.IN_PROGRESS,
                                                            V.AWAITING_COMMERCIAL_AGREEMENT),
        "plan_visit": can("warranty.service.resolve") and owner and st in (V.TRIAGED, V.ASSESSED, V.IN_PROGRESS),
        "record_visit": can("warranty.service.resolve") and owner and st == V.IN_PROGRESS,
        "add_evidence": can("warranty.service.resolve") and st in V.OPEN_STATES,
        "resolve": can("warranty.service.resolve") and owner and st == V.IN_PROGRESS and latest is not None
        and latest.outcome == V.COVERED,
        "verify": can("warranty.service.verify") and st == V.RESOLVED and pending is not None
        and pending.resolved_by != ctx.user.id,
        "close": can("warranty.service.assess") and st in V.OPEN_STATES and st != V.RESOLVED,
        "withdraw": can("warranty.service.triage") and st in V.WITHDRAWABLE,
        "reopen": can("warranty.service.verify") and st == V.CLOSED,
        "view_audit": can("warranty.service.audit"),
    }  # fmt: skip


def detail(s: Session, ctx, r: ServiceRequest) -> dict[str, Any]:
    people = People(s)
    e = s.get(WarrantyEntitlement, r.entitlement_id) if r.entitlement_id else entitlement.for_project(s, r.project_id)
    assessments = s.execute(sa.select(ServiceAssessment).where(ServiceAssessment.request_id == r.id)
                            .order_by(ServiceAssessment.created_on)).scalars()  # fmt: skip
    resolutions = s.execute(sa.select(ServiceResolution).where(ServiceResolution.request_id == r.id)
                            .order_by(ServiceResolution.created_on)).scalars()  # fmt: skip
    notes = s.execute(sa.select(ServiceNote).where(ServiceNote.request_id == r.id)
                      .order_by(ServiceNote.created_on)).scalars()  # fmt: skip
    evidence = s.execute(sa.select(ServiceEvidence).where(ServiceEvidence.request_id == r.id)
                         .order_by(ServiceEvidence.created_on)).scalars()  # fmt: skip
    audit = access.can(s, ctx, r, "warranty.service.audit")
    out = {
        **_row(s, r, people),
        "description": r.description, "area": r.area, "space_id": r.space_id, "noticed_on": _day(r.noticed_on),
        "related_request_id": r.related_request_id, "duplicate_of_id": r.duplicate_of_id,
        "rejections": r.rejections, "closed_on": _when(r.closed_on), "verified_by_kind": r.verified_by_kind,
        "entitlement": entitlement_view(s, e, project_id=r.project_id),
        "assessments": [{"id": a.id, "cycle": a.cycle, "outcome": a.outcome, "outcome_label": V.OUTCOME_WORDS[a.outcome],
                         "service_class": a.service_class, "basis_kind": a.basis_kind, "basis_path": a.basis_path,
                         "basis_text_sha256": a.basis_text_sha256, "as_of": _day(a.as_of),
                         "coverage_status": a.coverage_status, "explanation": a.explanation,
                         "internal_reason": a.internal_reason, "period_basis": a.period_basis,
                         "assessed_by": people(a.assessed_by), "assessed_on": _when(a.assessed_on)} for a in assessments],
        "visits": [{"id": v.id, "version": v.version, "visit_no": v.visit_no, "kind": v.kind, "status": v.status,
                    "planned_on": _day(v.planned_on), "done_on": _day(v.done_on), "customer_note": v.customer_note,
                    "internal_note": v.internal_note, "cancel_reason": v.cancel_reason, "done_by": people(v.done_by)}
                   for v in requests.visits(s, r)],
        "resolutions": [{"id": x.id, "cycle": x.cycle, "summary": x.summary, "internal_note": x.internal_note,
                         "resolved_by": people(x.resolved_by), "resolved_on": _when(x.resolved_on), "outcome": x.outcome,
                         "decided_on": _when(x.decided_on), "decided_by": people(x.decided_by),
                         "decided_by_customer": x.decided_account_id is not None} for x in resolutions],
        "notes": [{"id": n.id, "kind": n.kind, "visibility": n.visibility, "text": n.text,
                   "by": "CUSTOMER" if n.account_id else None, "author": None if n.account_id else people(n.created_by),
                   "created_on": _when(n.created_on)} for n in notes],
        "photos": [{**x, "attachment_id": link.attachment_id} for x, link in
                   zip(photos.customer_list(s, r), photos.rows(s, r), strict=True)],
        "evidence": [{"id": ev.id, "attachment_id": ev.attachment_id, "customer_visible": ev.customer_visible,
                      "caption": ev.caption, "visit_id": ev.visit_id, "resolution_id": ev.resolution_id,
                      "added_by": people(ev.created_by), "added_on": _when(ev.created_on)} for ev in evidence],
        "actions": (actions := _actions(s, ctx, r)),
        "owner_options": _owners(s) if actions["assign"] else [],
        "evidence_options": _evidence_options(s, r) if actions["add_evidence"] or actions["record_visit"]
        or actions["resolve"] else [],
        "vocabulary": vocabulary(),
    }  # fmt: skip
    if audit:
        out["timeline"] = [{"code": ev.event_code, "from": ev.from_state, "to": ev.to_state, "detail": ev.detail,
                            "by": "CUSTOMER" if ev.account_id else None,
                            "actor": None if ev.account_id else people(ev.created_by), "at": _when(ev.created_on)}
                           for ev in s.execute(sa.select(ServiceEvent).where(ServiceEvent.request_id == r.id)
                                               .order_by(ServiceEvent.created_on, ServiceEvent.id)).scalars()]  # fmt: skip
    return out


def _owners(s: Session) -> list[dict[str, Any]]:
    """Active people who may own a request (hold ``warranty.service.resolve``); names only, validated again on assign."""
    from veda.platform.identity.models import User
    from veda.platform.rbac.resolver import holders_of

    out: list[dict[str, Any]] = []
    for uid in holders_of(s, "warranty.service.resolve"):
        u = s.get(User, uid)
        if u is not None and u.status == "ACTIVE" and u.user_type == "HUMAN":
            out.append({"id": uid, "display_name": u.display_name})
    return sorted(out, key=lambda x: (x.get("display_name") or "").casefold())


def _evidence_options(s: Session, r: ServiceRequest) -> list[dict[str, Any]]:
    """Scanned, available attachments of this customer's home that may be cited (references only, never a URL)."""
    from veda.modules.attachments import service as att
    from veda.modules.attachments.models import Attachment

    rows = s.execute(sa.select(Attachment).where(Attachment.lead_id == r.lead_id, Attachment.scan_status == "CLEAN",
                                                 Attachment.is_deleted == sa.false())
                     .order_by(Attachment.created_on.desc()).limit(100)).scalars()  # fmt: skip
    return [{"id": a.id, "category": a.category_code, "attached_to": a.entity_type, "internal": a.visibility_code != "STANDARD",
             "uploaded_on": _when(a.created_on)} for a in rows if att.is_available(a)]  # fmt: skip


def vocabulary() -> dict[str, Any]:
    return {"categories": [{"code": k, "label": v} for k, v in V.CATEGORIES.items()],
            "outcomes": [{"code": k, "label": v} for k, v in V.OUTCOME_WORDS.items()],
            "closures": list(V.STAFF_CLOSURES), "priorities": list(V.PRIORITIES), "visit_kinds": list(V.VISIT_KINDS),
            "max_rejections": V.MAX_REJECTIONS}  # fmt: skip
