"""MTQ B1 lead-erasure cascade (07 §8.2; blueprint §4.1 "PII: included in lead anonymisation set").

Measurements are not personal data and are kept: the space tree, walls, openings and electrical points describe a
building. What identifies or describes a person is removed: the site address and coordinates, the visit's customer
contact and access notes, and every free-text note. Rows stay; their audit payloads are rewritten by the erasure-audit
job because their ids join the transaction's erasure set.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import MeasurementNote, MeasurementSet, MeasurementVisit, Property, SpaceElectricalPoint, SpaceMeasurement

ERASED = "[erased]"
# Free-text keys of measurement_set.property_capture (B1-T06 schema); every other key is a measurement or a code.
CAPTURE_TEXT_KEYS = ("access_notes", "working_hours_notes", "parking_notes", "notes")


def _all(s: Session, stmt):
    return s.execute(stmt.execution_options(include_deleted=True)).scalars().all()


def erase_for_lead(s: Session, lead) -> int:
    erasure = s.info.setdefault("erasure_entities", set())
    touched = 0
    properties = _all(s, sa.select(Property).where(Property.lead_id == lead.id))
    for p in properties:
        erasure.add(p.id)
        p.address_line_1 = p.address_line_2 = p.locality = p.pincode = None
        p.geo_lat_e6 = p.geo_lng_e6 = None
        p.notes = None
        touched += 1
    for v in _all(s, sa.select(MeasurementVisit).where(MeasurementVisit.lead_id == lead.id)):
        erasure.add(v.id)
        v.customer_contact_name = v.customer_contact_phone = None
        v.access_notes = None
        if v.cancel_reason:
            v.cancel_reason = ERASED
        touched += 1
    property_ids = [p.id for p in properties]
    if not property_ids:
        return touched
    sets = _all(s, sa.select(MeasurementSet).where(MeasurementSet.property_id.in_(property_ids)))
    for ms in sets:
        erasure.add(ms.id)
        if ms.rejection_reason:
            ms.rejection_reason = ERASED
        capture = dict(ms.property_capture or {})
        if any(k in capture for k in CAPTURE_TEXT_KEYS):
            ms.property_capture = {k: (ERASED if k in CAPTURE_TEXT_KEYS and v else v) for k, v in capture.items()}
        touched += 1
    set_ids = [ms.id for ms in sets]
    if set_ids:
        for note in _all(s, sa.select(MeasurementNote).where(MeasurementNote.measurement_set_id.in_(set_ids))):
            erasure.add(note.id)
            note.body = ERASED
            touched += 1
        measurement_ids = sa.select(SpaceMeasurement.id).where(SpaceMeasurement.measurement_set_id.in_(set_ids))
        for point in _all(
            s, sa.select(SpaceElectricalPoint).where(SpaceElectricalPoint.space_measurement_id.in_(measurement_ids))
        ):
            if point.notes:
                erasure.add(point.id)
                point.notes = ERASED
                touched += 1
    return touched


def audit_ids_for_lead(s: Session, lead_id: str) -> list[str]:
    """Every MTQ row of a lead whose audit payload may hold personal data (properties, visits, sets, notes,
    electrical points), for the erasure-audit rewrite: most of them have a property or a set as audit parent."""
    props = [p.id for p in _all(s, sa.select(Property).where(Property.lead_id == lead_id))]
    ids = list(props)
    ids += [v.id for v in _all(s, sa.select(MeasurementVisit).where(MeasurementVisit.lead_id == lead_id))]
    if not props:
        return ids
    sets = [m.id for m in _all(s, sa.select(MeasurementSet).where(MeasurementSet.property_id.in_(props)))]
    ids += sets
    if sets:
        ids += [n.id for n in _all(s, sa.select(MeasurementNote).where(MeasurementNote.measurement_set_id.in_(sets)))]
        measurement_ids = sa.select(SpaceMeasurement.id).where(SpaceMeasurement.measurement_set_id.in_(sets))
        ids += [
            e.id
            for e in _all(
                s, sa.select(SpaceElectricalPoint).where(SpaceElectricalPoint.space_measurement_id.in_(measurement_ids))
            )
        ]
    return ids
