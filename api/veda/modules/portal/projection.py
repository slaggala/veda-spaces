"""What the customer sees (CPP-004 … CPP-010): customer-authorised, customer-safe views over existing sources of truth.

Authorisation first: every view starts from the account's ACTIVE access rows (``identity.active_access``) and reaches a
property or a quotation only through its lead. A row outside them answers 404, the same as a row that does not exist,
so a guessed identifier discloses nothing.

Nothing here invents information. Each value comes from the module that owns it:

- the enquiry and its consultant: CRM ``lead`` (the consultant by name only);
- the place: MTQ ``property``; the site visit and measurement: ``measurement_visit`` and ``measurement_set`` (states and
  dates only; no measurement is shown);
- design and scope: whether a scope is being prepared or confirmed (``scope.status``), nothing of its content;
- the quotation: only versions issued to the customer, through the CQX customer-safe projection of the frozen,
  digest-verified document (``customer_proposal.projection.build``) and the CQX customer state;
- commitments, responsibilities and contacts: the Customer Promise information frozen in that issued quotation;
- progress after approval: the Project Lifecycle, only while its own flag is on and a project exists, through the
  classification allow-list (stage, its Customer Promise stage, customer actions). Otherwise those steps are "not yet
  available"; the portal never reads, sets or bypasses that flag;
- payments, invoices and receipts: Project Commercials' customer projection (``commercials.customer``), only while its
  own flag is on and the property has a commercial record; its Action Required items join this page's;
- delivery (work, quality checks, snags, the customer's own reports, handover): the Project Lifecycle's customer-safe
  delivery view (``project.delivery``), only while VEDA_PROJECT_DELIVERY_PORTAL_ENABLED and the lifecycle's flag are
  on; a handover summary waiting for the customer joins Action Required.

Estimates, BOQs, rates, margins, staff notes, internal states and staff identities beyond the assigned consultant's
name are never read into a customer view. The only digest a customer sees is the one the CQX projection itself carries
(the frozen document's, which the secure link uses to bind a decision to what was shown).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock, db
from veda.kernel.errors import ApiError, not_found
from veda.modules.crm.leads.models import Lead
from veda.modules.customer_proposal import grants as cqx_grants
from veda.modules.customer_proposal import journey as cqx_journey
from veda.modules.customer_proposal import projection as cqx
from veda.modules.mtq.models import MeasurementSet, MeasurementVisit, Property
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import Quotation, Scope
from veda.platform.identity.models import User

from . import identity
from . import vocab as V

# The customer state of a quotation version (CQX ``proposal_state``) in the portal's words.
QUOTATION_STATES = {
    "OPEN": (V.ACTION_REQUIRED, "Awaiting your decision"),
    "ACCEPTED": (V.COMPLETED, "Accepted"),
    "DECLINED": (V.INFORMATION, "Declined"),
    "EXPIRED": (V.INFORMATION, "No longer valid"),
    "SUPERSEDED": (V.INFORMATION, "Replaced by a newer version"),
    "UNAVAILABLE": (V.NOT_YET_AVAILABLE, "Not available right now"),
}
# Customer Promise stage of the Project Lifecycle → the portal's journey step after approval.
PROJECT_STEP = {
    "PROPOSAL_ACCEPTED": "execution", "VEDA_CONFIRMATION": "execution", "SCOPE_DESIGN_FINALISATION": "execution",
    "PRODUCTION_READINESS": "execution", "SITE_READINESS": "execution", "INSTALLATION": "execution",
    "JOINT_INSPECTION": "quality", "HANDOVER": "handover",
}  # fmt: skip
STEPS = (
    ("consultation", "Consultation"),
    ("site_measurement", "Site measurement"),
    ("design_scope", "Design and scope"),
    ("quotation", "Your quotation"),
    ("approval", "Your approval"),
    ("execution", "Execution"),
    ("quality", "Quality checks"),
    ("handover", "Handover"),
)
NOT_IN_PORTAL = "Progress for this stage is not shown in your portal yet. Your Veda Spaces contact can tell you more."


# --- authorisation ------------------------------------------------------------------------------------------------------
def leads(s: Session, account_id: str) -> dict[str, tuple[Lead, Any]]:
    """lead id → (lead, access) for every ACTIVE access of the account."""
    out = {}
    for a in identity.active_access(s, account_id):
        lead = s.get(Lead, a.lead_id)
        if lead is not None:
            out[lead.id] = (lead, a)
    return out


def property_for(s: Session, account_id: str, property_id: str) -> tuple[Property, Lead]:
    allowed = leads(s, account_id)
    prop = s.get(Property, property_id)
    if prop is None or prop.is_deleted or prop.lead_id not in allowed:
        raise not_found()
    return prop, allowed[prop.lead_id][0]


def quotation_for(s: Session, account_id: str, quotation_id: str) -> Quotation:
    q = s.get(Quotation, quotation_id)
    if q is None or q.is_deleted or q.lead_id not in leads(s, account_id) or not _visible(q):
        raise not_found()
    prop = s.get(Property, q.property_id)
    if prop is None or prop.is_deleted:
        raise not_found()
    return q


def _visible(q: Quotation) -> bool:
    """Issued to the customer (a frozen document exists): never a draft, internal review or internal approval."""
    return q.status in V.CUSTOMER_VISIBLE_QUOTATIONS and (q.snapshot is not None or q.issued_html is not None)


# --- shared pieces -----------------------------------------------------------------------------------------------------
def _day(value) -> str | None:
    return value.isoformat() if value else None


def _when(value) -> str | None:
    return clock.to_rfc3339(value) if value else None


def visible_quotations(s: Session, prop: Property) -> list[Quotation]:
    rows = s.execute(sa.select(Quotation).where(Quotation.property_id == prop.id, Quotation.is_deleted == sa.false(),
                                                Quotation.status.in_(V.CUSTOMER_VISIBLE_QUOTATIONS))
                     .order_by(Quotation.quotation_number, Quotation.variation_no, Quotation.version_no)).scalars()  # fmt: skip
    return [q for q in rows if _visible(q)]


def _cache(s: Session) -> dict[tuple[str, str], Any]:
    """One request's memo of quotation states and projections (each is computed once, however many views use it)."""
    return s.info.setdefault("portal_projection_cache", {})


def _state(s: Session, q: Quotation) -> str:
    key = ("state", q.id)
    if key not in _cache(s):
        _cache(s)[key] = cqx_grants.proposal_state(s, q)
    return _cache(s)[key]


def _proposal(s: Session, q: Quotation) -> dict[str, Any] | None:
    """The CQX customer-safe projection of the frozen document, or None when it does not verify (never shown then)."""
    key = ("proposal", q.id)
    if key not in _cache(s):
        try:
            _cache(s)[key] = cqx.build(s, q)
        except ApiError:
            _cache(s)[key] = None
    return _cache(s)[key]


def quotation_summary(s: Session, q: Quotation, proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    state = _state(s, q)
    if proposal is None:
        proposal = _proposal(s, q)
    if proposal is None:  # the frozen document no longer verifies: nothing of it is shown
        state = "UNAVAILABLE"
    kind, label = QUOTATION_STATES[state]
    p = proposal or {}
    days_left = None
    if state == "OPEN" and q.valid_until is not None:
        days_left = (q.valid_until - db.tx_time(s).date()).days
    return {
        "id": q.id, "reference": p.get("reference") or quotations.number_label(q),
        "title": p.get("title") or ("Variation" if q.variation_no else "Quotation"),
        "kind": "VARIATION" if q.variation_no else "QUOTATION", "version_no": q.version_no,
        "state": state, "status": kind, "status_label": label,
        "issued_on": p.get("issued_on"), "valid_until": _day(q.valid_until), "days_left": days_left,
        "total": (p.get("summary") or {}).get("total"), "currency": (p.get("summary") or {}).get("currency"),
    }  # fmt: skip


def _relevant(s: Session, rows: list[Quotation]) -> Quotation | None:
    """The quotation that matters now: an open one awaiting the customer, else the accepted one, else the latest."""
    heads = [q for q in rows if _state(s, q) != "SUPERSEDED"]
    for wanted in ("OPEN", "ACCEPTED"):
        found = [q for q in heads if _state(s, q) == wanted]
        if found:
            return sorted(found, key=lambda q: (q.variation_no == 0, q.issued_on or q.created_on))[-1]
    return max(rows, key=lambda q: q.issued_on or q.created_on) if rows else None


def contact(s: Session, lead: Lead, proposal: dict[str, Any] | None) -> dict[str, Any] | None:
    """The business contact approved for customers in the issued quotation; else the assigned consultant's name only."""
    frozen = ((proposal or {}).get("information") or {}).get("contacts", {}).get("quotation")
    if frozen:
        return {"source": "QUOTATION", "name": frozen.get("display_name"), "role": frozen.get("role"),
                "phone": frozen.get("phone"), "email": frozen.get("email"), "hours": frozen.get("hours")}  # fmt: skip
    if lead.assigned_to:
        u = s.get(User, lead.assigned_to)
        if u is not None and u.status == "ACTIVE":
            return {"source": "CONSULTANT", "name": u.display_name or u.full_name, "role": None, "phone": None,
                    "email": None, "hours": None}  # fmt: skip
    return None


# --- the journey -------------------------------------------------------------------------------------------------------
def _step(key: str, state: str, detail: str, when: str | None = None) -> dict[str, Any]:
    return {"key": key, "label": dict(STEPS)[key], "state": state, "detail": detail, "date": when}


def _project(s: Session, prop: Property):
    """The property's project, only while the Project Lifecycle is enabled (its own flag; never changed here)."""
    if not settings().project_lifecycle_enabled:
        return None
    from veda.modules.project.models import Project

    return s.execute(sa.select(Project).where(Project.property_id == prop.id, Project.is_deleted == sa.false())
                     ).scalars().first()  # fmt: skip


def journey(s: Session, lead: Lead, prop: Property, rows: list[Quotation], project,
            proposal: dict[str, Any] | None) -> list[dict[str, Any]]:  # fmt: skip
    today = db.tx_time(s).date()
    visits = list(s.execute(sa.select(MeasurementVisit).where(MeasurementVisit.property_id == prop.id,
                                                              MeasurementVisit.is_deleted == sa.false())
                            .order_by(MeasurementVisit.created_on)).scalars())  # fmt: skip
    sets = [m.status for m in s.execute(sa.select(MeasurementSet).where(MeasurementSet.property_id == prop.id,
                                                                        MeasurementSet.is_deleted == sa.false())).scalars()]  # fmt: skip
    scopes = [x for (x,) in s.execute(sa.select(Scope.status).where(Scope.property_id == prop.id,
                                                                    Scope.is_deleted == sa.false()))]  # fmt: skip
    states = {q.id: _state(s, q) for q in rows}
    issued = bool(rows)
    out = [_step("consultation", V.COMPLETED if lead.status != "NEW" or visits or issued else V.IN_PROGRESS,
                 "We have your enquiry." if lead.status != "NEW" or visits or issued
                 else "We have your enquiry and will be in touch.")]  # fmt: skip

    done = [v for v in visits if v.status == "COMPLETED"]
    live = [v for v in visits if v.status in ("SCHEDULED", "IN_PROGRESS")]
    if "VERIFIED" in sets:
        out.append(_step("site_measurement", V.COMPLETED, "Your site has been measured and the measurements checked.",
                         _day(done[-1].completed_on.date()) if done and done[-1].completed_on else None))  # fmt: skip
    elif any(v.status == "IN_PROGRESS" for v in live) or "SUBMITTED" in sets or done:
        out.append(_step("site_measurement", V.IN_PROGRESS, "Your site has been visited; the measurements are being "
                         "checked."))  # fmt: skip
    elif live and live[-1].scheduled_start_on:
        out.append(_step("site_measurement", V.UPCOMING, "Your site visit is scheduled.",
                         _when(live[-1].scheduled_start_on)))  # fmt: skip
    else:
        out.append(_step("site_measurement", V.UPCOMING, "Your site visit has not been scheduled yet."))

    if issued or "CONFIRMED" in scopes:
        out.append(_step("design_scope", V.COMPLETED, "The scope of work for your home has been prepared."))
    elif "DRAFT" in scopes:
        out.append(_step("design_scope", V.IN_PROGRESS, "We are preparing the scope of work for your home."))
    else:
        out.append(_step("design_scope", V.UPCOMING, "The scope of work is prepared after your site is measured."))

    base = [q for q in rows if q.variation_no == 0]
    if issued:
        latest = max(rows, key=lambda q: q.issued_on or q.created_on)
        out.append(_step("quotation", V.COMPLETED, "Your quotation has been shared with you.",
                         _day((latest.issued_on or latest.created_on).date())))  # fmt: skip
    else:
        out.append(_step("quotation", V.UPCOMING, "Your quotation will appear here once Veda Spaces issues it."))

    base_states = [states[q.id] for q in base]
    if "ACCEPTED" in base_states:
        accepted = next(q for q in base if states[q.id] == "ACCEPTED")
        out.append(_step("approval", V.COMPLETED, "You accepted your quotation.",
                         _day(accepted.decided_on.date()) if accepted.decided_on else None))  # fmt: skip
    elif "OPEN" in base_states:
        out.append(_step("approval", V.ACTION_REQUIRED, "Your quotation is waiting for your decision."))
    elif "DECLINED" in base_states:
        out.append(_step("approval", V.INFORMATION, "You declined the quotation."))
    elif base_states:
        out.append(_step("approval", V.INFORMATION, "Your quotation is no longer open for a decision."))
    else:
        out.append(_step("approval", V.UPCOMING, "Once you have your quotation, you decide here."))

    out += _project_steps(s, project, proposal, today)
    return out


def _project_steps(s: Session, project, proposal: dict[str, Any] | None, today: date) -> list[dict[str, Any]]:
    if project is None:
        return [_step(k, V.NOT_YET_AVAILABLE, NOT_IN_PORTAL) for k in ("execution", "quality", "handover")]
    from veda.modules.project import lifecycle

    d = lifecycle.get(project.lifecycle_version)
    current = PROJECT_STEP[d.stage(project.stage_code).customer_stage]
    labels = {n.get("stage"): n.get("label") for n in ((proposal or {}).get("information") or {}).get("next_steps")
              or []}  # approved customer copy frozen in the quotation  # fmt: skip
    order = ("execution", "quality", "handover")
    out = []
    for key in order:
        if project.status == "HANDED_OVER" or order.index(key) < order.index(current):
            out.append(_step(key, V.COMPLETED, "Completed."))
        elif key == current:
            stage_label = labels.get(d.stage(project.stage_code).customer_stage)
            out.append(_step(key, V.IN_PROGRESS, f"In progress: {stage_label}." if stage_label else "In progress."))
        else:
            out.append(_step(key, V.UPCOMING, "Not started yet."))
    if project.status == "HANDED_OVER":
        out[-1]["date"] = _day(project.handed_over_on.date()) if project.handed_over_on else None
    return out


def project_actions(s: Session, project) -> list[dict[str, Any]]:
    """Customer actions the project team recorded, through the classification allow-list (CUSTOMER_ACTION fields)."""
    if project is None:
        return []
    from veda.modules.project import classification
    from veda.modules.project import vocab as PV
    from veda.modules.project.models import ProjectBlocker, ProjectSiteReadiness

    assert classification.column_class("project_blocker", "customer_action") == classification.CUSTOMER_ACTION
    assert classification.column_class("project_site_readiness", "customer_action") == classification.CUSTOMER_ACTION
    out = []
    waiting_on_customer = tuple(x for x in PV.BLOCKER_OPEN if x != "WAITING_VEDA")
    for b in s.execute(sa.select(ProjectBlocker).where(ProjectBlocker.project_id == project.id,
                                                       ProjectBlocker.is_deleted == sa.false(),
                                                       ProjectBlocker.responsible_party == "CUSTOMER",
                                                       ProjectBlocker.status.in_(waiting_on_customer))
                       .order_by(ProjectBlocker.created_on)).scalars():  # fmt: skip
        if b.customer_action:
            out.append({"kind": "PROJECT_ACTION", "status": V.ACTION_REQUIRED, "title": "Something we need from you",
                        "text": b.customer_action, "due": _day(b.target_date)})  # fmt: skip
    for r in s.execute(sa.select(ProjectSiteReadiness).where(ProjectSiteReadiness.project_id == project.id,
                                                             ProjectSiteReadiness.is_deleted == sa.false(),
                                                             ProjectSiteReadiness.status == "CUSTOMER_ACTION_REQUIRED")
                       .order_by(ProjectSiteReadiness.item_code)).scalars():  # fmt: skip
        if r.customer_action:
            out.append({"kind": "SITE_READINESS", "status": V.ACTION_REQUIRED, "title": "Getting your site ready",
                        "text": r.customer_action, "due": _day(r.due_date)})  # fmt: skip
    return out


# --- views -------------------------------------------------------------------------------------------------------------
def _property_brief(prop: Property) -> dict[str, Any]:
    return {"reference": prop.property_number, "configuration": prop.configuration_label,
            "locality": prop.locality, "city": prop.city}  # fmt: skip


def _attention(s: Session, rows: list[Quotation], relevant: dict[str, Any] | None, project, journey_steps,
               lead: Lead, proposal) -> list[dict[str, Any]]:  # fmt: skip
    out: list[dict[str, Any]] = []
    for q in rows:
        if _state(s, q) == "OPEN":
            summary = quotation_summary(s, q, proposal if relevant and relevant["id"] == q.id else None)
            if summary["state"] != "OPEN":
                continue
            out.append({"kind": "QUOTATION_DECISION", "status": V.ACTION_REQUIRED,
                        "title": f"Review your {summary['title'].lower()} and tell us your decision",
                        "text": "To accept, decline or ask a question, use the secure proposal link Veda Spaces sent "
                                "you, or speak to your Veda Spaces contact.",
                        "due": summary["valid_until"], "quotation_id": q.id})  # fmt: skip
    out += project_actions(s, project)
    visit = next((x for x in journey_steps if x["key"] == "site_measurement" and x["state"] == V.UPCOMING
                  and x["date"]), None)  # fmt: skip
    if visit:
        out.append({"kind": "SITE_VISIT", "status": V.UPCOMING, "title": "Your site visit", "text":
                    "Your site visit is scheduled.", "due": visit["date"]})  # fmt: skip
    return out


def _next_step(journey_steps: list[dict[str, Any]]) -> dict[str, Any] | None:
    for wanted in (V.ACTION_REQUIRED, V.IN_PROGRESS, V.UPCOMING):
        found = next((x for x in journey_steps if x["state"] == wanted), None)
        if found:
            return {"key": found["key"], "label": found["label"], "state": found["state"], "detail": found["detail"],
                    "date": found["date"]}  # fmt: skip
    return None


HEADLINES = {
    "consultation": "Your enquiry is with us.", "site_measurement": "Your site is being measured.",
    "design_scope": "We are preparing your scope of work.", "quotation": "Your quotation is ready.",
    "approval": "You have approved your quotation.", "execution": "Your project is under way.",
    "quality": "We are checking the quality of the work.", "handover": "Your home is ready for handover.",
}  # fmt: skip


def _headline(lead: Lead, journey_steps: list[dict[str, Any]]) -> str:
    if lead.status == "LOST":
        return "This enquiry is closed."
    steps = {x["key"]: x for x in journey_steps}
    if any(x["state"] == V.ACTION_REQUIRED for x in journey_steps):
        return "We are waiting for your decision."
    if steps["approval"]["state"] == V.INFORMATION:  # declined, or no longer open: say exactly that
        return steps["approval"]["detail"]
    if steps["handover"]["state"] == V.COMPLETED:
        return "Your home has been handed over."
    reached = [x for x in journey_steps if x["state"] in (V.COMPLETED, V.IN_PROGRESS)]
    return HEADLINES[reached[-1]["key"]] if reached else "Your enquiry has been received."


def property_view(s: Session, account_id: str, prop: Property, lead: Lead, *, full: bool) -> dict[str, Any]:
    rows = visible_quotations(s, prop)
    relevant_q = _relevant(s, rows)
    proposal = _proposal(s, relevant_q) if relevant_q is not None else None
    relevant = quotation_summary(s, relevant_q, proposal) if relevant_q is not None else None
    project = _project(s, prop)
    steps = journey(s, lead, prop, rows, project, proposal)
    attention = _attention(s, rows, relevant, project, steps, lead, proposal)
    from veda.modules.commercials import customer as commercials

    money = commercials.for_property(s, prop)
    if money and money.get("available"):
        attention = money["attention"] + attention
    from veda.modules.project import delivery as project_delivery

    delivery = project_delivery.view(s, account_id, prop.id)
    for dp in (delivery or {}).get("projects", []):
        pkg = dp.get("package") or {}
        if pkg.get("can_acknowledge"):
            attention = [{"kind": "HANDOVER_ACKNOWLEDGEMENT", "status": V.ACTION_REQUIRED,
                          "title": "Review your handover summary", "text": "Veda Spaces has prepared the summary of "
                          "what is being handed over. Please review it and confirm you have received it.",
                          "due": None}] + attention  # fmt: skip
    out: dict[str, Any] = {
        "id": prop.id, "property": _property_brief(prop), "enquiry": {"reference": lead.public_reference},
        "headline": _headline(lead, steps), "next_step": _next_step(steps),
        "attention_count": sum(1 for a in attention if a["status"] == V.ACTION_REQUIRED),
        "quotation": relevant, "contact": contact(s, lead, proposal),
        "project_tracking": project is not None,
        "payments": ({"available": True, "outstanding": money["summary"]["outstanding"],
                      "next_payment": money["summary"]["next_payment"]} if money and money.get("available")
                     else ({"available": False} if money else None)),
    }  # fmt: skip
    if not full:
        return out
    info = (proposal or {}).get("information") or {}
    out.update({
        "journey": steps,
        "attention": attention,
        "quotations": [quotation_summary(s, q) for q in rows if _state(s, q) != "SUPERSEDED"],
        "documents": [{"kind": "QUOTATION", **quotation_summary(s, q)} for q in reversed(rows)],
        "included": [{"title": r.get("title"), "kind": r.get("kind"), "included_count": r.get("included_count"),
                      "optional_count": r.get("optional_count"),
                      "items": [{"description": x.get("description"), "detail": x.get("detail"),
                                 "status": x.get("status"), "dimensions": x.get("dimensions")} for x in r.get("lines") or []]}
                     for r in (proposal or {}).get("rooms") or []] if proposal else None,  # fmt: skip
        "commitments": {
            "source": relevant["reference"] if relevant else None,
            "inclusions": info.get("project_inclusions"), "warranty": (proposal or {}).get("warranty") or None,
            "manufacturer_warranty_note": info.get("manufacturer_warranty_note"),
            "handover": info.get("handover"), "care": info.get("care"), "next_steps": info.get("next_steps"),
            "payment_schedule": (proposal or {}).get("payment_schedule") or None,
            "payment_safety": info.get("payment_safety"),
        } if proposal else None,
        "responsibilities": {"client": info.get("client_responsibilities"), "site_readiness": info.get("site_readiness")}
        if proposal else None,
        "support": {"contacts": (info.get("contacts") or {}).get("support") or [],
                    "escalation": info.get("support_escalation")} if proposal else None,
        "commercials": ({k: v for k, v in money.items() if k != "attention"} if money else None),
        "delivery": delivery,
    })  # fmt: skip
    if money and money.get("available"):
        out["documents"] = ([{"kind": "INVOICE", **i} for i in money["invoices"]]
                            + [{"kind": "RECEIPT", **r} for r in money["receipts"]] + out["documents"])  # fmt: skip
    return out


def home(s: Session, account) -> dict[str, Any]:
    enquiries = []
    for lead, access in leads(s, account.id).values():
        props = s.execute(sa.select(Property).where(Property.lead_id == lead.id, Property.is_deleted == sa.false())
                          .order_by(Property.created_on)).scalars().all()  # fmt: skip
        enquiries.append({
            "reference": lead.public_reference, "relationship": access.relationship,
            "closed": lead.status == "LOST",
            "properties": [property_view(s, account.id, p, lead, full=False) for p in props],
        })  # fmt: skip
    from veda.modules.project import delivery as project_delivery

    return {"customer": {"name": account.display_name}, "enquiries": enquiries,
            "project_tracking_available": bool(settings().project_lifecycle_enabled),
            "delivery_available": project_delivery.enabled()}  # fmt: skip


def quotation_page(s: Session, q: Quotation) -> dict[str, Any]:
    """The CQX customer page model of one issued version, read-only: no link, no action, no interaction."""
    proposal = cqx.build(s, q)  # refuses (409) when the frozen document no longer verifies
    state = _state(s, q)
    notices = []
    if state in cqx_journey.STATE_NOTICES:
        notices.append({"code": state, "message": cqx_journey.STATE_NOTICES[state]})
    if state == "OPEN":
        notices.append({"code": "DECIDE_BY_LINK", "message": "To accept, decline or ask a question, use the secure "
                        "proposal link Veda Spaces sent you, or speak to your Veda Spaces contact."})  # fmt: skip
    return {"state": state, "proposal": proposal, "history": cqx_journey.history(s, q),
            "capabilities": {"interaction": False, "acceptance": False}, "notices": notices, "actions": [],
            "summary": quotation_summary(s, q, proposal)}  # fmt: skip
