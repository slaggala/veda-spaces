"""The property's measurement-to-quotation journey (blueprint §11.1 ``/leads/{id}/journey``, per property).

One read model for the staff workflow: the current verified measurement set, requirement decisions, and every scope,
BOQ, estimate and quotation revision with its upstream pins and computed staleness. Later phases register their own
sections (``SECTIONS``) so this module never imports them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.modules.mtq.models import MeasurementSet, Property

from . import boqs, lineage, rules, scopes, site
from .models import Boq, Requirement, Scope

SECTIONS: list[Callable[[Session, Any, Property], tuple[str, Any]]] = []


def view(s: Session, ctx, prop: Property) -> dict[str, Any]:
    current = site.current_verified_set(s, prop.id)
    sets = s.execute(
        sa.select(MeasurementSet).where(MeasurementSet.property_id == prop.id).order_by(MeasurementSet.revision_no)
    ).scalars()
    reqs = s.execute(sa.select(Requirement).where(Requirement.property_id == prop.id)).scalars().all()
    out: dict[str, Any] = {
        "property_id": prop.id,
        "property_number": prop.property_number,
        "lead_id": prop.lead_id,
        "current_measurement_set": (
            {
                "id": current.id,
                "revision_no": current.revision_no,
                "survey_level_code": current.survey_level_code,
                "verified_on": clock.to_rfc3339(current.verified_on) if current.verified_on else None,
                "snapshot_sha256": current.snapshot_sha256,
            }  # fmt: skip
            if current
            else None
        ),
        "measurement_sets": [
            {"id": m.id, "revision_no": m.revision_no, "status": m.status, "survey_level_code": m.survey_level_code}
            for m in sets
        ],  # fmt: skip
        "ruleset": {"version": rules.RULESET_VERSION, "status": rules.effective_status(), "sha256": rules.sha256()},
        "requirements": dict(Counter(r.status for r in reqs)),
        "scopes": [
            scopes.present(s, sc, full=False, state=lineage.scope_state(s, sc))
            for sc in s.execute(
                sa.select(Scope).where(Scope.property_id == prop.id).order_by(Scope.revision_no.desc())
            ).scalars()
        ],
        "boqs": [
            boqs.present(s, b, full=False)
            for b in s.execute(
                sa.select(Boq).where(Boq.property_id == prop.id).order_by(Boq.revision_no.desc())
            ).scalars()
        ],
    }
    for section in SECTIONS:
        key, value = section(s, ctx, prop)
        if value is not None:
            out[key] = value
    return out
