"""Visibility and locking for MTQ B2-B4 rows (blueprint §15.3): every row hangs off a lead, like B1.

Reads outside scope answer 404 (existence not disclosed); a visible row whose action is outside the actor's scope
answers 403; an erased lead is closed to writes. Every state change of a property's commercial lineage takes the
property's row lock (B1's ``lock_property``), so revisions of one property are serialised on both engines.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import not_found
from veda.modules.mtq import properties as site_properties
from veda.modules.mtq import scope as site_scope
from veda.modules.mtq import sets as site_sets
from veda.modules.mtq.models import Property


def property_visible(s: Session, ctx, property_id: str, permission: str) -> Property:
    return site_properties.get_visible(s, ctx, property_id, permission)


def row_visible[T](s: Session, ctx, model: type[T], row_id: str, permission: str) -> T:
    row = s.execute(
        sa.select(model).where(model.id == row_id, site_scope.condition(ctx, permission, model.lead_id))  # type: ignore[attr-defined]  # every commercial model has id and lead_id
    ).scalar_one_or_none()
    if row is None:
        raise not_found()
    return row


def for_write(s: Session, ctx, prop_or_lead_id: str, property_id: str, permission: str, *rows) -> None:
    """Scope check for the action, then the property lock, then re-read each row under it."""
    site_scope.require_in_scope(s, ctx, prop_or_lead_id, permission)
    site_sets.lock_for_write(s, property_id, *rows)


def condition(ctx, permission: str, lead_column):
    return site_scope.condition(ctx, permission, lead_column)
