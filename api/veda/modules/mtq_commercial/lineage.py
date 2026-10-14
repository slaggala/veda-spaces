"""Cross-phase lineage and staleness (blueprint §2.3, §14; instruction "cross-phase versioning").

Measurement revision → scope revision → BOQ revision → estimate revision → quotation version. Each downstream row
stores the id, revision number and sealed digest of what it was built from. Staleness is computed when read, never
written into history: an upstream change marks downstream artefacts stale (with reasons) and blocks the actions that
would carry them forward, until someone regenerates explicitly. Historical rows are never mutated.

Upstream changes that make a scope stale: a newer verified measurement set, a superseding scope revision, and any
change to the property's requirement decisions (accepting, excluding, re-deciding, adding or removing a requirement,
or changing its preferences), detected by the requirements digest pinned on the scope. A stale scope makes its BOQs
stale; a BOQ is also stale when it was superseded or when the rate card it was built against is no longer the active
card (its product structure may have changed). A stale BOQ makes its estimates stale, and a stale estimate blocks
quotation creation and issue.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel.jcs import canonical_bytes

from . import site
from .models import Boq, Requirement, Scope

# The decision fields of a requirement that feed a scope (free text is excluded: it carries no commercial meaning, and
# erasing it must not make history stale).
REQUIREMENT_FIELDS = ("id", "status", "necessity_code", "requirement_type_code", "space_id", "custom_label",
                      "anchor_wall_index", "preferences")  # fmt: skip


def requirements_sha256(s: Session, property_id: str) -> str:
    rows = s.execute(
        sa.select(Requirement).where(Requirement.property_id == property_id).order_by(Requirement.id)
    ).scalars()
    doc = [{k: getattr(r, k) for k in REQUIREMENT_FIELDS} for r in rows]
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


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
    elif requirements_sha256(s, scope.property_id) != scope.requirements_sha256:
        out.append({"code": "REQUIREMENTS_CHANGED", "message": "Requirement decisions changed after scope revision "
                    f"{scope.revision_no} was built; create a new scope revision."})  # fmt: skip
    return out


def scope_state(s: Session, scope: Scope) -> dict[str, Any]:
    return _state(scope_reasons(s, scope))


def boq_reasons(s: Session, boq: Boq) -> list[dict[str, Any]]:
    from . import estimator_card

    scope = s.get(Scope, boq.scope_id)
    assert scope is not None
    out = scope_reasons(s, scope)
    if boq.status == "SUPERSEDED":
        out.append({"code": "BOQ_SUPERSEDED", "message": f"BOQ revision {boq.revision_no} was superseded."})
    active = estimator_card.active_row(s)
    if active is None or active.id != boq.catalogue_card_id:
        out.append({"code": "CATALOGUE_CHANGED", "message": f"Rate card {boq.catalogue_card_version} is no longer the "
                    "active card; regenerate the BOQ against the card in force.",
                    "active_card_version": active.card_version if active else None})  # fmt: skip
    return out


def boq_state(s: Session, boq: Boq) -> dict[str, Any]:
    return _state(boq_reasons(s, boq))
