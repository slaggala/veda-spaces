"""Fact gathering (SCA-005): the records behind a lead's sales progression, read in batches, never written.

For a set of leads this reads, with one query per source: staff-logged contact activities, the estimator link,
measurement visits, base quotations, proposal links and customer requests, and projects. The result feeds
``stages.derive`` and the pipeline projection. Money appears only as the quoted total of the latest issued base
quotation, and the projection releases it only to holders of ``quotation.read``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.modules.crm.leads.models import Lead, LeadActivity
from veda.modules.customer_proposal.models import CustomerProposalRequest, ProposalAccessGrant
from veda.modules.estimator.models import BudgetEstimate, BudgetEstimateLeadLink
from veda.modules.mtq.models import MeasurementVisit, Property
from veda.modules.mtq_commercial.models import Quotation
from veda.modules.project.models import Project

from .stages import Facts

CONTACT_TYPES = ("CALL", "WHATSAPP", "EMAIL", "MEETING")
LOGGED_TYPES = CONTACT_TYPES + ("SITE_VISIT",)
ISSUED_STATUSES = ("ISSUED", "ACCEPTED", "REJECTED", "EXPIRED", "SUPERSEDED")
REQUEST_WAITING_ON_STAFF = ("OPEN", "UNDER_REVIEW")
REQUEST_WAITING_ON_CUSTOMER = ("NEEDS_CLARIFICATION",)


@dataclass
class LeadRecords:
    """The raw facts for one lead (ids and dates for links; never customer text)."""

    contacted_on: datetime | None = None
    meeting_on: datetime | None = None
    site_visit_logged_on: datetime | None = None
    issued_any: bool = False  # any base version ever issued (ISSUED, ACCEPTED, REJECTED, EXPIRED, SUPERSEDED)
    estimate: dict | None = None  # {reference, created_on, expires_on}
    property_ids: list[str] = field(default_factory=list)
    visits: list[dict] = field(default_factory=list)  # {id, status, scheduled_start_on, completed_on, property_id}
    quotation: dict | None = (
        None  # the latest base quotation: {id, number, status, issued_on, valid_until, total_minor}
    )
    quotations: int = 0
    accepted: dict | None = None  # the accepted base quotation {id, number, decided_on, method}
    proposal: dict | None = None  # {shared_on, first_viewed_on, last_viewed_on, view_count, links}
    requests_waiting_on_staff: int = 0
    requests_waiting_on_customer: int = 0
    requests: int = 0
    project: dict | None = None  # {id, number, stage_code, status}

    def facts(self, lead: Lead, *, now: datetime) -> Facts:
        q = self.quotation
        issued = self.issued_any
        valid = (
            q is not None and q["status"] == "ISSUED" and (q["valid_until"] is None or q["valid_until"] >= now.date())
        )
        return Facts(
            lead_status=lead.status,
            assigned=lead.assigned_to is not None,
            next_follow_up_on=lead.next_follow_up_on,
            last_activity_on=lead.last_activity_on,
            contacted_activity=self.contacted_on is not None,
            meeting_done=self.meeting_on is not None,
            site_visit_logged=self.site_visit_logged_on is not None,
            consent_withdrawn=lead.consent_withdrawn_on is not None,
            estimate_linked=self.estimate is not None,
            visits=sum(1 for v in self.visits if v["status"] != "CANCELLED"),
            visits_completed=sum(1 for v in self.visits if v["status"] == "COMPLETED"),
            quotations=self.quotations,
            quotation_issued=issued,
            quotation_open=valid,
            quotation_accepted=self.accepted is not None,
            quotation_declined=self.accepted is None and q is not None and q["status"] == "REJECTED",
            proposal_shared=self.proposal is not None,
            proposal_opened=bool(self.proposal and self.proposal["first_viewed_on"]),
            customer_requests_open=self.requests_waiting_on_staff + self.requests_waiting_on_customer,
            customer_requests=self.requests,
            project=self.project is not None,
        )


def gather(s: Session, lead_ids: list[str]) -> dict[str, LeadRecords]:
    out: dict[str, LeadRecords] = {lid: LeadRecords() for lid in lead_ids}
    if not lead_ids:
        return out
    ids = list(lead_ids)

    # Staff-logged, completed contact activities (system rows are the other modules' own syncs, not a contact).
    rows = s.execute(
        sa.select(LeadActivity.lead_id, LeadActivity.activity_type, sa.func.min(LeadActivity.completed_on))
        .where(LeadActivity.lead_id.in_(ids), LeadActivity.activity_status == "COMPLETED",
               LeadActivity.is_system_generated == sa.false(), LeadActivity.activity_type.in_(LOGGED_TYPES))
        .group_by(LeadActivity.lead_id, LeadActivity.activity_type)
    ).all()  # fmt: skip
    for lead_id, kind, first in rows:
        r = out[lead_id]
        first = clock.ensure_utc(first) if first else None
        if kind == "SITE_VISIT":
            if first and (r.site_visit_logged_on is None or first < r.site_visit_logged_on):
                r.site_visit_logged_on = first
            continue
        if first and (r.contacted_on is None or first < r.contacted_on):
            r.contacted_on = first
        if kind == "MEETING" and first and (r.meeting_on is None or first < r.meeting_on):
            r.meeting_on = first

    estimate_rows = s.execute(
        sa.select(BudgetEstimateLeadLink.lead_id, BudgetEstimate.public_reference, BudgetEstimate.created_on,
                  BudgetEstimate.expires_on)
        .join(BudgetEstimate, BudgetEstimate.id == BudgetEstimateLeadLink.estimate_id)
        .where(BudgetEstimateLeadLink.lead_id.in_(ids))
        .order_by(BudgetEstimate.created_on)
    ).all()  # fmt: skip
    for lead_id, ref, created_on, expires_on in estimate_rows:
        out[lead_id].estimate = {"reference": ref, "created_on": clock.to_rfc3339(created_on),
                                 "expires_on": expires_on.isoformat() if expires_on else None}  # fmt: skip

    for lead_id, prop_id in s.execute(
        sa.select(Property.lead_id, Property.id).where(Property.lead_id.in_(ids)).order_by(Property.created_on)
    ).all():
        out[lead_id].property_ids.append(prop_id)

    for v in s.execute(
        sa.select(MeasurementVisit).where(MeasurementVisit.lead_id.in_(ids)).order_by(MeasurementVisit.created_on)
    ).scalars():
        out[v.lead_id].visits.append({"id": v.id, "visit_number": v.visit_number, "status": v.status,
                                      "scheduled_start_on": clock.to_rfc3339(v.scheduled_start_on),
                                      "completed_on": clock.to_rfc3339(v.completed_on), "property_id": v.property_id})  # fmt: skip

    for q in s.execute(
        sa.select(Quotation).where(Quotation.lead_id.in_(ids)).order_by(Quotation.created_on, Quotation.version_no)
    ).scalars():
        r = out[q.lead_id]
        r.quotations += 1
        if q.quotation_kind != "BASE":
            continue
        if q.status == "ACCEPTED":
            r.accepted = {"id": q.id, "quotation_number": q.quotation_number, "version_no": q.version_no,
                          "decided_on": clock.to_rfc3339(q.decided_on), "method": q.decision_method}  # fmt: skip
        if q.status in ISSUED_STATUSES:
            r.issued_any = True
        current = r.quotation
        # The base version that matters to the customer: an ACCEPTED one, else the ISSUED one, else the latest row
        # (a newer version in preparation never displaces the issued one the customer holds).
        rank = {"ACCEPTED": 3, "ISSUED": 2}.get(q.status, 1)
        if current is None or rank >= {"ACCEPTED": 3, "ISSUED": 2}.get(current["status"], 1):
            r.quotation = {"id": q.id, "quotation_number": q.quotation_number, "version_no": q.version_no,
                           "status": q.status, "issued_on": clock.to_rfc3339(q.issued_on), "valid_until": q.valid_until,
                           "total_minor": q.total_minor, "property_id": q.property_id}  # fmt: skip

    for g in s.execute(
        sa.select(ProposalAccessGrant)
        .where(ProposalAccessGrant.lead_id.in_(ids))
        .order_by(ProposalAccessGrant.created_on)
    ).scalars():
        r = out[g.lead_id]
        p = r.proposal or {"shared_on": clock.to_rfc3339(g.created_on), "first_viewed_on": None, "last_viewed_on": None,
                           "view_count": 0, "links": 0, "active_links": 0}  # fmt: skip
        p["links"] += 1
        p["active_links"] += 1 if g.status in ("CREATED", "ACTIVE") else 0
        p["view_count"] += g.view_count or 0
        if g.first_viewed_on and (
            p["first_viewed_on"] is None or clock.to_rfc3339(g.first_viewed_on) < p["first_viewed_on"]
        ):
            p["first_viewed_on"] = clock.to_rfc3339(g.first_viewed_on)
        if g.last_viewed_on and (
            p["last_viewed_on"] is None or clock.to_rfc3339(g.last_viewed_on) > p["last_viewed_on"]
        ):
            p["last_viewed_on"] = clock.to_rfc3339(g.last_viewed_on)
        r.proposal = p

    for lead_id, status, n in s.execute(
        sa.select(CustomerProposalRequest.lead_id, CustomerProposalRequest.status, sa.func.count())
        .where(CustomerProposalRequest.lead_id.in_(ids))
        .group_by(CustomerProposalRequest.lead_id, CustomerProposalRequest.status)
    ).all():
        r = out[lead_id]
        r.requests += n
        if status in REQUEST_WAITING_ON_STAFF:
            r.requests_waiting_on_staff += n
        elif status in REQUEST_WAITING_ON_CUSTOMER:
            r.requests_waiting_on_customer += n

    for pj in s.execute(sa.select(Project).where(Project.lead_id.in_(ids)).order_by(Project.created_on)).scalars():
        out[pj.lead_id].project = {"id": pj.id, "project_number": pj.project_number, "stage_code": pj.stage_code,
                                   "status": pj.status}  # fmt: skip
    return out
