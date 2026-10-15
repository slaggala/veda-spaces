"""Booking an accepted quotation as a project (PLB-01, PLB-02, PLB-46).

A project exists only because a customer legitimately accepted a base quotation. ``eligibility`` lists every reason a
quotation cannot be booked; ``create`` refuses on any of them:

- not ACCEPTED (a draft, one in internal review, approved, issued and undecided, rejected, expired or superseded);
- a variation (a variation updates the baseline of the project its chain already has; it never starts one);
- a property or customer context that does not match the quotation's (the request names the property it books for);
- acceptance without its authoritative record: the decision fields, the B4 ACCEPTED event bound to the frozen
  baseline digest and method, and, for a customer's digital decision, the CQX acceptance evidence for that version;
- integrity: the frozen document, its HTML or the frozen accepted baseline no longer matching their digests;
- a chain that already has a project (exactly one project per accepted baseline);
- an erased customer record.

Creation is transaction-safe and idempotent: it takes the property lock (every commercial transition of the property
takes it), re-reads the quotation under it and checks for an existing project before inserting; the unique indexes on
the source quotation and the chain refuse any duplicate the lock did not; a retry with the same Idempotency-Key
replays the first response, and a new request for a booked chain answers 409 PROJECT_EXISTS with the project's id.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db, sequences
from veda.kernel.errors import ApiError, not_found
from veda.modules.crm.leads.models import Lead
from veda.modules.mtq import scope as site_scope
from veda.modules.mtq import sets as site_sets
from veda.modules.mtq.models import Property
from veda.modules.mtq_commercial.models import Quotation, QuotationEvent

from . import baseline, events, lifecycle
from .models import Project, ProjectChecklistItem, ProjectSiteReadiness, ProjectStage

PERMISSION = "project.create_from_acceptance"
SEQUENCE = "PROJECT"


def _p(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **extra}


def acceptance_evidence(s: Session, q: Quotation) -> list[dict[str, Any]]:
    out = []
    if not (q.decision_method and q.decided_on and q.decision_recorded_by and q.accepted_total_minor is not None
            and q.accepted_baseline_sha256):  # fmt: skip
        out.append(_p("ACCEPTANCE_EVIDENCE_MISSING", "The acceptance has no complete decision record."))
        return out
    recorded = [e for e in s.execute(sa.select(QuotationEvent).where(QuotationEvent.quotation_id == q.id,
                                                                     QuotationEvent.event_code == "ACCEPTED")).scalars()
                if (e.detail or {}).get("accepted_baseline_sha256") == q.accepted_baseline_sha256
                and (e.detail or {}).get("method") == q.decision_method]  # fmt: skip
    if len(recorded) != 1:
        out.append(_p("ACCEPTANCE_EVIDENCE_MISSING", "The acceptance was not recorded by the quotation decision "
                      "service for this frozen baseline."))  # fmt: skip
    if q.decision_method == "CUSTOMER_DIGITAL":
        from veda.modules.customer_proposal.models import QuotationAcceptanceEvidence as Evidence

        ev = s.execute(sa.select(Evidence).where(Evidence.quotation_id == q.id)).scalar_one_or_none()
        if ev is None or ev.decision != "ACCEPTED" or ev.snapshot_sha256 != q.snapshot_sha256:
            out.append(_p("ACCEPTANCE_EVIDENCE_MISSING", "The customer's digital acceptance has no evidence for this "
                          "version."))  # fmt: skip
    return out


def eligibility(s: Session, q: Quotation, property_id: str | None = None) -> list[dict[str, Any]]:
    """Every reason ``q`` cannot be booked as a project (empty: it can)."""
    from veda.modules.mtq_commercial import rendering

    out: list[dict[str, Any]] = []
    if q.status != "ACCEPTED":
        out.append(_p("QUOTATION_NOT_ACCEPTED", f"The quotation is {q.status.lower().replace('_', ' ')}; only an "
                      "accepted quotation is booked as a project.", status=q.status))  # fmt: skip
    if q.quotation_kind != "BASE":
        out.append(_p("QUOTATION_IS_VARIATION", "A variation updates the baseline of its project; it never starts "
                      "one."))  # fmt: skip
    prop = s.get(Property, q.property_id)
    if property_id is not None and property_id != q.property_id:
        out.append(_p("CONTEXT_MISMATCH", "The quotation belongs to another property."))
    if prop is None or prop.lead_id != q.lead_id:
        out.append(_p("CONTEXT_MISMATCH", "The quotation's property and customer record do not match."))
    lead = s.get(Lead, q.lead_id)
    if lead is None or lead.is_deleted or lead.anonymized_on is not None:
        out.append(_p("LEAD_ERASED", "The customer record was erased."))
    if q.status == "ACCEPTED":
        out += acceptance_evidence(s, q)
        if not rendering.integrity(q):
            out.append(_p("SNAPSHOT_INTEGRITY_FAILED", "The frozen quotation no longer matches its sealed digests."))
        if not baseline.accepted_baseline_verifies(q):
            out.append(_p("BASELINE_INTEGRITY_FAILED", "The frozen accepted baseline no longer matches its digest."))
    existing = s.execute(sa.select(Project).where(Project.quotation_number == q.quotation_number)).scalar_one_or_none()
    if existing is not None:
        out.append(_p("PROJECT_EXISTS", f"{q.quotation_number} is already booked as {existing.project_number}.",
                      project_id=existing.id))  # fmt: skip
    return out


def visible_quotation(s: Session, ctx, quotation_id: str) -> Quotation:
    """The quotation, if its lead is within the booking capability's scope (404 otherwise: existence not disclosed)."""
    q = s.execute(sa.select(Quotation).where(Quotation.id == quotation_id,
                                             site_scope.condition(ctx, PERMISSION, Quotation.lead_id))
                  ).scalar_one_or_none()  # fmt: skip
    if q is None:
        raise not_found()
    return q


def bookable(s: Session, ctx, limit: int = 50) -> list[tuple[Quotation, list[dict[str, Any]]]]:
    """Accepted base quotations in scope with no project yet (the booking queue), each with its eligibility."""
    booked = sa.select(Project.quotation_number)
    rows = s.execute(sa.select(Quotation).where(
        Quotation.status == "ACCEPTED", Quotation.quotation_kind == "BASE",
        Quotation.quotation_number.not_in(booked), site_scope.condition(ctx, PERMISSION, Quotation.lead_id),
    ).order_by(Quotation.decided_on.desc()).limit(limit)).scalars().all()  # fmt: skip
    return [(q, eligibility(s, q)) for q in rows]


def _seed_site_readiness(s: Session, p: Project, q: Quotation) -> int:
    """PLB-16: one observation per readiness item and customer responsibility the accepted quotation froze from the
    Customer Promise, referenced by code (the frozen text stays in the quotation). Each starts TO_BE_CONFIRMED: the
    quotation's statement is customer content, not an observation of this site."""
    info = (q.snapshot or {}).get("customer_information") or {}
    version = info.get("content_version")
    n = 0
    for kind, key in (("READINESS", "site_readiness"), ("RESPONSIBILITY", "client_responsibilities")):
        for item in info.get(key) or []:
            s.add(ProjectSiteReadiness(project_id=p.id, lead_id=p.lead_id, kind=kind, source="CUSTOMER_PROMISE",
                                       item_code=item["code"], category=item["category"],
                                       promise_content_version=version, status="TO_BE_CONFIRMED",
                                       responsible_party="TO_BE_CONFIRMED"))  # fmt: skip
            n += 1
    return n


def create(s: Session, ctx, quotation_id: str, property_id: str) -> Project:
    q = visible_quotation(s, ctx, quotation_id)
    site_scope.require_in_scope(s, ctx, q.lead_id, PERMISSION)
    site_sets.lock_property(s, q.property_id)
    s.refresh(q)
    found = eligibility(s, q, property_id)
    if found:
        exists = next((x for x in found if x["code"] == "PROJECT_EXISTS"), None)
        if exists is not None:
            raise ApiError(409, "PROJECT_EXISTS", exists["message"], extra={"project_id": exists["project_id"]})
        status = 422 if any(x["code"] in ("QUOTATION_IS_VARIATION", "CONTEXT_MISMATCH") for x in found) else 409
        raise ApiError(status, "NOT_BOOKABLE", f"{len(found)} reason(s) stop this quotation from being booked as a "
                       "project.", extra={"problems": found})  # fmt: skip
    d = lifecycle.current()
    now = db.tx_time(s)
    p = Project(project_number=sequences.next_number(s, SEQUENCE), lead_id=q.lead_id, property_id=q.property_id,
                source="ACCEPTED_QUOTATION", source_quotation_id=q.id, quotation_number=q.quotation_number,
                status="ACTIVE", stage_code=d.stages[0].code, stage_entered_on=now, lifecycle_version=d.version,
                lifecycle_sha256=d.sha256, baseline_seq=1)  # fmt: skip
    s.add(p)
    s.flush()
    for n, st in enumerate(d.stages, start=1):
        first = n == 1
        s.add(ProjectStage(project_id=p.id, lead_id=p.lead_id, stage_code=st.code, sequence_no=n,
                           status="ACTIVE" if first else "NOT_STARTED", entered_on=now if first else None,
                           entered_by=ctx.user.id if first else None))  # fmt: skip
        for item in st.checklist:
            s.add(ProjectChecklistItem(project_id=p.id, lead_id=p.lead_id, stage_code=st.code, item_code=item.code,
                                       state="OPEN"))  # fmt: skip
    seeded = _seed_site_readiness(s, p, q)
    events.record(s, p, "PROJECT_CREATED", stage=p.stage_code, to=p.stage_code, quotation_id=q.id,
                  quotation_number=q.quotation_number, lifecycle_version=d.version, lifecycle_sha256=d.sha256,
                  site_readiness_items=seeded)  # fmt: skip
    previous = None
    for accepted in baseline.accepted_chain(s, q.quotation_number):  # the base, then variations already accepted
        previous = baseline.append(s, p, accepted, previous)
        events.record(s, p, "BASELINE_RECORDED", stage=p.stage_code, baseline_id=previous.id,
                      baseline_seq=previous.sequence_no, kind=previous.kind, quotation_id=accepted.id,
                      baseline_sha256=previous.baseline_sha256)  # fmt: skip
    s.flush()
    return p
