"""Scope revisions (blueprint §8.1, §14; instruction B2.3).

A scope revision is built from the property's ACCEPTED requirements over its current verified measurement set: one
item per requirement, with the catalogue mapping and the resolved card inputs of its item type. A new revision carries
staff edits (options, finish, dimension overrides with their reason, inclusion) from the latest earlier revision of the
same requirement (``carried_from_item_id``), so a re-measure keeps decisions while the derived values follow the new
measurements.

Only a DRAFT changes. CONFIRMED seals it (canonical JSON digest); confirming needs the measurement set to still be the
property's current verified set and every requirement to be decided (nothing PROPOSED). Confirming supersedes the
previous confirmed revision; nothing downstream is changed, it is reported stale until regenerated.
"""

from __future__ import annotations

import hashlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq.models import Property

from . import quantity, requirements, rules, site
from .models import Requirement, Scope, ScopeItem

EDITABLE = ("options", "finish_code", "material_key", "inclusion_code", "label", "notes")


def _latest(s: Session, property_id: str, *statuses: str) -> Scope | None:
    return s.execute(
        sa.select(Scope)
        .where(Scope.property_id == property_id, Scope.status.in_(statuses))
        .order_by(Scope.revision_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def _next_revision(s: Session, property_id: str) -> int:
    top = s.execute(
        sa.select(sa.func.max(Scope.revision_no))
        .where(Scope.property_id == property_id)
        .execution_options(include_deleted=True)
    ).scalar()
    return int(top or 0) + 1


def require_draft(scope: Scope) -> None:
    if scope.status != "DRAFT":
        raise ApiError(409, "SCOPE_FROZEN", f"Scope revision {scope.revision_no} is {scope.status.lower()}; "
                       "create a new revision to change it.", extra={"status": scope.status})  # fmt: skip


def _label(req: Requirement, itype: rules.ItemType) -> str:
    return (req.custom_label or itype.label)[:120]


def _resolve(item: ScopeItem, req: Requirement, facts: site.Facts) -> None:
    """Recompute the item's card inputs and rule-set options from the measurement set (never from a client)."""
    itype = rules.item_type(item.item_type_code)
    dims = quantity.derive_inputs(itype, facts, item.space_id, item.anchor_wall_index)
    ruled = quantity.options_from_rules(itype, facts, item.space_id)
    item.dimensions = {"inputs": dims, "option_rules": ruled}
    item.dimension_source_code = quantity.worst_source(dims, item.dimension_overrides or {})


def _effective_options(item: ScopeItem, req: Requirement) -> dict[str, str]:
    itype = rules.item_type(item.item_type_code)
    ruled = {k: v["value"] for k, v in ((item.dimensions or {}).get("option_rules") or {}).items()}
    prefs = (req.preferences or {}).get("options") or {}
    return {**ruled, **prefs, **(item.options or {}), **itype.fixed_options}


def effective_options(item: ScopeItem, req: Requirement) -> dict[str, str]:
    return _effective_options(item, req)


def _item_for(req: Requirement, previous: ScopeItem | None, sort: int) -> ScopeItem:
    itype = rules.item_type(req.requirement_type_code)
    prefs = req.preferences or {}
    item = ScopeItem(
        requirement_id=req.id,
        space_id=req.space_id,
        item_type_code=req.requirement_type_code,
        card_product_code=itype.card_product,
        label=_label(req, itype),
        origin_code=requirements.ORIGIN_OF_SOURCE[req.source_code],
        necessity_code=req.necessity_code,
        inclusion_code="OPTIONAL" if req.necessity_code == "OPTIONAL" else "INCLUDED",
        rule_key=(req.source_ref or {}).get("rule_key"),
        anchor_wall_index=req.anchor_wall_index,
        options={},
        finish_code=prefs.get("finish_code"),
        material_key=prefs.get("material_key"),
        dimension_overrides={},
        dimension_source_code="ASSUMED",
        sort_order=sort,
    )
    if previous is not None:
        item.carried_from_item_id = previous.id
        for f in EDITABLE:
            setattr(item, f, getattr(previous, f))
        item.dimension_overrides = dict(previous.dimension_overrides or {})
        item.override_reason = previous.override_reason
    return item


def _populate(s: Session, scope: Scope, facts: site.Facts, kept: dict[str, ScopeItem] | None = None) -> dict[str, Any]:
    reqs = s.execute(sa.select(Requirement).where(Requirement.property_id == scope.property_id)).scalars().all()
    carried_from = _latest(s, scope.property_id, "CONFIRMED", "SUPERSEDED")
    previous: dict[str, ScopeItem] = {}
    if carried_from is not None:
        previous = {
            i.requirement_id: i
            for i in s.execute(sa.select(ScopeItem).where(ScopeItem.scope_id == carried_from.id)).scalars()
        }
    order = {sid: n for n, sid in enumerate(facts.spaces)}
    accepted = sorted(
        (r for r in reqs if r.status == "ACCEPTED"),
        key=lambda r: (r.space_id is None, order.get(r.space_id or "", 999), r.requirement_type_code, r.dedupe_key),
    )
    for n, req in enumerate(accepted, start=1):
        item = _item_for(req, previous.get(req.id), n * 10)
        old = (kept or {}).get(req.id)
        if old is not None:  # a refreshed draft keeps its own edits
            for f in EDITABLE:
                setattr(item, f, getattr(old, f))
            item.dimension_overrides = dict(old.dimension_overrides or {})
            item.override_reason = old.override_reason
            item.carried_from_item_id = old.carried_from_item_id
        item.scope_id = scope.id
        _resolve(item, req, facts)
        s.add(item)
    scope.exclusions = exclusions(s, reqs, requirements.spaces_of(s, facts.prop))
    return {
        "items": len(accepted),
        "carried_from_scope_id": carried_from.id if carried_from else None,
        "undecided_requirement_ids": [r.id for r in reqs if r.status == "PROPOSED"],
        "excluded": len(scope.exclusions),
    }


def exclusions(s: Session, reqs, spaces) -> list[dict[str, Any]]:
    out = []
    for r in reqs:
        if r.status not in ("EXCLUDED", "NOT_APPLICABLE"):
            continue
        sp = spaces.get(r.space_id) if r.space_id else None
        out.append({"requirement_id": r.id, "space_id": r.space_id, "space_label": sp.label if sp else None,
                    "requirement_type_code": r.requirement_type_code,
                    "label": r.custom_label or rules.item_type(r.requirement_type_code).label,
                    "status": r.status, "necessity_code": r.necessity_code})  # fmt: skip
    return sorted(out, key=lambda e: (e["space_label"] or "", e["label"]))


def create(s: Session, ctx, prop: Property, body) -> Scope:
    mset = site.require_current_verified(s, prop)
    draft = _latest(s, prop.id, "DRAFT")
    if draft is not None:
        raise ApiError(409, "DRAFT_EXISTS", f"Scope revision {draft.revision_no} is still a draft; refresh, edit or "
                       "confirm it.", extra={"scope_id": draft.id})  # fmt: skip
    rs = rules.load()
    previous = _latest(s, prop.id, "CONFIRMED")
    scope = Scope(
        lead_id=prop.lead_id,
        property_id=prop.id,
        measurement_set_id=mset.id,
        measurement_revision_no=mset.revision_no,
        measurement_snapshot_sha256=mset.snapshot_sha256 or "",  # a verified set is always sealed
        revision_no=_next_revision(s, prop.id),
        supersedes_scope_id=previous.id if previous else None,
        status="DRAFT",
        tier_code=body.tier_code,
        ruleset_version=rs.ruleset_version,
        ruleset_sha256=rules.sha256(),
        ruleset_status=rules.effective_status(),
        notes=body.notes,
    )
    s.add(scope)
    s.flush()
    facts = site.load(s, prop, mset)
    scope.generation_run = _populate(s, scope, facts)
    s.flush()
    return scope


def refresh(s: Session, ctx, scope: Scope, prop: Property) -> Scope:
    """Re-read the accepted requirements and the current verified set into the draft, keeping the draft's edits."""
    require_draft(scope)
    mset = site.require_current_verified(s, prop)
    kept = {i.requirement_id: i for i in items(s, scope)}
    from veda.kernel import audit_hook

    for i in kept.values():
        audit_hook.soft_delete(i)
    s.flush()
    scope.measurement_set_id, scope.measurement_revision_no = mset.id, mset.revision_no
    scope.measurement_snapshot_sha256 = mset.snapshot_sha256 or ""  # a verified set is always sealed
    facts = site.load(s, prop, mset)
    run = _populate(s, scope, facts, kept)
    scope.generation_run = {**run, "refreshed_on": clock.to_rfc3339(db.tx_time(s))}
    s.flush()
    return scope


def update_item(s: Session, ctx, item: ScopeItem, scope: Scope, body) -> ScopeItem:
    require_draft(scope)
    data = body.model_dump(exclude_unset=True)
    itype = rules.item_type(item.item_type_code)
    if "options" in data:
        opts = dict(body.options or {})
        fixed = set(opts) & set(itype.fixed_options)
        if fixed:
            raise ApiError(422, "VALIDATION_FAILED", f"{', '.join(sorted(fixed))} is fixed by the item type.",
                           errors=[field_error("options", "FIXED_OPTION", "Fixed by the item type.")])  # fmt: skip
        item.options = opts
    for f in ("finish_code", "material_key", "inclusion_code", "notes"):
        if f in data:
            setattr(item, f, data[f])
    if "label" in data and body.label:
        item.label = body.label
    if "dimension_overrides" in data:
        overrides = {k: str(v) for k, v in (body.dimension_overrides or {}).items()}
        unknown = set(overrides) - set(itype.inputs)
        if unknown:
            raise ApiError(422, "VALIDATION_FAILED", f"{itype.label} has no input {', '.join(sorted(unknown))}.",
                           errors=[field_error("dimension_overrides", "UNKNOWN_INPUT", "Unknown input.")])  # fmt: skip
        if overrides and not (body.override_reason or "").strip():
            raise ApiError(422, "OVERRIDE_REASON_REQUIRED", "Say why the measured value is overridden.",
                           errors=[field_error("override_reason", "REQUIRED", "A reason is required.")])  # fmt: skip
        item.dimension_overrides = overrides
        item.override_reason = body.override_reason.strip() if overrides and body.override_reason else None
    if item.inclusion_code == "EXCLUDED" and item.necessity_code == "MANDATORY" and not (item.notes or "").strip():
        raise ApiError(422, "REASON_REQUIRED", "Note why a mandatory item is excluded.",
                       errors=[field_error("notes", "REQUIRED", "A note is required.")])  # fmt: skip
    item.dimension_source_code = quantity.worst_source((item.dimensions or {}).get("inputs") or {},
                                                       item.dimension_overrides or {})  # fmt: skip
    return item


def confirm(s: Session, ctx, scope: Scope, prop: Property) -> Scope:
    require_draft(scope)
    current = site.current_verified_set(s, prop.id)
    if current is None or current.id != scope.measurement_set_id:
        raise ApiError(409, "STALE_MEASUREMENT", "A newer verified measurement set exists; refresh the draft first.",
                       extra={"current_measurement_set_id": current.id if current else None})  # fmt: skip
    undecided = (
        s.execute(sa.select(Requirement.id).where(Requirement.property_id == prop.id, Requirement.status == "PROPOSED"))
        .scalars()
        .all()
    )
    if undecided:
        raise ApiError(409, "UNDECIDED_REQUIREMENTS", f"{len(undecided)} recommendation(s) are still proposed: accept "
                       "or exclude each before confirming.", extra={"requirement_ids": list(undecided)})  # fmt: skip
    accepted = set(
        s.execute(
            sa.select(Requirement.id).where(Requirement.property_id == prop.id, Requirement.status == "ACCEPTED")
        ).scalars()
    )
    in_scope = {i.requirement_id for i in items(s, scope)}
    if accepted != in_scope:
        raise ApiError(409, "SCOPE_OUT_OF_DATE", "Requirements changed after this draft was built; refresh it first.",
                       extra={"missing": sorted(accepted - in_scope), "extra": sorted(in_scope - accepted)})  # fmt: skip
    reqs = s.execute(sa.select(Requirement).where(Requirement.property_id == prop.id)).scalars().all()
    scope.exclusions = exclusions(s, reqs, requirements.spaces_of(s, prop))
    previous = _latest(s, prop.id, "CONFIRMED")
    if previous is not None:
        previous.status = "SUPERSEDED"
        s.flush()  # one CONFIRMED per property (partial unique index): the old one steps aside first
    digest = snapshot_sha256(s, scope)  # computed first: the sealed-row CHECK needs it with the status
    scope.status, scope.confirmed_on, scope.confirmed_by = "CONFIRMED", db.tx_time(s), ctx.user.id
    scope.snapshot_sha256 = digest
    return scope


def snapshot(s: Session, scope: Scope) -> dict[str, Any]:
    return {
        "scope_id": scope.id,
        "revision_no": scope.revision_no,
        "measurement_set_id": scope.measurement_set_id,
        "measurement_snapshot_sha256": scope.measurement_snapshot_sha256,
        "ruleset": [scope.ruleset_version, scope.ruleset_sha256],
        "tier_code": scope.tier_code,
        "exclusions": scope.exclusions,
        "items": [
            {
                k: getattr(i, k)
                for k in (
                    "id",
                    "requirement_id",
                    "space_id",
                    "item_type_code",
                    "card_product_code",
                    "label",
                    "origin_code",
                    "necessity_code",
                    "inclusion_code",
                    "rule_key",
                    "anchor_wall_index",
                    "options",
                    "finish_code",
                    "material_key",
                    "dimensions",
                    "dimension_overrides",
                    "override_reason",
                    "dimension_source_code",
                )
            }  # fmt: skip
            for i in items(s, scope)
        ],
    }


def snapshot_sha256(s: Session, scope: Scope) -> str:
    return hashlib.sha256(canonical_bytes(snapshot(s, scope))).hexdigest()


def items(s: Session, scope: Scope) -> list[ScopeItem]:
    return list(
        s.execute(
            sa.select(ScopeItem).where(ScopeItem.scope_id == scope.id).order_by(ScopeItem.sort_order, ScopeItem.id)
        ).scalars()
    )


def latest_confirmed(s: Session, property_id: str) -> Scope | None:
    return _latest(s, property_id, "CONFIRMED")


def present_item(item: ScopeItem, req: Requirement | None, spaces: dict) -> dict[str, Any]:
    sp = spaces.get(item.space_id) if item.space_id else None
    itype = rules.item_type(item.item_type_code)
    return {
        "id": item.id,
        "version": item.version,
        "scope_id": item.scope_id,
        "requirement_id": item.requirement_id,
        "space_id": item.space_id,
        "space_label": sp.label if sp else None,
        "item_type_code": item.item_type_code,
        "card_product_code": item.card_product_code,
        "catalogue_mapped": item.card_product_code is not None,
        "unmapped_reason": itype.unmapped_reason,
        "label": item.label,
        "origin_code": item.origin_code,
        "necessity_code": item.necessity_code,
        "inclusion_code": item.inclusion_code,
        "rule_key": item.rule_key,
        "anchor_wall_index": item.anchor_wall_index,
        "options": item.options or {},
        "effective_options": _effective_options(item, req) if req else item.options or {},
        "finish_code": item.finish_code,
        "material_key": item.material_key,
        "inputs": (item.dimensions or {}).get("inputs") or {},
        "option_rules": (item.dimensions or {}).get("option_rules") or {},
        "dimension_overrides": item.dimension_overrides or {},
        "override_reason": item.override_reason,
        "dimension_source_code": item.dimension_source_code,
        "carried_from_item_id": item.carried_from_item_id,
        "notes": item.notes,
    }


def present(s: Session, scope: Scope, *, full: bool = True, state: dict | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": scope.id,
        "version": scope.version,
        "property_id": scope.property_id,
        "lead_id": scope.lead_id,
        "revision_no": scope.revision_no,
        "status": scope.status,
        "tier_code": scope.tier_code,
        "measurement_set_id": scope.measurement_set_id,
        "measurement_revision_no": scope.measurement_revision_no,
        "measurement_snapshot_sha256": scope.measurement_snapshot_sha256,
        "supersedes_scope_id": scope.supersedes_scope_id,
        "ruleset_version": scope.ruleset_version,
        "ruleset_sha256": scope.ruleset_sha256,
        "ruleset_status": scope.ruleset_status,
        "generation_run": scope.generation_run or {},
        "exclusions": scope.exclusions or [],
        "confirmed_on": clock.to_rfc3339(scope.confirmed_on) if scope.confirmed_on else None,
        "confirmed_by": scope.confirmed_by,
        "snapshot_sha256": scope.snapshot_sha256,
        "notes": scope.notes,
        "created_on": clock.to_rfc3339(scope.created_on),
    }
    if state is not None:
        out["lineage"] = state
    if full:
        rows = items(s, scope)
        reqs = {
            r.id: r
            for r in s.execute(
                sa.select(Requirement).where(Requirement.id.in_([i.requirement_id for i in rows]))
            ).scalars()
        }
        spaces = requirements.spaces_of(s, s.get(Property, scope.property_id))  # type: ignore[arg-type]  # the property row exists (FK)
        out["items"] = [present_item(i, reqs.get(i.requirement_id), spaces) for i in rows]
    return out
