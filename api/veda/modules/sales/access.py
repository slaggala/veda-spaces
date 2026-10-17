"""Sales access (SCA-001): the flag and the pipeline's read scope."""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.modules.crm.leads.models import Lead
from veda.modules.crm.leads.repository import HIDDEN_SPAM, own_predicate

PIPELINE = "sales.pipeline.view"


def enabled() -> bool:
    return bool(settings().sales_experience_enabled)


def pipeline_predicate(ctx) -> sa.ColumnElement[bool]:
    """Which live leads the actor may see in the pipeline: ALL, or OWN (assigned to or created by the actor, as the
    lead's own OWN scope), never a deleted or quarantined lead."""
    scope = ctx.scope(PIPELINE)
    if scope == "ALL":
        who: sa.ColumnElement[bool] = sa.true()
    elif scope == "OWN":
        who = own_predicate(ctx.user.id)
    else:
        who = sa.false()
    return sa.and_(who, Lead.is_deleted == sa.false(), Lead.spam_status.not_in(HIDDEN_SPAM))
