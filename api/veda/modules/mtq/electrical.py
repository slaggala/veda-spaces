"""Electrical points (MTQ B1-T08; B1-SCOPE §2.5).

Light, fan, socket, AC, DB and switchboard points, sensor lights with their sensor and switching, and point shifting
from an existing position to a new one. Points are written with their space (one capture payload), matched by
``client_ref`` so their ids, and the photos attached to them, survive edits. Counts by (type, status) per space are the
inputs to B3's ``ELECTRICAL.*`` lines; B1 only stores them.

Full surveys: every switchboard or DB box obstruction on a furniture wall has its electrical point on the same wall at
the same offset (within 50 mm), because the capture UI creates both and B2 rules need the point to decide between
shortening a unit and shifting the point.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError, field_error

from . import bindings, sets, tolerance
from .models import PropertySpace, SpaceElectricalPoint, SpaceMeasurement, SpaceWall
from .verification import EXTRA_SPACE_CHECKS, problem

FIELDS = (
    "point_type_code",
    "status_code",
    "from_offset_mm",
    "from_height_mm",
    "to_offset_mm",
    "to_height_mm",
    "sensor_type_code",
    "switching_code",
    "location_code",
    "quantity",
    "reason_code",
    "notes",
    "attachment_id",
)
OBSTRUCTION_POINT = {"SWITCHBOARD": "SWITCHBOARD", "DB_BOX": "DB_BOX"}


def _walls(s: Session, sm: SpaceMeasurement) -> dict[int, SpaceWall]:
    return {
        w.wall_index: w
        for w in s.execute(sa.select(SpaceWall).where(SpaceWall.space_measurement_id == sm.id)).scalars()
    }


def _pre_write(s: Session, sp: PropertySpace, payload) -> None:
    """Space-type rules for the typed attributes (no escape hatch: a key belongs to the space type it describes)."""
    if payload.attributes.staircase is not None and sp.space_type_code != "STAIRCASE":
        raise ApiError(422, "VALIDATION_FAILED", "Staircase geometry belongs to a staircase space.",
                       errors=[field_error("attributes.staircase", "NOT_ALLOWED", "Not a staircase.")])  # fmt: skip
    walls = {w.wall_index: w.length_mm for w in payload.walls}
    for p in payload.electrical_points:
        for wall, offset in ((p.wall_index, p.from_offset_mm), (p.to_wall_index, p.to_offset_mm)):
            if wall is not None and offset is not None and offset > walls[wall]:
                raise ApiError(422, "VALIDATION_FAILED", f"Point {p.client_ref} lies beyond the end of wall {wall}.",
                               errors=[field_error("electrical_points", "OUT_OF_RANGE", "Offset past the wall.")])  # fmt: skip


def _after_write(s: Session, sm: SpaceMeasurement, payload) -> None:
    walls = _walls(s, sm)
    existing = {
        p.client_ref: p
        for p in s.execute(
            sa.select(SpaceElectricalPoint).where(SpaceElectricalPoint.space_measurement_id == sm.id)
        ).scalars()
    }
    keep = set()
    for p in payload.electrical_points:
        keep.add(p.client_ref)
        values: dict[str, Any] = {f: getattr(p, f) for f in FIELDS}
        values["space_wall_id"] = walls[p.wall_index].id if p.wall_index is not None else None
        values["to_wall_id"] = walls[p.to_wall_index].id if p.to_wall_index is not None else None
        if values["location_code"] is None:
            values["location_code"] = "WALL" if p.wall_index is not None else "CEILING"
        row = existing.get(p.client_ref)
        if row is None:
            s.add(SpaceElectricalPoint(space_measurement_id=sm.id, client_ref=p.client_ref, **values))
        else:
            for k, v in values.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
    for ref, row in existing.items():
        if ref not in keep:
            row.is_deleted = True
    s.flush()


def _copy(s: Session, source: SpaceMeasurement, copy: SpaceMeasurement) -> None:
    old = {
        w.id: w.wall_index
        for w in s.execute(sa.select(SpaceWall).where(SpaceWall.space_measurement_id == source.id)).scalars()
    }
    new = {
        w.wall_index: w.id
        for w in s.execute(sa.select(SpaceWall).where(SpaceWall.space_measurement_id == copy.id)).scalars()
    }

    def remap(wall_id: str | None) -> str | None:
        index = old.get(wall_id) if wall_id is not None else None
        return new.get(index) if index is not None else None

    for p in s.execute(
        sa.select(SpaceElectricalPoint).where(SpaceElectricalPoint.space_measurement_id == source.id)
    ).scalars():
        s.add(SpaceElectricalPoint(space_measurement_id=copy.id, client_ref=p.client_ref, space_wall_id=remap(p.space_wall_id),
                                   to_wall_id=remap(p.to_wall_id), **{f: getattr(p, f) for f in FIELDS}))  # fmt: skip
    s.flush()


def _present(s: Session, sm: SpaceMeasurement, out: dict[str, Any]) -> None:
    by_id = {w["id"]: w["wall_index"] for w in out["walls"]}
    points = []
    for p in s.execute(
        sa.select(SpaceElectricalPoint)
        .where(SpaceElectricalPoint.space_measurement_id == sm.id)
        .order_by(SpaceElectricalPoint.client_ref)
    ).scalars():
        points.append({
            "id": p.id, "client_ref": p.client_ref,
            "wall_index": by_id.get(p.space_wall_id) if p.space_wall_id else None,
            "to_wall_index": by_id.get(p.to_wall_id) if p.to_wall_id else None,
            **{f: getattr(p, f) for f in FIELDS},
        })  # fmt: skip
    out["electrical_points"] = points
    counts = Counter((p["point_type_code"], p["status_code"]) for p in points for _ in range(p["quantity"]))
    out["electrical_counts"] = [
        {"point_type_code": t, "status_code": st, "count": n} for (t, st), n in sorted(counts.items())
    ]


def _checks(sp, m: dict[str, Any], level: str, gate: str) -> list[dict]:
    if level != "FULL":
        return []
    from .capture import FURNITURE_TAGS

    out = []
    points = m.get("electrical_points") or []
    for w in m.get("walls") or []:
        if not FURNITURE_TAGS & set(w["usable_for_code"]):
            continue
        for o in w["obstructions"]:
            kind = OBSTRUCTION_POINT.get(o.get("kind"))
            if kind is None:
                continue
            match = any(
                p["point_type_code"] == kind
                and p["wall_index"] == w["wall_index"]
                and p.get("from_offset_mm") is not None
                and abs(p["from_offset_mm"] - o["offset_mm"]) <= tolerance.CLOSURE_MM
                for p in points
            )
            if not match:
                out.append(problem(f"/spaces/{sp.id}/walls/{w['wall_index']}", "ELECTRICAL_POINT_MISSING",
                                   f"Capture the {kind.replace('_', ' ').lower()} on this wall as an electrical point.",
                                   space=sp.label))  # fmt: skip
    return out


def _extra_entities(mset_id, sm_ids) -> list:
    return [(
        "space_electrical_point",
        sa.select(SpaceElectricalPoint.id).where(SpaceElectricalPoint.space_measurement_id.in_(sm_ids)),
    )]  # fmt: skip


def _point_binding(s: Session, entity_id: str):
    p = s.get(SpaceElectricalPoint, entity_id)
    if p is None or p.is_deleted:
        return None
    sm = s.get(SpaceMeasurement, p.space_measurement_id)
    if sm is None:
        return None
    return bindings._set_context(s, sm.measurement_set_id, wall_id=p.space_wall_id, space_id=sm.space_id)


def _register() -> None:
    from veda.modules.attachments import registry

    if _after_write not in sets.AFTER_SPACE_WRITE:
        sets.PRE_WRITE.append(_pre_write)
        sets.AFTER_SPACE_WRITE.insert(0, _after_write)  # points first, then derivation reads the full tree
        sets.COPY_HOOKS.insert(0, _copy)
        sets.PRESENT_HOOKS.append(_present)
        EXTRA_SPACE_CHECKS.append(_checks)
        bindings.EXTRA_SET_ENTITIES = _extra_entities
        registry.bind(
            registry.EntityBinding("space_electrical_point", _point_binding, container_usage=bindings.set_usage)
        )


_register()
