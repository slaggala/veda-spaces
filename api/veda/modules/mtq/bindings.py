"""Attachment bindings for the MTQ record types (ATT registry; MTQ blocker closure §6).

Each binding resolves an id to its lead (scope and retention), its limits container (the measurement set), its wall
(per-wall limits) and space (soft limit), and says whether the record still accepts uploads and who may withdraw.
Property and space photos are not revision-scoped: they stay attached across measurement revisions.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from veda.modules.attachments import registry

from .models import Property, PropertySpace


def _property(s: Session, entity_id: str) -> registry.EntityContext | None:
    prop = s.get(Property, entity_id)
    if prop is None or prop.is_deleted:
        return None
    return registry.EntityContext(lead_id=prop.lead_id)


def _space(s: Session, entity_id: str) -> registry.EntityContext | None:
    sp = s.get(PropertySpace, entity_id)
    if sp is None or sp.is_deleted:
        return None
    prop = s.get(Property, sp.property_id)
    if prop is None:
        return None
    return registry.EntityContext(lead_id=prop.lead_id, space_id=sp.id)


registry.bind(registry.EntityBinding("property", _property))
registry.bind(registry.EntityBinding("property_space", _space))
