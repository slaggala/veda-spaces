"""Derived sales progression (SCA-005): a pure function from facts on file to a stage, its basis and attention.

Nothing here reads a database or writes anything. ``facts.gather`` collects the inputs from the records the other
modules own; this module only ranks them. The strongest evidence wins; a staff-recorded lead status is evidence of
its own kind (LEAD_STATUS) and is reported as such, so a claimed "quotation sent" with no quotation record is visible
as a claim, and a customer's acceptance recorded by the quotation module outranks any open CRM status.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .vocab import ATTENTION, BASES, LEAD_STATUS_STAGE, QUIET_DAYS, STAGES

OPEN_LEAD_STATUSES = ("NEW", "CONTACTED", "SITE_VISIT", "QUOTATION_SENT", "NEGOTIATION")


@dataclass(frozen=True)
class Facts:
    """Everything the stage depends on, as booleans, counts and times (never free text or money)."""

    lead_status: str
    assigned: bool = True
    next_follow_up_on: datetime | None = None
    last_activity_on: datetime | None = None
    contacted_activity: bool = False  # a COMPLETED, staff-logged CALL, WHATSAPP, EMAIL or MEETING
    meeting_done: bool = False  # a COMPLETED, staff-logged MEETING (how a consultation is logged today)
    site_visit_logged: bool = False  # a COMPLETED, staff-logged SITE_VISIT activity (a visit outside MTQ)
    consent_withdrawn: bool = False  # the lead asked not to be contacted: no follow-up is expected
    estimate_linked: bool = False
    visits: int = 0  # measurement visits not cancelled
    visits_completed: int = 0
    quotations: int = 0  # quotation rows of any status (base and variations)
    quotation_issued: bool = False  # a base quotation ever issued (ISSUED, ACCEPTED, REJECTED, EXPIRED, SUPERSEDED)
    quotation_open: bool = False  # the latest base quotation is ISSUED and in its validity
    quotation_accepted: bool = False  # a base quotation ACCEPTED (B4 decision, any method)
    quotation_declined: bool = False  # the latest base quotation is REJECTED and none was accepted
    proposal_shared: bool = False
    proposal_opened: bool = False  # a proposal link was opened (link possession: not a decision)
    customer_requests_open: int = 0
    customer_requests: int = 0
    project: bool = False


@dataclass(frozen=True)
class Progression:
    stage: str
    basis: str
    attention: tuple[str, ...] = field(default_factory=tuple)
    claimed_without_record: bool = False  # the stage rests on a staff status with no record behind it

    def __post_init__(self) -> None:
        assert self.stage in STAGES and self.basis in BASES
        assert all(a in ATTENTION for a in self.attention)


def _rank(stage: str) -> int:
    return STAGES.index(stage)


def derive(f: Facts, *, now: datetime) -> Progression:
    status = f.lead_status
    if status == "LOST":
        return Progression("LOST", "LEAD_STATUS", attention=())
    if status == "WON":
        return Progression("WON", "LEAD_STATUS", attention=(), claimed_without_record=not f.quotation_accepted)
    if f.quotation_accepted:
        return Progression("ACCEPTED", "QUOTATION_RECORD", attention=_attention(f, "ACCEPTED", now))
    if f.quotation_declined:
        return Progression("QUOTATION_DECLINED", "QUOTATION_RECORD", attention=_attention(f, "QUOTATION_DECLINED", now))

    candidates: list[tuple[str, str]] = [("NEW", "NONE")]
    claimed = LEAD_STATUS_STAGE.get(status, "NEW")
    candidates.append((claimed, "LEAD_STATUS" if claimed != "NEW" else "NONE"))
    if f.contacted_activity:
        candidates.append(("CONTACTED", "ACTIVITY"))
    if f.meeting_done:
        candidates.append(("CONSULTATION", "ACTIVITY"))
    if f.site_visit_logged:
        candidates.append(("SITE_MEASUREMENT", "ACTIVITY"))
    if f.visits:
        candidates.append(("SITE_MEASUREMENT", "MEASUREMENT_RECORD"))
    if f.quotations and not f.quotation_issued:
        candidates.append(("QUOTATION_PREPARATION", "QUOTATION_RECORD"))
    if f.quotation_issued:
        candidates.append(("QUOTATION_ISSUED", "QUOTATION_RECORD"))
        if f.proposal_opened or f.customer_requests:
            candidates.append(("CUSTOMER_CONSIDERING", "PROPOSAL_RECORD"))
    # Highest stage wins; among equals a record outranks a staff status (BASES order puts LEAD_STATUS first).
    stage, basis = max(candidates, key=lambda c: (_rank(c[0]), BASES.index(c[1])))
    recorded = any(s == stage and b not in ("NONE", "LEAD_STATUS") for s, b in candidates)
    return Progression(stage, basis, attention=_attention(f, stage, now),
                       claimed_without_record=basis == "LEAD_STATUS" and not recorded)  # fmt: skip


def _attention(f: Facts, stage: str, now: datetime) -> tuple[str, ...]:
    out: list[str] = []
    if f.lead_status not in OPEN_LEAD_STATUSES:
        return ()
    if f.next_follow_up_on is not None and f.next_follow_up_on < now:
        out.append("FOLLOW_UP_OVERDUE")
    if f.next_follow_up_on is None and not f.consent_withdrawn:  # a do-not-contact lead needs no follow-up
        out.append("NO_FOLLOW_UP_PLANNED")
        if f.last_activity_on is None or f.last_activity_on < now - timedelta(days=QUIET_DAYS):
            out.append("QUIET")
    if not f.assigned:
        out.append("UNASSIGNED")
    if f.customer_requests_open:
        out.append("CUSTOMER_REQUEST_OPEN")
    if f.proposal_shared and not f.proposal_opened and f.quotation_open:
        out.append("PROPOSAL_NOT_OPENED")
    if stage == "ACCEPTED":
        out.append("ACCEPTED_NOT_CLOSED")
    if stage == "QUOTATION_DECLINED":
        out.append("DECLINED_STILL_OPEN")
    return tuple(a for a in ATTENTION if a in out)
