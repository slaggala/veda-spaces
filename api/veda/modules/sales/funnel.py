"""The acquisition funnel (SCA-007): counts per stage over a period, each with the kind of record that produced it.

Three kinds of number, never mixed:

- ``AUTHORITATIVE``: rows written by the feature that owns the fact (estimates, leads, visits, quotations, proposal
  links, acceptances, won and lost statuses);
- ``CLIENT_EVENT``: the site's anonymous beacons (site visits, estimator starts, enquiry starts, journey views),
  de-duplicated per browser session and day;
- ``NOT_TRACKED``: no beacon of that event has ever been received (the site was not sending them), reported as such
  and never as zero.

Ratios are computed only between tracked counts with a positive denominator; otherwise they are ``null`` with the
reason. The lead cohort is the leads created in the period (spam and deleted excluded), judged by their facts as of
now, so "quotation issued" counts leads of the cohort that have reached that stage by today.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.modules.crm.leads.models import Lead
from veda.modules.crm.leads.repository import HIDDEN_SPAM
from veda.modules.estimator.models import BudgetEstimate
from veda.platform.lookups import service as lookups

from . import attribution, facts, stages
from .models import AcquisitionEventDaily
from .vocab import CHANNEL_LABELS, CHANNELS, EVENTS, STAGE_LABELS, STAGES

BUSINESS_TZ = "Asia/Kolkata"
COHORT_LIMIT = 5000
# Funnel steps in order, with the fact that proves a lead reached them.
LEAD_STEPS: tuple[tuple[str, str], ...] = (
    ("leads_created", "Enquiries received"),
    ("leads_with_estimate", "Enquiries with a budgetary estimate"),
    ("contacted", "Contacted"),
    ("consultation", "Consultation held"),
    ("measurement", "Site measurement"),
    ("quotation_issued", "Quotation issued"),
    ("quotation_opened", "Quotation opened by the customer"),
    ("accepted", "Accepted by the customer"),
    ("won", "Won"),
    ("lost", "Lost"),
)


def _reached(f: stages.Facts, p: stages.Progression) -> set[str]:
    """The funnel steps a lead has reached: from records wherever they exist, else from the open CRM statuses, which
    say where the lead was put by staff. A closed status (WON, LOST) says nothing about the steps in between: those
    count only when a record proves them."""
    status = f.lead_status
    out = {"leads_created"}
    if f.estimate_linked:
        out.add("leads_with_estimate")
    if (
        f.contacted_activity
        or f.meeting_done
        or f.visits
        or f.quotations
        or status in ("CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION")
    ):
        out.add("contacted")
    if f.meeting_done:
        out.add("consultation")
    if f.visits or f.quotations or status in ("SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION"):
        out.add("measurement")
    if f.quotation_issued or f.quotation_accepted or status in ("QUOTATION_SENT", "NEGOTIATION"):
        out.add("quotation_issued")
    if f.proposal_opened:
        out.add("quotation_opened")
    if f.quotation_accepted:
        out.add("accepted")
    if status == "WON":
        out.add("won")
    if status == "LOST":
        out.add("lost")
    return out


def _ratio(num: int | None, den: int | None, num_tracked: bool, den_tracked: bool) -> dict:
    if not (num_tracked and den_tracked):
        return {"value": None, "reason": "NOT_TRACKED"}
    if not den:
        return {"value": None, "reason": "NO_DENOMINATOR"}
    return {"value": round((num or 0) / den, 4), "reason": None}


def report(s: Session, day_from: date, day_to: date, *, now: datetime) -> dict:
    start, end = clock.local_day_range_utc(day_from, day_to, BUSINESS_TZ)

    # --- client beacons (counts per event and channel; NOT_TRACKED when the site never sent that event) ---
    ever = {e for (e,) in s.execute(sa.select(AcquisitionEventDaily.event).distinct()).all()}
    period_rows = s.execute(
        sa.select(AcquisitionEventDaily.event, AcquisitionEventDaily.channel, sa.func.sum(AcquisitionEventDaily.count))
        .where(AcquisitionEventDaily.day >= day_from.isoformat(), AcquisitionEventDaily.day <= day_to.isoformat())
        .group_by(AcquisitionEventDaily.event, AcquisitionEventDaily.channel)
    ).all()
    beacons: dict[str, dict] = {}
    for event in EVENTS:
        per_channel: dict[str, int] = {c: 0 for c in CHANNELS}
        total = 0
        for e, ch, n in period_rows:
            if e == event:
                per_channel[ch] = per_channel.get(ch, 0) + int(n)
                total += int(n)
        tracked = event in ever
        beacons[event] = {"count": total if tracked else None, "basis": "CLIENT_EVENT",
                          "tracking": "TRACKED" if tracked else "NOT_TRACKED",
                          "by_channel": per_channel if tracked else None}  # fmt: skip

    estimates = s.execute(
        sa.select(sa.func.count()).select_from(BudgetEstimate)
        .where(BudgetEstimate.origin == "PUBLIC", BudgetEstimate.created_on >= start, BudgetEstimate.created_on < end)
    ).scalar_one()  # fmt: skip

    # --- the lead cohort ---
    leads = list(s.execute(
        sa.select(Lead)
        .where(Lead.is_deleted == sa.false(), Lead.spam_status.not_in(HIDDEN_SPAM),
               Lead.created_on >= start, Lead.created_on < end)
        .order_by(Lead.created_on)
        .limit(COHORT_LIMIT + 1)
    ).scalars())  # fmt: skip
    truncated = len(leads) > COHORT_LIMIT
    leads = leads[:COHORT_LIMIT]
    records = facts.gather(s, [lead.id for lead in leads])
    steps = {code: 0 for code, _ in LEAD_STEPS}
    by_channel: dict[str, dict[str, int]] = {
        c: {"leads": 0, "quotation_issued": 0, "accepted": 0, "won": 0, "lost": 0} for c in CHANNELS
    }
    by_source: dict[str, dict] = {}
    stage_counts = {code: 0 for code in STAGES}
    claimed = 0
    lost_reasons: dict[str, dict] = {}
    for lead in leads:
        f = records[lead.id].facts(lead, now=now)
        p = stages.derive(f, now=now)
        reached = _reached(f, p)
        for code in reached:
            steps[code] += 1
        stage_counts[p.stage] += 1
        if p.claimed_without_record:
            claimed += 1
        source = lookups.value_ref(s, lead.source_id)
        ch = attribution.channel(
            source["code"] if source else None, lead.utm_source, lead.utm_medium, lead.referrer_url
        ).code
        bucket = by_channel[ch]
        bucket["leads"] += 1
        for code in ("quotation_issued", "accepted", "won", "lost"):
            if code in reached:
                bucket[code] += 1
        key = source["code"] if source else "UNKNOWN"
        src = by_source.setdefault(
            key, {"code": key, "label": source["label"] if source else "Unknown", "leads": 0, "won": 0}
        )
        src["leads"] += 1
        if "won" in reached:
            src["won"] += 1
        if lead.status == "LOST":
            reason = lookups.value_ref(s, lead.lost_reason_id)
            rkey = reason["code"] if reason else "NOT_PROVIDED"
            entry = lost_reasons.setdefault(
                rkey, {"code": rkey, "label": reason["label"] if reason else "Not provided", "count": 0}
            )
            entry["count"] += 1

    leads_n = steps["leads_created"]
    starts = beacons["estimator_started"]
    visits = beacons["site_visit"]
    return {
        "period": {"from": day_from.isoformat(), "to": day_to.isoformat(), "timezone": BUSINESS_TZ},
        "as_of": clock.to_rfc3339(now),
        "site": beacons,
        "estimates_completed": {"count": estimates, "basis": "AUTHORITATIVE", "tracking": "TRACKED"},
        "leads": [
            {"code": code, "label": label, "count": steps[code], "basis": "AUTHORITATIVE", "tracking": "TRACKED"}
            for code, label in LEAD_STEPS
        ],  # fmt: skip
        "cohort": {"size": leads_n, "truncated": truncated, "claimed_stages_without_record": claimed},
        "current_stages": [{"code": code, "label": STAGE_LABELS[code], "count": stage_counts[code]} for code in STAGES],
        "ratios": {
            "estimator_start_to_estimate": _ratio(estimates, starts["count"], True, starts["tracking"] == "TRACKED"),
            "site_visit_to_enquiry": _ratio(leads_n, visits["count"], True, visits["tracking"] == "TRACKED"),
            "enquiry_to_quotation": _ratio(steps["quotation_issued"], leads_n, True, True),
            "quotation_to_acceptance": _ratio(steps["accepted"], steps["quotation_issued"], True, True),
            "enquiry_to_won": _ratio(steps["won"], leads_n, True, True),
            "decided_to_won": _ratio(steps["won"], steps["won"] + steps["lost"], True, True),
        },
        "by_channel": [{"code": c, "label": CHANNEL_LABELS[c], **by_channel[c]} for c in CHANNELS],
        "by_source": sorted(by_source.values(), key=lambda x: (-x["leads"], x["code"])),
        "lost_reasons": sorted(lost_reasons.values(), key=lambda x: (-x["count"], x["code"])),
        "stalled": {
            "quiet": sum(
                1
                for lead in leads
                if "QUIET" in stages.derive(records[lead.id].facts(lead, now=now), now=now).attention
            )
        },
    }
