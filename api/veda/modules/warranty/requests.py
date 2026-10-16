"""Post-handover service requests (WSV-010 … WSV-019): an explicit, server-side workflow.

A request's initial meaning is only that the customer reported an issue: it asserts no defect, warranty validity,
responsibility or free service. Every change is a command that checks the actor, permission and scope, the current
state, the version (If-Match for staff; idempotency for customers) and its own required fields, writes its rows and
appends a text-free timeline event. No body carries a status. Nothing is deleted; rows that hold history (assessments,
resolutions, visits, notes) are appended, never overwritten.

Coverage is decided only by ``assess`` (``warranty.service.assess``), as of the request's ``reported_on``:

- COVERED needs a basis: a structured coverage class ACTIVE on that date, or a cited ``warranty`` or
  ``service_support`` statement of the frozen entitlement (path and text digest stored) together with a recorded
  period basis while no structured class applies. A manufacturer note, an exclusion or estimator copy never supports
  COVERED.
- MANUFACTURER_WARRANTY is a referral: never covered, never resolved as Veda Spaces' work.
- NOT_COVERED (an exclusion may be cited) and OUTSIDE_WARRANTY_PERIOD (an EXPIRED class on that date, or a cited
  statement with its period basis) choose CHARGEABLE or NOT_SERVICEABLE.
- CHARGEABLE fails closed: the repository has no mechanism to agree post-handover work commercially, so the request
  waits in AWAITING_COMMERCIAL_AGREEMENT and can only be withdrawn or closed CHARGEABLE_NOT_AGREED.
- INSPECTION_REQUIRED allows an inspection visit and a new assessment; INSUFFICIENT_INFORMATION asks the customer.

A SERVICE visit and a resolution need the latest assessment of the cycle to be COVERED. Verification is the customer's
confirmation or a staff verification by someone other than the resolver; a customer may reject a resolution twice,
then staff verify. Reopening a closed request needs a reason, starts a new cycle and needs a new coverage decision.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db, sequences
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.jcs import canonical_bytes

from . import access, entitlement, events
from . import vocab as V
from .models import (
    ServiceAssessment,
    ServiceEvidence,
    ServiceNote,
    ServiceRequest,
    ServiceResolution,
    ServiceVisit,
    WarrantyEntitlement,
)

SEQUENCE = "SERVICE_REQUEST"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _invalid(field: str, code: str, message: str, status: int = 422) -> ApiError:
    return ApiError(status, "VALIDATION_FAILED", message, errors=[field_error(field, code, message)])


def _text(value: str | None, field: str, what: str, min_len: int = 5) -> str:
    text = (value or "").strip()
    if len(text) < min_len:
        raise _invalid(field, "REQUIRED", f"{what} (at least {min_len} characters).")
    return text


def note(
    s: Session, r: ServiceRequest, kind: str, visibility: str, text: str, account_id: str | None = None
) -> ServiceNote:
    n = ServiceNote(
        request_id=r.id, lead_id=r.lead_id, kind=kind, visibility=visibility, text=text, account_id=account_id
    )
    s.add(n)
    s.flush()
    return n


def _touch(s: Session, r: ServiceRequest) -> None:
    r.updated_on = db.tx_time(s)  # the version moves on any change under the request


def latest_assessment(s: Session, r: ServiceRequest) -> ServiceAssessment | None:
    return s.execute(sa.select(ServiceAssessment).where(ServiceAssessment.request_id == r.id,
                                                        ServiceAssessment.cycle == r.cycle,
                                                        ServiceAssessment.is_deleted == sa.false())
                     .order_by(ServiceAssessment.created_on.desc(), ServiceAssessment.id.desc())).scalars().first()  # fmt: skip


def visits(s: Session, r: ServiceRequest) -> list[ServiceVisit]:
    return list(s.execute(sa.select(ServiceVisit).where(ServiceVisit.request_id == r.id, ServiceVisit.is_deleted == sa.false())
                          .order_by(ServiceVisit.visit_no)).scalars())  # fmt: skip


def done_since(s: Session, r: ServiceRequest, kind: str, after) -> bool:
    """A visit of ``kind`` of this cycle, planned after ``after`` (a decision or a rejected resolution) and done:
    work recorded for an earlier cycle or before the current decision never counts (review H2)."""
    return any(v.kind == kind and v.status == "DONE" and v.cycle == r.cycle and (after is None or v.created_on > after)
               for v in visits(s, r))  # fmt: skip


def last_rejection(s: Session, r: ServiceRequest):
    return s.execute(sa.select(sa.func.max(ServiceResolution.decided_on)).where(
        ServiceResolution.request_id == r.id, ServiceResolution.cycle == r.cycle,
        ServiceResolution.outcome == "REJECTED")).scalar()  # fmt: skip


def pending_resolution(s: Session, r: ServiceRequest) -> ServiceResolution | None:
    return s.execute(sa.select(ServiceResolution).where(ServiceResolution.request_id == r.id,
                                                        ServiceResolution.outcome == "PENDING",
                                                        ServiceResolution.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip


# --- submission --------------------------------------------------------------------------------------------------------
def _project_of(s: Session, property_id: str, project_id: str):
    from veda.modules.project.models import Project

    p = s.get(Project, project_id)
    if p is None or p.property_id != property_id or p.is_deleted:
        raise not_found()
    return p


def _space(s: Session, property_id: str, space_id: str | None) -> str | None:
    if space_id is None:
        return None
    from veda.modules.mtq.models import PropertySpace

    sp = s.get(PropertySpace, space_id)
    if sp is None or sp.property_id != property_id or sp.is_deleted:
        raise _invalid("space_id", "UNKNOWN_SPACE", "Not a room of this home.")
    return sp.id


def _same_property(s: Session, property_id: str, request_id: str | None, field: str) -> str | None:
    if request_id is None:
        return None
    other = s.get(ServiceRequest, request_id)
    if other is None or other.property_id != property_id or other.is_deleted:
        raise _invalid(field, "UNKNOWN_REQUEST", "Not a service request of this home.")
    return other.id


def submit(s: Session, *, property_id: str, project_id: str, body, channel: str, account_id: str | None = None,
           key: str | None = None) -> tuple[ServiceRequest, bool]:  # fmt: skip
    """(request, created). The caller checked the flags and the actor's access to the property (or the staff code)."""
    from veda.modules.crm.leads.models import Lead
    from veda.modules.project import access as paccess

    p = _project_of(s, property_id, project_id)
    key_sha = request_sha = None
    if channel == "PORTAL":
        if not key or not 8 <= len(key) <= 128:
            raise ApiError(400, "IDEMPOTENCY_KEY_REQUIRED", "Send an Idempotency-Key header (8 to 128 characters).")
        key_sha = _sha(key)
        request_sha = hashlib.sha256(canonical_bytes({"project_id": p.id, "category": body.category,
                                                      "description": body.description, "area": body.area,
                                                      "space_id": body.space_id, "noticed_on": str(body.noticed_on),
                                                      "related_request_id": body.related_request_id})).hexdigest()  # fmt: skip
    paccess.lock(s, p)  # serialises submissions on this project (the open-request cap is counted under it)
    lead = s.get(Lead, p.lead_id)
    if lead is None or lead.anonymized_on is not None:
        raise not_found()
    if key_sha is not None:
        found = s.execute(sa.select(ServiceRequest).where(ServiceRequest.account_id == account_id,
                                                          ServiceRequest.client_key_sha256 == key_sha,
                                                          ServiceRequest.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip
        if found is not None:
            if found.request_sha256 != request_sha:
                raise ApiError(
                    409, "IDEMPOTENCY_KEY_REUSED", "This request key was already used for a different request."
                )
            return found, False
    if p.status != "HANDED_OVER":
        raise ApiError(409, "PROJECT_NOT_HANDED_OVER", "Your home has not been handed over yet. Please report it on "
                       "your project instead, or speak to your Veda Spaces contact.")  # fmt: skip
    if body.noticed_on is not None and body.noticed_on > entitlement.today(s):
        raise _invalid("noticed_on", "FUTURE_DATE", "The date you noticed it cannot be in the future.")
    open_ = s.execute(sa.select(sa.func.count(ServiceRequest.id)).where(
        ServiceRequest.project_id == p.id, ServiceRequest.status.in_(V.OPEN_STATES), ServiceRequest.is_deleted == sa.false(),
        ServiceRequest.account_id == account_id if account_id else ServiceRequest.channel == "STAFF")).scalar() or 0  # fmt: skip
    if open_ >= V.MAX_OPEN_PER_ACCOUNT:
        raise ApiError(409, "REQUEST_LIMIT_REACHED", f"There are {open_} open service requests for this home. Veda "
                       "Spaces will look at those first; please speak to your contact if something is urgent.")  # fmt: skip
    e = entitlement.for_project(s, p.id)
    r = ServiceRequest(request_number=sequences.next_number(s, SEQUENCE), lead_id=p.lead_id, property_id=p.property_id,
                       project_id=p.id, entitlement_id=e.id if e else None,
                       related_request_id=_same_property(s, p.property_id, body.related_request_id, "related_request_id"),
                       channel=channel, account_id=account_id, category=body.category,
                       space_id=_space(s, p.property_id, body.space_id), area=body.area, description=body.description,
                       noticed_on=body.noticed_on, reported_on=entitlement.today(s), status=V.REPORTED,
                       client_key_sha256=key_sha, request_sha256=request_sha)  # fmt: skip
    s.add(r)
    s.flush()
    events.record(s, r, "SUBMITTED", to=V.REPORTED, account_id=account_id, channel=channel, project_id=p.id,
                  related_request_id=r.related_request_id)  # fmt: skip
    events.customer(s, r, events.RECEIVED)
    if channel == "PORTAL":
        events.staff(s, r, events.SUBMITTED)
    return r, True


# --- information -------------------------------------------------------------------------------------------------------
def request_information(s: Session, ctx, r: ServiceRequest, question: str, if_match: int | None) -> ServiceRequest:
    access.for_write(s, ctx, r, "warranty.service.triage", if_match)
    access.state(r, *V.INFORMATION_FROM)
    _ask(s, r, _text(question, "question", "Ask the customer what you need, in words they will read", 10))
    return r


def _ask(s: Session, r: ServiceRequest, question: str) -> None:
    n = note(s, r, "INFORMATION_REQUEST", "CUSTOMER", question)
    frm = r.status
    r.return_state, r.status = (frm if frm in V.INFORMATION_FROM else V.TRIAGED), V.INFORMATION_REQUESTED
    _touch(s, r)
    events.record(s, r, "INFORMATION_REQUESTED", frm=frm, to=r.status, note_id=n.id)
    events.customer(s, r, events.INFORMATION_REQUESTED)


def add_information(s: Session, r: ServiceRequest, text: str, *, account_id: str | None = None, ctx=None,
                    if_match: int | None = None) -> ServiceRequest:  # fmt: skip
    if ctx is not None:
        access.for_write(s, ctx, r, "warranty.service.triage", if_match)
    else:
        access.lock(s, r)
        access.lead_open(s, r.lead_id)
    access.state(r, V.INFORMATION_REQUESTED)
    n = note(s, r, "CUSTOMER_INFORMATION", "CUSTOMER", _text(text, "text", "Tell us what was asked", 3),
             account_id=account_id)  # fmt: skip
    back = r.return_state or V.TRIAGED
    r.status, r.return_state = back, None
    _touch(s, r)
    events.record(s, r, "INFORMATION_ADDED", frm=V.INFORMATION_REQUESTED, to=back, account_id=account_id, note_id=n.id)
    if account_id:
        events.staff(s, r, events.INFORMATION_ADDED)
    return r


# --- triage, assessment, assignment ------------------------------------------------------------------------------------
def triage(s: Session, ctx, r: ServiceRequest, body, if_match: int | None) -> ServiceRequest:
    access.for_write(s, ctx, r, "warranty.service.triage", if_match)
    access.state(r, V.REPORTED)
    if body.category is not None:
        r.category = body.category
    r.priority = body.priority
    if body.space_id is not None:
        r.space_id = _space(s, r.property_id, body.space_id)
    if body.note:
        note(s, r, "INTERNAL", "INTERNAL", body.note.strip())
    r.status = V.TRIAGED
    _touch(s, r)
    events.record(s, r, "TRIAGED", frm=V.REPORTED, to=V.TRIAGED, category=r.category, priority=r.priority)
    return r


def _entitlement(s: Session, r: ServiceRequest) -> WarrantyEntitlement:
    e = s.get(WarrantyEntitlement, r.entitlement_id) if r.entitlement_id else entitlement.for_project(s, r.project_id)
    if e is None:
        raise ApiError(409, "ENTITLEMENT_NOT_REGISTERED", "The warranty of this project is not registered yet; register "
                       "it from the project's handover first.")  # fmt: skip
    r.entitlement_id = e.id
    return e


def _class(e: WarrantyEntitlement, code: str | None) -> dict[str, Any] | None:
    if code is None:
        return None
    found = next((c for c in (e.terms or {}).get("coverage") or [] if c.get("code") == code), None)
    if found is None:
        raise _invalid("coverage_class", "UNKNOWN_CLASS", "Not a coverage class of this warranty.")
    return found


def _recorded(e: WarrantyEntitlement, on: date) -> bool:
    return any(x["status"] != V.NOT_RECORDED for x in entitlement.statuses(e, on))


def assess(s: Session, ctx, r: ServiceRequest, body, if_match: int | None) -> ServiceAssessment:
    access.for_write(s, ctx, r, "warranty.service.assess", if_match)
    access.state(r, V.TRIAGED, V.IN_PROGRESS, V.ASSESSED)
    previous = latest_assessment(s, r)
    if r.status in (V.IN_PROGRESS, V.ASSESSED):
        # after an inspection: one planned before the first decision (from TRIAGED), or one the latest decision asked for
        asked = previous is None or previous.outcome == V.INSPECTION_REQUIRED
        if not asked or not done_since(s, r, "INSPECTION", previous.created_on if previous else None):
            raise ApiError(409, "INSPECTION_NOT_DONE", "A request is assessed again only after the inspection it needed "
                           "is recorded.")  # fmt: skip
    e = _entitlement(s, r)
    on = r.reported_on
    outcome = body.outcome
    explanation = _text(body.explanation, "explanation", "Explain the decision to the customer", 10)
    internal = _text(body.internal_reason, "internal_reason", "Record the reason for the decision", 10)
    period = (body.period_basis or "").strip() or None
    basis_kind = basis_path = basis_sha = cov_status = None
    service_class = None
    cls = _class(e, body.coverage_class)
    if cls is not None:
        cov_status, _start, _end = entitlement.class_status(e, cls, on)
        basis_kind, basis_path, basis_sha = (
            "COVERAGE_CLASS",
            f"coverage/{cls['code']}",
            entitlement.text_sha(cls["covers"]),
        )
    elif body.basis_path:
        found = entitlement.cited(e, body.basis_path)
        if found is None:
            raise _invalid("basis_path", "UNKNOWN_SOURCE", "Not a statement of this warranty.")
        basis_kind, basis_path, basis_sha = found[0], body.basis_path, entitlement.text_sha(found[1])
    if outcome == V.COVERED:
        if basis_kind not in V.COVERED_BASES:
            raise _invalid("basis_path", "BASIS_REQUIRED", "Coverage rests on an active coverage class or a warranty or "
                           "service-support statement of the accepted quotation (never a manufacturer note or an "
                           "exclusion).")  # fmt: skip
        if basis_kind == "COVERAGE_CLASS" and cov_status != V.ACTIVE:
            raise ApiError(422, "COVERAGE_NOT_ACTIVE", f"That coverage was {(cov_status or '').lower().replace('_', ' ')} "
                           f"on {on.isoformat()}, when the request was reported.", extra={"coverage_status": cov_status})  # fmt: skip
        if basis_kind != "COVERAGE_CLASS" and _recorded(e, on):
            raise _invalid("coverage_class", "CLASS_REQUIRED", "A recorded coverage class applies to this warranty: decide "
                           "on the class, not on a statement.")  # fmt: skip
        if basis_kind != "COVERAGE_CLASS" and not period:
            raise _invalid("period_basis", "REQUIRED", "No warranty period is recorded: say why the request is within the "
                           "cited statement's period.")  # fmt: skip
        service_class = V.WARRANTY
    elif outcome == V.OUTSIDE_WARRANTY_PERIOD:
        if basis_kind == "COVERAGE_CLASS":
            if cov_status != V.EXPIRED:
                raise ApiError(422, "COVERAGE_NOT_EXPIRED", f"That coverage was {(cov_status or '').lower()} on "
                               f"{on.isoformat()}.", extra={"coverage_status": cov_status})  # fmt: skip
        elif basis_kind in ("WARRANTY_STATEMENT", "SERVICE_SUPPORT_STATEMENT"):
            if _recorded(e, on):
                raise _invalid("coverage_class", "CLASS_REQUIRED", "A recorded coverage class applies to this warranty: "
                               "decide on the class, not on a statement.")  # fmt: skip
            if not period:
                raise _invalid(
                    "period_basis", "REQUIRED", "Say why the request is outside the cited statement's period."
                )
        else:
            raise _invalid("basis_path", "BASIS_REQUIRED", "Cite the coverage class or statement whose period ended.")
    elif outcome == V.NOT_COVERED:
        if basis_kind is not None and basis_kind not in ("EXCLUSION", "WARRANTY_STATEMENT", "SERVICE_SUPPORT_STATEMENT",
                                                         "COVERAGE_CLASS"):  # fmt: skip
            raise _invalid(
                "basis_path", "BASIS_NOT_ALLOWED", "Cite an exclusion or the statement that does not cover it."
            )
    elif outcome == V.MANUFACTURER_WARRANTY:
        if basis_kind is not None and basis_kind != "MANUFACTURER_NOTE":
            raise _invalid("basis_path", "BASIS_NOT_ALLOWED", "Cite the manufacturer-warranty note, or nothing.")
    elif basis_kind is not None:
        raise _invalid("basis_path", "BASIS_NOT_ALLOWED", "No basis is cited for this outcome.")
    if outcome in (V.NOT_COVERED, V.OUTSIDE_WARRANTY_PERIOD):
        if body.service_class not in (V.CHARGEABLE, V.NOT_SERVICEABLE):
            raise _invalid("service_class", "REQUIRED", "Say whether the work could be offered as chargeable service or "
                           "cannot be serviced.")  # fmt: skip
        service_class = body.service_class
    a = ServiceAssessment(request_id=r.id, lead_id=r.lead_id, cycle=r.cycle, outcome=outcome, service_class=service_class,
                          basis_kind=basis_kind, basis_path=basis_path, basis_text_sha256=basis_sha, as_of=on,
                          coverage_status=cov_status, explanation=explanation, internal_reason=internal,
                          period_basis=period, assessed_by=ctx.user.id, assessed_on=db.tx_time(s))  # fmt: skip
    s.add(a)
    s.flush()
    frm = r.status
    r.service_class = service_class
    if outcome == V.INSUFFICIENT_INFORMATION:
        r.status = V.TRIAGED
        events.record(s, r, "ASSESSED", frm=frm, to=V.TRIAGED, outcome=outcome, assessment_id=a.id)
        _ask(s, r, explanation)
        return a
    r.status = V.AWAITING_COMMERCIAL_AGREEMENT if service_class == V.CHARGEABLE else V.ASSESSED
    _touch(s, r)
    events.record(s, r, "ASSESSED", frm=frm, to=r.status, outcome=outcome, assessment_id=a.id, basis=basis_kind,
                  basis_sha256=basis_sha)  # fmt: skip
    events.customer(s, r, events.COVERAGE_DECIDED, assessment_id=a.id)
    return a


def assign(s: Session, ctx, r: ServiceRequest, owner_user_id: str, if_match: int | None) -> ServiceRequest:
    from veda.platform.identity.models import User
    from veda.platform.rbac.resolver import load_grants

    access.for_write(s, ctx, r, "warranty.service.assign", if_match)
    access.state(r, V.TRIAGED, V.ASSESSED, V.IN_PROGRESS, V.AWAITING_COMMERCIAL_AGREEMENT)
    u = s.get(User, owner_user_id)
    scope = load_grants(s, owner_user_id).granted.get("warranty.service.resolve") if u is not None else None
    if u is None or u.status != "ACTIVE" or u.user_type != "HUMAN" or scope is None:
        raise _invalid("owner_user_id", "NOT_ELIGIBLE", "That person cannot resolve service requests "
                       "(needs warranty.service.resolve).")  # fmt: skip
    previous, r.owner_user_id = r.owner_user_id, u.id
    _touch(s, r)
    events.record(s, r, "ASSIGNED", frm=r.status, to=r.status, owner_user_id=u.id, previous_owner_id=previous)
    return r


# --- visits, evidence, resolution --------------------------------------------------------------------------------------
def _owner(ctx, r: ServiceRequest) -> None:
    if r.owner_user_id != ctx.user.id:
        raise ApiError(
            403, "OWNER_ONLY", "Only the request's owner records its visits and resolution; assign it first."
        )


def plan_visit(s: Session, ctx, r: ServiceRequest, body, if_match: int | None) -> ServiceVisit:
    access.for_write(s, ctx, r, "warranty.service.resolve", if_match)
    _owner(ctx, r)
    access.state(r, V.TRIAGED, V.ASSESSED, V.IN_PROGRESS)
    latest = latest_assessment(s, r)
    if body.kind == "SERVICE" and (latest is None or latest.outcome != V.COVERED):
        raise ApiError(409, "COVERAGE_NOT_DECIDED", "A service visit follows a decision that the request is covered.")
    if (
        body.kind == "INSPECTION"
        and r.status != V.TRIAGED
        and (latest is None or latest.outcome != V.INSPECTION_REQUIRED)
    ):
        raise ApiError(409, "INSPECTION_NOT_REQUIRED", "An inspection is planned before the coverage decision or when "
                       "the decision says one is needed.")  # fmt: skip
    if body.planned_on < entitlement.today(s):
        raise _invalid("planned_on", "PAST_DATE", "A planned visit date cannot be in the past.")
    n = (max((v.visit_no for v in visits(s, r)), default=0)) + 1
    v = ServiceVisit(request_id=r.id, lead_id=r.lead_id, visit_no=n, cycle=r.cycle, kind=body.kind, status="PLANNED",
                     planned_on=body.planned_on, customer_note=body.customer_note, internal_note=body.internal_note)  # fmt: skip
    s.add(v)
    s.flush()
    frm, r.status = r.status, V.IN_PROGRESS
    _touch(s, r)
    events.record(s, r, "VISIT_PLANNED", frm=frm, to=r.status, visit_id=v.id, kind=v.kind,
                  planned_on=v.planned_on.isoformat())  # fmt: skip
    events.customer(s, r, events.VISIT_PLANNED, visit_id=v.id)
    return v


def _visit(s: Session, r: ServiceRequest, visit_id: str) -> ServiceVisit:
    v = s.get(ServiceVisit, visit_id)
    if v is None or v.request_id != r.id or v.is_deleted:
        raise not_found()
    return v


def record_visit(s: Session, ctx, r: ServiceRequest, visit_id: str, body, if_match: int | None) -> ServiceVisit:
    access.for_write(s, ctx, r, "warranty.service.resolve", if_match)
    _owner(ctx, r)
    access.state(r, V.IN_PROGRESS)
    v = _visit(s, r, visit_id)
    if v.status != "PLANNED" or v.cycle != r.cycle:
        raise ApiError(
            409, "INVALID_STATE", f"Visit {v.visit_no} is {v.status.lower()} or belongs to an earlier cycle."
        )
    if body.done_on > entitlement.today(s):
        raise _invalid("done_on", "FUTURE_DATE", "A visit cannot be recorded as done in the future.")
    v.status, v.done_on, v.done_by = "DONE", body.done_on, ctx.user.id
    if body.customer_note:
        v.customer_note = body.customer_note
    if body.internal_note:
        v.internal_note = body.internal_note
    for item in body.evidence or []:
        _cite(s, r, item, visit_id=v.id)
    _touch(s, r)
    events.record(s, r, "VISIT_DONE", frm=r.status, to=r.status, visit_id=v.id, done_on=v.done_on.isoformat())
    return v


def cancel_visit(s: Session, ctx, r: ServiceRequest, visit_id: str, reason: str, if_match: int | None) -> ServiceVisit:
    access.for_write(s, ctx, r, "warranty.service.resolve", if_match)
    _owner(ctx, r)
    access.state(r, *(x for x in V.OPEN_STATES if x != V.RESOLVED))
    v = _visit(s, r, visit_id)
    if v.status != "PLANNED" or v.cycle != r.cycle:
        raise ApiError(
            409, "INVALID_STATE", f"Visit {v.visit_no} is {v.status.lower()} or belongs to an earlier cycle."
        )
    v.status, v.cancel_reason = "CANCELLED", _text(reason, "reason", "Say why the visit is cancelled")
    _touch(s, r)
    events.record(s, r, "VISIT_CANCELLED", frm=r.status, to=r.status, visit_id=v.id)
    return v


def _cite(s: Session, r: ServiceRequest, item, *, visit_id: str | None = None,
          resolution_id: str | None = None) -> ServiceEvidence:  # fmt: skip
    from veda.modules.attachments import service as att
    from veda.modules.attachments.models import Attachment

    a = s.get(Attachment, item.attachment_id)
    if a is None or a.lead_id != r.lead_id or not att.is_available(a):
        raise _invalid("attachment_id", "NOT_AVAILABLE", "Evidence must be a scanned, available attachment of this "
                       "customer's home.")  # fmt: skip
    if item.customer_visible and (a.visibility_code != "STANDARD" or not (item.caption or "").strip()):
        raise _invalid("customer_visible", "NOT_SHAREABLE", "Only a non-internal attachment with a customer caption "
                       "can be shown to the customer.")  # fmt: skip
    existing = s.execute(sa.select(ServiceEvidence).where(ServiceEvidence.request_id == r.id,
                                                          ServiceEvidence.attachment_id == a.id,
                                                          ServiceEvidence.is_deleted == sa.false())).scalar_one_or_none()  # fmt: skip
    if existing is not None:
        if (bool(item.customer_visible), (item.caption or "").strip() or None) != (existing.customer_visible,
                                                                                 existing.caption):  # fmt: skip
            raise ApiError(409, "EVIDENCE_ALREADY_CITED", "This attachment is already cited on the request as it was; "
                           "nothing was changed.")  # fmt: skip
        return existing
    ev = ServiceEvidence(request_id=r.id, lead_id=r.lead_id, attachment_id=a.id, visit_id=visit_id,
                         resolution_id=resolution_id, customer_visible=bool(item.customer_visible),
                         caption=(item.caption or "").strip() or None)  # fmt: skip
    s.add(ev)
    s.flush()
    events.record(s, r, "EVIDENCE_ADDED", frm=r.status, to=r.status, attachment_id=a.id,
                  customer_visible=ev.customer_visible)  # fmt: skip
    return ev


def add_evidence(s: Session, ctx, r: ServiceRequest, item, if_match: int | None) -> ServiceEvidence:
    access.for_write(s, ctx, r, "warranty.service.resolve", if_match)
    access.state(r, *V.OPEN_STATES)
    ev = _cite(s, r, item)
    _touch(s, r)
    return ev


def resolve(s: Session, ctx, r: ServiceRequest, body, if_match: int | None) -> ServiceResolution:
    access.for_write(s, ctx, r, "warranty.service.resolve", if_match)
    _owner(ctx, r)
    access.state(r, V.IN_PROGRESS)
    latest = latest_assessment(s, r)
    if latest is None or latest.outcome != V.COVERED:
        raise ApiError(409, "COVERAGE_NOT_DECIDED", "Only a request decided as covered is resolved as warranty service; "
                       "close it with its reason otherwise.")  # fmt: skip
    since = max(x for x in (latest.created_on, last_rejection(s, r)) if x is not None)
    if not done_since(s, r, "SERVICE", since):
        raise ApiError(409, "SERVICE_NOT_RECORDED", "Record the service visit for this decision (what was done) before "
                       "resolving; earlier visits do not count.")  # fmt: skip
    if pending_resolution(s, r) is not None:
        raise ApiError(409, "INVALID_STATE", "A resolution is already waiting for verification.")
    res = ServiceResolution(request_id=r.id, lead_id=r.lead_id, cycle=r.cycle,
                            summary=_text(body.summary, "summary", "Tell the customer what was done", 10),
                            internal_note=(body.internal_note or "").strip() or None, resolved_by=ctx.user.id,
                            resolved_on=db.tx_time(s), outcome="PENDING")  # fmt: skip
    s.add(res)
    s.flush()
    for item in body.evidence or []:
        _cite(s, r, item, resolution_id=res.id)
    r.status = V.RESOLVED
    _touch(s, r)
    events.record(s, r, "RESOLVED", frm=V.IN_PROGRESS, to=V.RESOLVED, resolution_id=res.id, cycle=r.cycle)
    events.customer(s, r, events.RESOLVED, resolution_id=res.id)
    return res


# --- verification and closure ------------------------------------------------------------------------------------------
def _close(s: Session, r: ServiceRequest, code: str, *, verified_by: str | None = None) -> None:
    for v in visits(s, r):  # a closed request keeps no planned visit (review M1)
        if v.status == "PLANNED":
            v.status, v.cancel_reason = "CANCELLED", "The request was closed."
            events.record(s, r, "VISIT_CANCELLED", frm=r.status, to=r.status, visit_id=v.id)
    frm = r.status
    r.status, r.closure_code, r.closed_on, r.verified_by_kind = V.CLOSED, code, db.tx_time(s), verified_by
    r.return_state = None
    _touch(s, r)
    events.record(s, r, "CLOSED", frm=frm, to=V.CLOSED, closure_code=code, verified_by=verified_by)


def confirm(s: Session, r: ServiceRequest, account_id: str) -> tuple[ServiceRequest, bool]:
    """The customer confirms the resolution. Repeating it after it was recorded changes nothing."""
    access.lock(s, r)
    access.lead_open(s, r.lead_id)
    if r.status == V.CLOSED and r.closure_code == "SERVICED" and r.verified_by_kind == "CUSTOMER":
        return r, False
    access.state(r, V.RESOLVED)
    res = pending_resolution(s, r)
    assert res is not None  # RESOLVED always has one (resolve writes it with the state)
    res.outcome, res.decided_on, res.decided_account_id = "CONFIRMED", db.tx_time(s), account_id
    events.record(s, r, "VERIFIED", frm=V.RESOLVED, to=V.RESOLVED, account_id=account_id, resolution_id=res.id,
                  verified_by="CUSTOMER")  # fmt: skip
    _close(s, r, "SERVICED", verified_by="CUSTOMER")
    return r, True


def reject(s: Session, r: ServiceRequest, account_id: str, reason: str) -> ServiceRequest:
    access.lock(s, r)
    access.lead_open(s, r.lead_id)
    access.state(r, V.RESOLVED)
    if r.rejections >= V.MAX_REJECTIONS:
        raise ApiError(409, "REJECTION_LIMIT_REACHED", "Please speak to your Veda Spaces contact: we will check it with "
                       "you directly.")  # fmt: skip
    res = pending_resolution(s, r)
    assert res is not None
    n = note(s, r, "REJECTION", "CUSTOMER", _text(reason, "reason", "Tell us what is still not right", 10), account_id)
    res.outcome, res.decided_on, res.decided_account_id = "REJECTED", db.tx_time(s), account_id
    r.rejections += 1
    r.status = V.IN_PROGRESS
    _touch(s, r)
    events.record(s, r, "RESOLUTION_REJECTED", frm=V.RESOLVED, to=V.IN_PROGRESS, account_id=account_id,
                  resolution_id=res.id, note_id=n.id)  # fmt: skip
    events.staff(s, r, events.REJECTED)
    return r


def verify(s: Session, ctx, r: ServiceRequest, if_match: int | None) -> ServiceRequest:
    access.for_write(s, ctx, r, "warranty.service.verify", if_match)
    access.state(r, V.RESOLVED)
    res = pending_resolution(s, r)
    assert res is not None
    if res.resolved_by == ctx.user.id:
        raise ApiError(403, "SEPARATION_OF_DUTIES", "A resolution is verified by someone other than the person who "
                       "resolved it.")  # fmt: skip
    res.outcome, res.decided_on, res.decided_by = "VERIFIED", db.tx_time(s), ctx.user.id
    events.record(s, r, "VERIFIED", frm=V.RESOLVED, to=V.RESOLVED, resolution_id=res.id, verified_by="STAFF")
    _close(s, r, "SERVICED", verified_by="STAFF")
    events.customer(s, r, events.CLOSED)
    return r


def withdraw(s: Session, r: ServiceRequest, *, account_id: str | None = None, ctx=None, if_match: int | None = None,
             reason: str | None = None) -> tuple[ServiceRequest, bool]:  # fmt: skip
    if ctx is not None:
        access.for_write(s, ctx, r, "warranty.service.triage", if_match)
    else:
        access.lock(s, r)
        access.lead_open(s, r.lead_id)
        if r.status == V.CLOSED and r.closure_code == "CUSTOMER_WITHDREW":
            return r, False  # a repeated withdrawal changes nothing
    access.state(r, *V.WITHDRAWABLE)
    said = (reason or "").strip()
    if said:
        note(s, r, "WITHDRAWAL", "CUSTOMER", said, account_id)
    events.record(s, r, "WITHDRAWN", frm=r.status, to=r.status, account_id=account_id)
    _close(s, r, "CUSTOMER_WITHDREW")
    if ctx is not None:
        events.customer(s, r, events.CLOSED)
    return r, True


def close(s: Session, ctx, r: ServiceRequest, body, if_match: int | None) -> ServiceRequest:
    access.for_write(s, ctx, r, "warranty.service.assess", if_match)
    access.state(r, *(x for x in V.OPEN_STATES if x != V.RESOLVED))
    code = body.closure_code
    explanation = _text(body.explanation, "explanation", "Explain the closure to the customer", 10)
    latest = latest_assessment(s, r)
    if code == "DUPLICATE":
        dup = _same_property(s, r.property_id, body.duplicate_of_id, "duplicate_of_id")
        if dup is None or dup == r.id:
            raise _invalid("duplicate_of_id", "REQUIRED", "Say which request of this home it duplicates.")
        r.duplicate_of_id = dup
    elif code == "NOT_COVERED":
        if latest is None or latest.outcome not in (V.NOT_COVERED, V.OUTSIDE_WARRANTY_PERIOD) \
                or latest.service_class != V.NOT_SERVICEABLE:  # fmt: skip
            raise ApiError(
                409, "ASSESSMENT_REQUIRED", "Close as not covered only after a coverage decision that says so."
            )
    elif code == "REFERRED_TO_MANUFACTURER":
        if latest is None or latest.outcome != V.MANUFACTURER_WARRANTY:
            raise ApiError(409, "ASSESSMENT_REQUIRED", "Refer to the manufacturer only after a coverage decision that "
                           "says so.")  # fmt: skip
    elif code == "CHARGEABLE_NOT_AGREED":
        if r.status != V.AWAITING_COMMERCIAL_AGREEMENT:
            raise ApiError(
                409, "ASSESSMENT_REQUIRED", "Only a request waiting for a commercial agreement closes this way."
            )
    elif code == "CANNOT_SERVICE":
        _text(body.internal_reason, "internal_reason", "Record why it cannot be serviced", 10)
    if code == "CHARGEABLE_NOT_AGREED" or code == "CANNOT_SERVICE" or body.internal_reason:
        if body.internal_reason:
            note(s, r, "INTERNAL", "INTERNAL", body.internal_reason.strip())
    note(s, r, "CLOSURE", "CUSTOMER", explanation)
    _close(s, r, code)
    events.customer(s, r, events.CLOSED)
    return r


def reopen(s: Session, ctx, r: ServiceRequest, reason: str, if_match: int | None) -> ServiceRequest:
    access.for_write(s, ctx, r, "warranty.service.verify", if_match)
    access.state(r, V.CLOSED)
    n = note(s, r, "REOPEN", "INTERNAL", _text(reason, "reason", "Say why the request is reopened", 10))
    previous = r.closure_code
    r.cycle += 1
    r.status, r.closure_code, r.closed_on, r.verified_by_kind, r.service_class = V.TRIAGED, None, None, None, None
    r.duplicate_of_id = None
    _touch(s, r)
    events.record(s, r, "REOPENED", frm=V.CLOSED, to=V.TRIAGED, previous_closure=previous, cycle=r.cycle, note_id=n.id)
    return r
