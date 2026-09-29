"""Dashboard metrics (04 §11, LEAD-014). Every metric respects the viewer's lead.read scope
and excludes soft-deleted and quarantined (spam) leads."""

from __future__ import annotations

import statistics
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.kernel.errors import ApiError
from veda.platform.identity.models import User
from veda.platform.lookups.service import value_ref

from . import repository as repo
from .models import OPEN_STATUSES, Lead, LeadActivity

PERIOD_DAYS = {"today": 1, "7d": 7, "30d": 30, "90d": 90}


def period_range(period: str, day_from: date | None, day_to: date | None, tz: str) -> tuple[datetime, datetime]:
    today = clock.now().astimezone(ZoneInfo(tz)).date()
    if period == "custom":
        if not day_from or not day_to or day_to < day_from:
            raise ApiError(422, "INVALID_QUERY_PARAM", "Custom periods need from ≤ to.")
        return clock.local_day_range_utc(day_from, day_to, tz)
    days = PERIOD_DAYS[period]
    return clock.local_day_range_utc(today - timedelta(days=days - 1), today, tz)


def summary(s: Session, ctx, period: str, day_from: date | None, day_to: date | None) -> dict:
    tz = ctx.user.timezone
    start, end = period_range(period, day_from, day_to, tz)
    prev_start = start - (end - start)
    scope = repo.scope_predicate(ctx.scope("lead.read"), ctx.user.id)
    base = sa.and_(scope, Lead.spam_status.not_in(repo.HIDDEN_SPAM))

    def count(*conds) -> int:
        return int(s.execute(sa.select(sa.func.count()).select_from(Lead).where(base, *conds)).scalar() or 0)

    pipeline_rows = s.execute(
        sa.select(Lead.status, sa.func.count()).where(base, Lead.status.in_(OPEN_STATUSES)).group_by(Lead.status)
    ).all()
    pipeline = {st: 0 for st in OPEN_STATUSES}
    pipeline.update({row[0]: int(row[1]) for row in pipeline_rows})
    won = count(Lead.status == "WON", Lead.won_on >= start, Lead.won_on < end)
    lost = count(Lead.status == "LOST", Lead.lost_on >= start, Lead.lost_on < end)
    new_count = count(Lead.created_on >= start, Lead.created_on < end)
    prev_count = count(Lead.created_on >= prev_start, Lead.created_on < start)
    unassigned = count(Lead.status.in_(OPEN_STATUSES), Lead.assigned_to.is_(None))

    now = clock.now()
    day_start = clock.start_of_local_day(now, tz)
    day_end = day_start + timedelta(days=1)
    act_base = (
        sa.select(sa.func.count())
        .select_from(LeadActivity)
        .join(Lead, Lead.id == LeadActivity.lead_id)
        .where(base, LeadActivity.activity_status == "PLANNED")
    )
    due_today = int(
        s.execute(
            act_base.where(
                LeadActivity.scheduled_on >= day_start,
                LeadActivity.scheduled_on < day_end,
                LeadActivity.scheduled_on >= now,
            )
        ).scalar()
        or 0
    )
    overdue = int(s.execute(act_base.where(LeadActivity.scheduled_on < now)).scalar() or 0)

    first_contact = (
        sa.select(LeadActivity.lead_id, sa.func.min(LeadActivity.completed_on).label("first"))
        .where(
            LeadActivity.activity_status == "COMPLETED", LeadActivity.activity_type.in_(("CALL", "WHATSAPP", "MEETING"))
        )
        .group_by(LeadActivity.lead_id)
        .subquery()
    )
    rows = s.execute(
        sa.select(Lead.created_on, first_contact.c.first)
        .join(first_contact, first_contact.c.lead_id == Lead.id)
        .where(base, Lead.created_on >= start, Lead.created_on < end)
    ).all()
    hours = []
    for created, first in rows:
        first_dt = (
            first
            if isinstance(first, datetime)
            else datetime.strptime(first, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=clock.now().tzinfo)
        )
        hours.append(max(0.0, (first_dt - created).total_seconds() / 3600))
    by_source = s.execute(
        sa.select(Lead.source_id, sa.func.count())
        .where(base, Lead.created_on >= start, Lead.created_on < end)
        .group_by(Lead.source_id)
        .order_by(sa.func.count().desc())
    ).all()
    disabled = (
        sa.select(User.id)
        .where(sa.or_(User.status != "ACTIVE", User.is_deleted == sa.true()))
        .execution_options(include_deleted=True)
    )
    needs_reassignment = count(Lead.status.in_(OPEN_STATUSES), Lead.assigned_to.in_(disabled))
    needs_enrichment = count(
        Lead.status.in_(OPEN_STATUSES), sa.or_(Lead.project_type_id.is_(None), Lead.budget_range_id.is_(None))
    )
    spam_queue = None
    if ctx.scope("lead.update") == "ALL":
        spam_queue = int(
            s.execute(
                sa.select(sa.func.count()).select_from(Lead).where(scope, Lead.spam_status == "SUSPECTED")
            ).scalar()
            or 0
        )
    return {
        "period": {"from": clock.to_rfc3339(start), "to": clock.to_rfc3339(end), "timezone": tz},
        "pipeline": pipeline,
        "closed_in_period": {"WON": won, "LOST": lost},
        "new_leads": {"count": new_count, "previous_period_count": prev_count},
        "unassigned_open": unassigned,
        "follow_ups": {"due_today": due_today, "overdue": overdue},
        "conversion_rate": round(won / (won + lost), 4) if (won + lost) else None,
        "median_hours_to_first_contact": round(statistics.median(hours), 1) if hours else None,
        "by_source": [
            {**(value_ref(s, sid) or {"code": None, "label": None}), "count": int(n)} for sid, n in by_source
        ],
        "needs_reassignment": needs_reassignment,
        "needs_enrichment": needs_enrichment,
        "spam_review_count": spam_queue,
    }
