"""The staff sales pipeline (SCA-006): one row per live lead, with its derived stage and the facts behind it.

A projection, never an entity: nothing is stored, and no row carries customer free text (the enquiry message, notes,
decision notes and internal comments stay in their own screens). The quoted amount appears only to a holder of
``quotation.read``; everyone else sees that it is withheld. Stage, attention and channel filters apply after
derivation over the leads in the actor's scope (at most ``SCAN_LIMIT`` most recent leads of the chosen status group),
so that a filter never changes what a stage means.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import field_error, validation_failed
from veda.modules.crm.leads.models import Lead
from veda.platform.identity.models import User
from veda.platform.lookups import service as lookups

from . import access, attribution, facts, stages
from .vocab import ATTENTION, ATTENTION_LABELS, BASIS_LABELS, CHANNEL_LABELS, CHANNELS, STAGE_LABELS, STAGES

SCAN_LIMIT = 500
OPEN = ("NEW", "CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION")
STATUS_GROUPS = {
    "open": OPEN,
    "won": ("WON",),
    "lost": ("LOST",),
    "closed": ("WON", "LOST"),
    "all": OPEN + ("WON", "LOST"),
}


def _user(s: Session, user_id: str | None, cache: dict) -> dict | None:
    if not user_id:
        return None
    if user_id not in cache:
        u = s.get(User, user_id, execution_options={"include_deleted": True})
        cache[user_id] = {"id": user_id, "display_name": (u.display_name or u.full_name) if u else None}
    return cache[user_id]


def row(s: Session, ctx, lead: Lead, rec: facts.LeadRecords, *, now: datetime, users: dict) -> dict:
    f = rec.facts(lead, now=now)
    p = stages.derive(f, now=now)
    source = lookups.value_ref(s, lead.source_id)
    ch = attribution.channel(source["code"] if source else None, lead.utm_source, lead.utm_medium, lead.referrer_url)
    may_see_amount = ctx.has("quotation.read")
    q = rec.quotation
    quoted = None
    if q is not None and q["status"] in facts.ISSUED_STATUSES and q["total_minor"] is not None:
        quoted = {"amount_minor": q["total_minor"], "currency": "INR"} if may_see_amount else {"withheld": True}
    elif lead.quoted_amount_minor is not None and q is None:
        quoted = (
            {"amount_minor": lead.quoted_amount_minor, "currency": lead.currency}
            if may_see_amount
            else {"withheld": True}
        )
    return {
        "lead": {
            "id": lead.id,
            "lead_number": lead.lead_number,
            "name": lead.name,
            "city": lead.city,
            "status": lead.status,
            "created_on": clock.to_rfc3339(lead.created_on),
        },  # fmt: skip
        "source": source,
        "channel": {"code": ch.code, "label": CHANNEL_LABELS[ch.code], "detail": ch.detail},
        "stage": {
            "code": p.stage,
            "label": STAGE_LABELS[p.stage],
            "basis": p.basis,
            "basis_label": BASIS_LABELS[p.basis],
            "claimed_without_record": p.claimed_without_record,
        },  # fmt: skip
        "facts": {
            "estimate": rec.estimate,
            "contacted_on": clock.to_rfc3339(rec.contacted_on),
            "consultation_on": clock.to_rfc3339(rec.meeting_on),
            "properties": rec.property_ids,
            "visits": rec.visits,
            "quotation": None
            if q is None
            else {k: v for k, v in q.items() if k != "total_minor"}
            | {"valid_until": q["valid_until"].isoformat() if q["valid_until"] else None},
            "quotations": rec.quotations,
            "accepted": rec.accepted,
            "proposal": rec.proposal,
            "customer_requests": {
                "total": rec.requests,
                "waiting_on_staff": rec.requests_waiting_on_staff,
                "waiting_on_customer": rec.requests_waiting_on_customer,
            },  # fmt: skip
            "project": rec.project,
        },
        "quoted": quoted,
        "owner": _user(s, lead.assigned_to, users),
        "last_activity_on": clock.to_rfc3339(lead.last_activity_on),
        "next_follow_up_on": clock.to_rfc3339(lead.next_follow_up_on),
        "is_follow_up_overdue": bool(lead.next_follow_up_on and lead.next_follow_up_on < now),
        "attention": [{"code": a, "label": ATTENTION_LABELS[a]} for a in p.attention],
        "customer_action": _customer_action(f, p.stage),
        "closed": {
            "won_on": clock.to_rfc3339(lead.won_on),
            "lost_on": clock.to_rfc3339(lead.lost_on),
            "lost_reason": lookups.value_ref(s, lead.lost_reason_id),
        },  # fmt: skip
    }


def _customer_action(f: stages.Facts, stage: str) -> str | None:
    """What, if anything, the customer is expected to do next (a fact of the records, not a prediction)."""
    if f.lead_status not in OPEN:
        return None
    if (
        f.customer_requests_open
        and f.customer_requests_open > 0
        and stage == "CUSTOMER_CONSIDERING"
        and not f.quotation_open
    ):
        return None
    if f.quotation_open and not f.quotation_accepted:
        return "Decision on the issued quotation"
    return None


def listing(s: Session, ctx, query, *, now: datetime) -> tuple[list[dict], dict]:
    for name, value, allowed in (("stage", query.stage, STAGES), ("attention", query.attention, ATTENTION),
                                 ("channel", query.channel, CHANNELS)):  # fmt: skip
        if value is not None and value not in allowed:
            raise validation_failed([field_error(name, "INVALID", "Not a known value.")])
    statuses = STATUS_GROUPS[query.status]
    stmt = (
        sa.select(Lead)
        .where(access.pipeline_predicate(ctx), Lead.status.in_(statuses))
        .order_by(Lead.created_on.desc(), Lead.id.desc())
        .limit(SCAN_LIMIT + 1)
    )
    if query.owner == "me":
        stmt = stmt.where(Lead.assigned_to == ctx.user.id)
    elif query.owner == "unassigned":
        stmt = stmt.where(Lead.assigned_to.is_(None))
    elif query.owner:
        stmt = stmt.where(Lead.assigned_to == query.owner)
    if query.q:
        stmt = stmt.where(Lead.search_text.contains(query.q.casefold()))
    leads = list(s.execute(stmt).scalars())
    truncated = len(leads) > SCAN_LIMIT
    leads = leads[:SCAN_LIMIT]
    records = facts.gather(s, [lead.id for lead in leads])
    users: dict = {}
    rows = [row(s, ctx, lead, records[lead.id], now=now, users=users) for lead in leads]
    if query.stage:
        rows = [r for r in rows if r["stage"]["code"] == query.stage]
    if query.attention:
        rows = [r for r in rows if any(a["code"] == query.attention for a in r["attention"])]
    if query.channel:
        rows = [r for r in rows if r["channel"]["code"] == query.channel]
    total = len(rows)
    start = (query.page - 1) * query.limit
    page = rows[start : start + query.limit]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["stage"]["code"]] = counts.get(r["stage"]["code"], 0) + 1
    meta = {"page": query.page, "limit": query.limit, "total": total, "scanned": len(leads), "truncated": truncated,
            "stage_counts": counts}  # fmt: skip
    return page, meta


def one(s: Session, ctx, lead: Lead, *, now: datetime) -> dict:
    records = facts.gather(s, [lead.id])
    return row(s, ctx, lead, records[lead.id], now=now, users={})
