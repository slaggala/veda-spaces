"""Read-only view of one verified measurement set, as the B2 engines need it (B1 lineage, never bypassed).

Everything comes from B1's own presenters (``sets.present_measurement`` with the electrical hook), so derived areas,
perimeters and usable wall segments are exactly what B1 verified and sealed. Only in-scope, live spaces count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.errors import ApiError
from veda.modules.mtq import sets as site_sets
from veda.modules.mtq.models import MeasurementSet, Property, PropertySpace, SpaceMeasurement


@dataclass
class Facts:
    prop: Property
    mset: MeasurementSet
    spaces: dict[str, PropertySpace] = field(default_factory=dict)  # in-scope live spaces, walk order
    measured: dict[str, dict[str, Any]] = field(default_factory=dict)  # space id → presented measurement

    def m(self, space_id: str | None) -> dict[str, Any] | None:
        return self.measured.get(space_id) if space_id else None

    def walls(self, space_id: str | None) -> list[dict[str, Any]]:
        m = self.m(space_id)
        return [w for w in (m or {}).get("walls") or [] if w.get("wall_type_code") != "OPEN"]

    def ref(self, space_id: str | None, **extra) -> dict[str, Any]:
        """The measurement source of a value: set, revision and (when given) the space measurement and wall."""
        out: dict[str, Any] = {"measurement_set_id": self.mset.id, "measurement_revision_no": self.mset.revision_no}
        m = self.m(space_id)
        if m is not None:
            out["space_measurement_id"] = m["id"]
        out.update({k: v for k, v in extra.items() if v is not None})
        return out


def current_verified_set(s: Session, property_id: str) -> MeasurementSet | None:
    return s.execute(
        sa.select(MeasurementSet).where(MeasurementSet.property_id == property_id, MeasurementSet.status == "VERIFIED")
    ).scalar_one_or_none()


def require_current_verified(s: Session, prop: Property) -> MeasurementSet:
    mset = current_verified_set(s, prop.id)
    if mset is None:
        raise ApiError(409, "SET_NOT_VERIFIED", "This property has no verified measurement set yet; scope is built "
                       "from verified measurements only.")  # fmt: skip
    return mset


def load(s: Session, prop: Property, mset: MeasurementSet) -> Facts:
    site_sets.ensure_hooks()
    facts = Facts(prop=prop, mset=mset)
    spaces = s.execute(
        sa.select(PropertySpace)
        .where(PropertySpace.property_id == prop.id, PropertySpace.is_in_scope == sa.true())
        .order_by(PropertySpace.level_index, PropertySpace.sort_order)
    ).scalars()
    facts.spaces = {sp.id: sp for sp in spaces}
    for sm in s.execute(sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == mset.id)).scalars():
        if sm.space_id in facts.spaces:
            facts.measured[sm.space_id] = site_sets.present_measurement(s, sm)
    return facts
