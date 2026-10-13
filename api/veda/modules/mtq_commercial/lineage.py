"""Cross-phase lineage and staleness (blueprint §2.3, §14; instruction "cross-phase versioning").

Measurement revision → scope revision → BOQ revision → estimate revision → quotation version. Each downstream row
stores the id, revision number and sealed digest of what it was built from. Staleness is computed when read, never
written into history: an upstream change marks downstream artefacts stale (with reasons) and blocks the actions that
would carry them forward, until someone regenerates explicitly. Historical rows are never mutated.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from . import site
from .models import Boq, Scope


def _state(reasons: list[dict[str, Any]]) -> dict[str, Any]:
    return {"stale": bool(reasons), "reasons": reasons}


def scope_reasons(s: Session, scope: Scope) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    current = site.current_verified_set(s, scope.property_id)
    if current is None or current.id != scope.measurement_set_id:
        out.append({"code": "MEASUREMENT_REVISED", "message": "A newer verified measurement set exists.",
                    "current_measurement_set_id": current.id if current else None,
                    "current_revision_no": current.revision_no if current else None})  # fmt: skip
    if scope.status == "SUPERSEDED":
        out.append({"code": "SCOPE_SUPERSEDED", "message": f"Scope revision {scope.revision_no} was superseded."})
    return out


def scope_state(s: Session, scope: Scope) -> dict[str, Any]:
    return _state(scope_reasons(s, scope))


def boq_reasons(s: Session, boq: Boq) -> list[dict[str, Any]]:
    scope = s.get(Scope, boq.scope_id)
    assert scope is not None
    out = scope_reasons(s, scope)
    if boq.status == "SUPERSEDED":
        out.append({"code": "BOQ_SUPERSEDED", "message": f"BOQ revision {boq.revision_no} was superseded."})
    return out


def boq_state(s: Session, boq: Boq) -> dict[str, Any]:
    return _state(boq_reasons(s, boq))
