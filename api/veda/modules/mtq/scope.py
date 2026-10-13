"""MTQ scope resolution (blueprint §15.3, 06 §4).

Every MTQ row hangs off a lead. An actor holding a permission with:

- **ALL** scope sees every row;
- **OWN** scope sees a row when they own the lead (assigned to or created by them, the lead module's rule) or are
  assigned a live measurement visit on it (the surveyor's route into a property);
- no grant sees nothing.

Out of scope reads as 404 (the row's existence is not disclosed), as for leads. An erased lead is closed to writes.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError, not_found
from veda.modules.attachments import registry as att_registry
from veda.modules.crm.leads.models import Lead
from veda.modules.crm.leads.repository import own_predicate

from .models import MeasurementVisit


def assigned_lead_ids(actor_id: str):
    return sa.select(MeasurementVisit.lead_id).where(
        MeasurementVisit.assigned_to == actor_id, MeasurementVisit.is_deleted == sa.false()
    )


def owned_lead_ids(actor_id: str):
    return sa.select(Lead.id).where(sa.or_(own_predicate(actor_id), Lead.id.in_(assigned_lead_ids(actor_id))))


def condition(ctx, permission: str, lead_column) -> sa.ColumnElement[bool]:
    scope = ctx.scope(permission)
    if scope == "ALL":
        return sa.true()
    if scope == "OWN":
        return lead_column.in_(owned_lead_ids(ctx.user.id))
    return sa.false()


def require_lead(s: Session, ctx, lead_id: str, permission: str, *, write: bool = True) -> Lead:
    """The lead exists, is live, is within ``permission``'s scope and (for writes) is not erased."""
    scope = ctx.scope(permission)
    if scope is None:
        from veda.platform.auth.request_auth import deny

        deny(ctx, permission)
    lead = s.get(Lead, lead_id)
    if lead is None or lead.is_deleted:
        raise not_found()
    if scope == "OWN" and s.execute(owned_lead_ids(ctx.user.id).where(Lead.id == lead_id)).first() is None:
        raise not_found()
    if write and lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This lead was erased; its site records can no longer change.")
    return lead


def require_in_scope(s: Session, ctx, lead_id: str, permission: str) -> None:
    """A visible record, but the action is outside ``permission``'s scope → 403 (or 404 when not visible at all)."""
    scope = ctx.scope(permission)
    if scope is None:
        from veda.platform.auth.request_auth import deny

        deny(ctx, permission)
    if scope == "OWN" and s.execute(owned_lead_ids(ctx.user.id).where(Lead.id == lead_id)).first() is None:
        raise ApiError(
            403, "PERMISSION_DENIED", f"Requires {permission} for this lead.", extra={"permission": permission}
        )
    lead = s.get(Lead, lead_id)
    if lead is not None and lead.anonymized_on is not None:
        raise ApiError(409, "INVALID_STATE", "This lead was erased; its site records can no longer change.")


# The surveyor assigned to a visit may reach the lead's attachments too (ATT scope extension).
att_registry.grant_lead_access(lambda actor_id: Lead.id.in_(assigned_lead_ids(actor_id)))
