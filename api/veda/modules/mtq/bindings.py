"""Attachment bindings for the MTQ record types (ATT registry; MTQ blocker closure §6).

Each binding resolves an id to its lead (scope and retention), its limits container (the measurement set), its wall
(per-wall limits) and space (soft limit), and says whether the record still accepts uploads and who may withdraw.
Property and space photos are not revision-scoped: they stay attached across measurement revisions.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.modules.attachments import registry

from .models import (
    MeasurementNote,
    MeasurementSet,
    Property,
    PropertySpace,
    SpaceMeasurement,
    SpaceOpening,
    SpaceWall,
)


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


# --- measurement-set records (B1-T06): limits container = the set; frozen once the set is submitted ---------------------
def _set_context(s: Session, mset_id: str, **extra) -> registry.EntityContext | None:
    mset = s.get(MeasurementSet, mset_id)
    if mset is None or mset.is_deleted:
        return None
    prop = s.get(Property, mset.property_id)
    if prop is None:
        return None
    draft = mset.status == "DRAFT"
    return registry.EntityContext(
        lead_id=prop.lead_id,
        container_id=mset.id,
        writable=draft,
        withdraw_rule="UPLOADER_OR_ALL" if draft else "VERIFIER_WITH_REASON",
        extra={"verify_permission": "measurement.verify"},
        **extra,
    )


def _measurement_set(s: Session, entity_id: str) -> registry.EntityContext | None:
    return _set_context(s, entity_id)


def _wall(s: Session, entity_id: str) -> registry.EntityContext | None:
    wall = s.get(SpaceWall, entity_id)
    if wall is None or wall.is_deleted:
        return None
    sm = s.get(SpaceMeasurement, wall.space_measurement_id)
    if sm is None:
        return None
    return _set_context(s, sm.measurement_set_id, wall_id=wall.id, space_id=sm.space_id)


def _opening(s: Session, entity_id: str) -> registry.EntityContext | None:
    op = s.get(SpaceOpening, entity_id)
    if op is None or op.is_deleted:
        return None
    return _wall(s, op.space_wall_id)


def _note(s: Session, entity_id: str) -> registry.EntityContext | None:
    note = s.get(MeasurementNote, entity_id)
    if note is None or note.is_deleted:
        return None
    return _set_context(s, note.measurement_set_id, space_id=note.space_id)


def set_conditions(mset_id: str) -> list:
    """Conditions on ``attachment`` selecting every live attachment that counts toward a set's limits."""
    from veda.modules.attachments.models import Attachment

    sm_ids = sa.select(SpaceMeasurement.id).where(SpaceMeasurement.measurement_set_id == mset_id)
    wall_ids = sa.select(SpaceWall.id).where(SpaceWall.space_measurement_id.in_(sm_ids))
    pairs = [
        ("space_wall", wall_ids),
        ("space_opening", sa.select(SpaceOpening.id).where(SpaceOpening.space_wall_id.in_(wall_ids))),
        ("measurement_note", sa.select(MeasurementNote.id).where(MeasurementNote.measurement_set_id == mset_id)),
        *EXTRA_SET_ENTITIES(mset_id, sm_ids),
    ]
    return [
        sa.and_(Attachment.entity_type == "measurement_set", Attachment.entity_id == mset_id),
        *(sa.and_(Attachment.entity_type == et, Attachment.entity_id.in_(ids)) for et, ids in pairs),
    ]


def _no_extra(mset_id, sm_ids) -> list:
    return []


EXTRA_SET_ENTITIES = _no_extra  # B1-T08 adds electrical points


def set_usage(s: Session, mset_id: str) -> tuple[int, int]:
    from veda.modules.attachments.models import Attachment

    row = s.execute(
        sa.select(sa.func.count(Attachment.id), sa.func.coalesce(sa.func.sum(Attachment.byte_size), 0)).where(
            sa.or_(*set_conditions(mset_id)),
            Attachment.retention_state == "ACTIVE",
            Attachment.upload_status != "REJECTED",
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


for _type, _resolve in (("measurement_set", _measurement_set), ("space_wall", _wall), ("space_opening", _opening),
                        ("measurement_note", _note)):  # fmt: skip
    registry.bind(registry.EntityBinding(_type, _resolve, container_usage=set_usage))
