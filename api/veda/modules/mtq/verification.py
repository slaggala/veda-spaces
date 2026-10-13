"""Measurement verification (MTQ B1-T06 baseline; the full Lite and Full rules arrive with B1-T07).

``completeness`` gates submission; ``summary`` is the set's computed summary (blueprint §4.1 ``summary``).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import MeasurementSet, PropertySpace, SpaceMeasurement, SpaceOpening, SpaceWall


def in_scope_spaces(s: Session, mset: MeasurementSet) -> list[PropertySpace]:
    return list(
        s.execute(
            sa.select(PropertySpace)
            .where(PropertySpace.property_id == mset.property_id, PropertySpace.is_in_scope == sa.true())
            .order_by(PropertySpace.level_index, PropertySpace.sort_order)
        ).scalars()
    )


def measurements(s: Session, mset: MeasurementSet) -> dict[str, SpaceMeasurement]:
    return {
        sm.space_id: sm
        for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == mset.id)).scalars()
    }


def completeness(s: Session, mset: MeasurementSet) -> list[dict[str, Any]]:
    """Every in-scope space has a measurement its surveyor marked complete."""
    by_space = measurements(s, mset)
    problems = []
    for sp in in_scope_spaces(s, mset):
        sm = by_space.get(sp.id)
        if sm is None:
            problems.append({"pointer": f"/spaces/{sp.id}", "code": "NOT_MEASURED", "space": sp.label})
        elif not sm.is_complete:
            problems.append({"pointer": f"/spaces/{sp.id}", "code": "NOT_COMPLETE", "space": sp.label})
    return problems


def summary(s: Session, mset: MeasurementSet) -> dict[str, Any]:
    by_space = measurements(s, mset)
    ids = [sm.id for sm in by_space.values()]
    walls = s.execute(sa.select(sa.func.count(SpaceWall.id)).where(SpaceWall.space_measurement_id.in_(ids))).scalar()
    openings = s.execute(
        sa.select(sa.func.count(SpaceOpening.id))
        .join(SpaceWall, SpaceWall.id == SpaceOpening.space_wall_id)
        .where(SpaceWall.space_measurement_id.in_(ids))
    ).scalar()
    floor = sum(sm.derived_floor_area_sqft_centi or 0 for sm in by_space.values())
    wall_area = sum(sm.derived_wall_area_net_sqft_centi or 0 for sm in by_space.values())
    return {
        "survey_level": mset.survey_level_code,
        "spaces": len(by_space),
        "walls": int(walls or 0),
        "openings": int(openings or 0),
        "total_floor_area_sqft_centi": floor,
        "total_wall_area_net_sqft_centi": wall_area,
    }
