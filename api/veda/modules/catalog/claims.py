"""Governed claims: their validity at release, at activation and every time V3 content is served (B3 closure).

A governed claim is a copy record with claim governance (a claim record) or a promise record linked to its confirmed
promise-matrix row. The release gate approves claims once, but a claim is time-bounded and can lose its standing
after activation. `problems` is therefore evaluated by release validation, by activation, and by every public serve
(catalog, estimate and replay).

A claim is valid only while all of these hold:
- it is approved and not withdrawn;
- it is in effect, and today is before its review date (it lapses on that date);
- an accountable owner remains assigned;
- its environment is permitted;
- it still applies to every package, product or room it is shown for.

Changes after activation are recorded as append-only `CatalogClaimControl` rows: withdraw, unassign or assign an owner,
restrict applicability, reinstate. The latest row per claim wins. Any problem fails closed.
"""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.kernel import clock
from veda.modules.estimator import promise_matrix

from . import kinds, text
from .models import CLAIM_CONTROL_ACTIONS, CatalogClaimControl, CatalogRecord

BUSINESS_TZ = ZoneInfo("Asia/Kolkata")


class ClaimError(ValueError):
    pass


def today() -> date:
    """The business date (India) from the platform clock, so tests control it."""
    return clock.now().astimezone(BUSINESS_TZ).date()


def controls(s: Session) -> dict[str, CatalogClaimControl]:
    """The latest control row per claim key (created order; ids are time-ordered UUIDv7)."""
    rows = s.execute(sa.select(CatalogClaimControl).order_by(CatalogClaimControl.created_on, CatalogClaimControl.id))
    return {row.copy_key: row for row in rows.scalars()}


def control(s: Session, copy_key: str, action: str, reason: str, *, owner: str | None = None,
            applies_to: dict | None = None) -> CatalogClaimControl:  # fmt: skip
    """Record a change to a released claim's standing. It takes effect on the next public serve, with no release."""
    if action not in CLAIM_CONTROL_ACTIONS:
        raise ClaimError(f"unknown claim control {action!r}")
    if len((reason or "").strip()) < 10:
        raise ClaimError("say why (at least 10 characters)")
    found = s.execute(
        sa.select(CatalogRecord.document).where(CatalogRecord.kind == "copy", CatalogRecord.record_key == copy_key)
    ).scalars().first()  # fmt: skip
    if found is None:
        raise ClaimError(f"no copy record {copy_key}")
    model = kinds.load_model("copy", found)
    if not (isinstance(model, kinds.Copy) and (model.claim is not None or model.promise)):
        raise ClaimError(f"copy {copy_key} is not a governed claim")
    if action == "ASSIGN_OWNER" and not promise_matrix._named(owner):
        raise ClaimError("name the accountable owner (a role)")
    scope = None
    if action == "RESTRICT_APPLICABILITY":
        scope = kinds.AppliesTo.model_validate(applies_to or {}).model_dump(mode="json")
    row = CatalogClaimControl(copy_key=copy_key, action=action, owner=owner if action == "ASSIGN_OWNER" else None,
                              scope=scope, reason=reason.strip()[:300])  # fmt: skip
    s.add(row)
    s.flush()
    return row


def governed(cat) -> dict[str, kinds.Copy]:
    """The release's governed claims: claim records and promise records."""
    return {k: m for k, m in cat.of(kinds.Copy).items() if m.claim is not None or m.promise}


def _uses(cat, key: str) -> list[tuple[str, str]]:
    """Where a claim is shown: (kind of scope, key), from package badges and summaries, materials and hardware."""
    out = []
    for pkey, pkg in cat.of(kinds.Package).items():
        if key in (pkg.badge, pkg.public_summary, pkg.warranty_copy, *pkg.material_promise, *pkg.hardware_promise):
            out.append(("package", pkey))
    for kind in (kinds.Material, kinds.Hardware):
        for m in cat.of(kind).values():
            if key in m.statements:
                out.extend(("product", p) for p in getattr(m, "products", ()) or ())
                out.extend(("room", r) for r in getattr(m, "rooms", ()) or ())
    return out


def _applies(scope: kinds.AppliesTo, cat, use: tuple[str, str]) -> bool:
    """A use is covered when the scope names it in its dimension; a dimension the scope leaves empty is unconstrained."""
    kind, key = use
    if kind == "package":
        return not scope.packages or key in scope.packages
    if kind == "product":
        return not scope.products or key in scope.products
    if not scope.rooms:
        return True
    codes = {r.room_code for k, r in cat.of(kinds.RoomTemplate).items() if k in scope.rooms}
    return key in scope.rooms or key in codes


def problems(cat, *, on: date | None = None, env: str | None = None,
             current: dict[str, CatalogClaimControl] | None = None) -> list[str]:  # fmt: skip
    """Why a release's governed claims may not be shown now (empty when every one is valid)."""
    on = on or today()
    env = env or settings().env
    current = current or {}
    out = []
    for key, copy in sorted(governed(cat).items()):
        ctl = current.get(key)
        action = ctl.action if ctl is not None else None
        if action == "WITHDRAW":
            out.append(f"copy {key}: claim withdrawn after release")
            continue
        scope = copy.applies_to
        if action == "RESTRICT_APPLICABILITY" and ctl is not None and ctl.scope is not None:
            scope = kinds.AppliesTo.model_validate(ctl.scope)
        c = copy.claim
        owner = c.owner if c is not None else (copy.governance.owner if copy.governance else None)
        if action == "ASSIGN_OWNER" and ctl is not None:
            owner = ctl.owner
        if action == "UNASSIGN_OWNER" or not promise_matrix._named(owner):
            out.append(f"copy {key}: claim has no responsible owner")
        if c is not None:
            if c.status != "APPROVED":
                out.append(f"copy {key}: claim is {c.status}, not approved")
            if not promise_matrix._named(c.approver):
                out.append(f"copy {key}: claim has no approver")
            absolute = text.absolute_in(copy.statement) or set(c.categories) & {"ranking", "price"}
            if absolute and not promise_matrix._named(c.backup_owner):
                out.append(f"copy {key}: an absolute, ranking or price claim needs a backup owner")
            if c.effective_from > on:
                out.append(f"copy {key}: claim is not in effect until {c.effective_from.isoformat()}")
            if c.review_by is not None and c.review_by <= on:
                out.append(f"copy {key}: claim review date {c.review_by.isoformat()} has been reached")
            if env not in c.environments:
                out.append(f"copy {key}: claim is not approved for the {env} environment")
        if scope is not None:
            for use in _uses(cat, key):
                if not _applies(scope, cat, use):
                    out.append(f"copy {key}: claim does not apply to the {use[0]} {use[1]} it is shown for")
    return out


def valid_until(cat, *, on: date | None = None) -> date | None:
    """The first date on which a currently valid claim stops (or starts) being valid: public caches end there."""
    on = on or today()
    edges = []
    for copy in governed(cat).values():
        c = copy.claim
        if c is None:
            continue
        edges += [d for d in (c.review_by, c.effective_from) if d is not None and d > on]
    return min(edges) if edges else None
