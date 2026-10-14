"""Requirements (blueprint §7; owner instruction B2.1-B2.3): what each space, or the project, needs, with provenance.

Seeding evaluates the versioned ruleset against the property's current verified measurement set. A rule fires from the
space's type (a template recommendation: source SURVEY_TEMPLATE, origin RECOMMENDED) or from a measured fact (a tagged
wall, a captured electrical point, a proposed partition: source MEASUREMENT_RULE, origin AUTO). Seeded requirements
are PROPOSED: nothing is accepted without a staff decision, and a decided requirement is never re-proposed or changed
by a later seed. Staff additions (STAFF_SELECTION, CUSTOMER_REQUEST, MANUAL) are accepted by the act of adding them.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error, not_found
from veda.modules.mtq.models import Property, PropertySpace

from . import rules, site
from .models import Requirement

ORIGIN_OF_SOURCE = {
    "MEASUREMENT_RULE": "AUTO",
    "SURVEY_TEMPLATE": "RECOMMENDED",
    "CUSTOMER_REQUEST": "CUSTOMER_REQUESTED",
    "STAFF_SELECTION": "MANUAL",
    "MANUAL": "MANUAL",
}


def dedupe_key(space_id: str | None, type_code: str, anchor: int | None, instance_no: int) -> str:
    where = space_id or "PROJECT"
    return f"{where}:{type_code}:" + (f"W{anchor}" if anchor is not None else f"I{instance_no}")


def _candidates(facts: site.Facts) -> list[dict[str, Any]]:
    """Every (rule, space, anchor) the ruleset fires on for this verified set."""
    rs = rules.load()
    out: list[dict[str, Any]] = []
    for rule in rs.rules:
        if rule.project:
            if _project_when(rule.when, facts):
                out.append({"rule": rule, "space": None, "anchor": None, "fact": _project_fact(rule.when)})
            continue
        for sid, sp in facts.spaces.items():
            if rule.space_types is not None and sp.space_type_code not in rule.space_types:
                continue
            walls = facts.walls(sid)
            if rule.per == "tagged_wall":
                for w in walls:
                    if rule.tag in (w.get("usable_for_code") or []):
                        out.append({"rule": rule, "space": sp, "anchor": w["wall_index"],
                                    "fact": f"W{w['wall_index']} tagged {rule.tag}"})  # fmt: skip
                continue
            if rule.per == "any_tagged_wall":
                tagged = [w["wall_index"] for w in walls if rule.tag in (w.get("usable_for_code") or [])]
                if tagged:
                    out.append({"rule": rule, "space": sp, "anchor": None,
                                "fact": f"{', '.join(f'W{i}' for i in tagged)} tagged {rule.tag}"})  # fmt: skip
                continue
            fact = _space_when(rule.when, facts, sid)
            if fact is not None:
                out.append({"rule": rule, "space": sp, "anchor": None, "fact": fact})
    return out


def _space_when(when: dict[str, Any], facts: site.Facts, sid: str) -> str | None:
    if not when:
        return f"space type {facts.spaces[sid].space_type_code}"
    m = facts.m(sid) or {}
    if when.get("proposed_partition"):
        walls = [w for w in m.get("walls") or [] if w.get("is_proposed")]
        return f"proposed partition W{walls[0]['wall_index']}" if walls else None
    if when.get("opening_types"):
        wanted = set(when["opening_types"])
        for w in m.get("walls") or []:
            for o in w.get("openings") or []:
                if o["opening_type_code"] in wanted:
                    return f"{o['opening_type_code'].lower()} on W{w['wall_index']}"
        return None
    return None


def _project_when(when: dict[str, Any], facts: site.Facts) -> bool:
    elec = when.get("electrical")
    if not elec:
        return True
    from .quantity import measured_count

    types = tuple(elec["types"]) if elec.get("types") else None
    n, _ = measured_count(facts, types, tuple(elec.get("statuses") or ()))
    return n > 0


def _project_fact(when: dict[str, Any]) -> str:
    elec = when.get("electrical")
    if not elec:
        return "project-level recommendation"
    return "captured electrical points: " + "/".join(elec.get("statuses") or [])


def seed(s: Session, ctx, prop: Property) -> dict[str, Any]:
    """Propose what the ruleset recommends for the current verified set. Idempotent: an existing requirement with the
    same key (whatever its status) is left as it is."""
    mset = site.require_current_verified(s, prop)
    facts = site.load(s, prop, mset)
    existing = set(
        s.execute(sa.select(Requirement.dedupe_key).where(Requirement.property_id == prop.id)).scalars().all()
    )
    created: list[Requirement] = []
    skipped = 0
    for c in _candidates(facts):
        rule, sp, anchor = c["rule"], c["space"], c["anchor"]
        key = dedupe_key(sp.id if sp else None, rule.item, anchor, 1)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        req = Requirement(
            lead_id=prop.lead_id,
            property_id=prop.id,
            space_id=sp.id if sp else None,
            requirement_type_code=rule.item,
            necessity_code=rule.necessity,
            status="PROPOSED",
            source_code="MEASUREMENT_RULE" if rule.origin == "AUTO" else "SURVEY_TEMPLATE",
            source_ref={
                "rule_key": rule.key,
                "origin": rule.origin,
                "fact": c["fact"],
                "ruleset_version": rules.RULESET_VERSION,
                "ruleset_sha256": rules.sha256(),
                "ruleset_status": rules.effective_status(),
                "measurement_set_id": mset.id,
                "measurement_revision_no": mset.revision_no,
                "template_key": sp.space_template_key if sp else None,
                "template_version": sp.template_version if sp else None,
            },
            anchor_wall_index=anchor,
            instance_no=1,
            dedupe_key=key,
            preferences={},
        )
        s.add(req)
        created.append(req)
    s.flush()
    return {"created": len(created), "unchanged": skipped, "measurement_set_id": mset.id,
            "measurement_revision_no": mset.revision_no, "ruleset_version": rules.RULESET_VERSION,
            "ruleset_status": rules.effective_status()}  # fmt: skip


def _space_of(s: Session, prop: Property, space_id: str | None) -> PropertySpace | None:
    if space_id is None:
        return None
    sp = s.get(PropertySpace, space_id)
    if sp is None or sp.is_deleted or sp.property_id != prop.id:
        raise ApiError(422, "VALIDATION_FAILED", "The space is not part of this property.",
                       errors=[field_error("space_id", "UNKNOWN_SPACE", "Not a space of this property.")])  # fmt: skip
    return sp


def add(s: Session, ctx, prop: Property, body) -> Requirement:
    """A staff selection, a customer request or a manual addition: accepted by being added (the act is the decision)."""
    sp = _space_of(s, prop, body.space_id)
    itype = rules.item_type(body.requirement_type_code)
    if body.requirement_type_code == "CUSTOM" and not body.custom_label:
        raise ApiError(422, "VALIDATION_FAILED", "Describe the custom item.",
                       errors=[field_error("custom_label", "REQUIRED", "A label is required.")])  # fmt: skip
    if itype.project and sp is not None:
        raise ApiError(422, "VALIDATION_FAILED", f"{itype.label} is a project-level item; leave the space empty.",
                       errors=[field_error("space_id", "PROJECT_LEVEL", "Project-level item.")])  # fmt: skip
    if not itype.project and sp is None and body.requirement_type_code != "CUSTOM":
        raise ApiError(422, "VALIDATION_FAILED", f"Choose the space for {itype.label.lower()}.",
                       errors=[field_error("space_id", "REQUIRED", "Choose a space.")])  # fmt: skip
    taken = set(
        s.execute(
            sa.select(Requirement.dedupe_key).where(
                Requirement.property_id == prop.id,
                Requirement.requirement_type_code == body.requirement_type_code,
                Requirement.space_id.is_(None) if sp is None else Requirement.space_id == sp.id,
            )
        ).scalars()
    )
    if body.anchor_wall_index is not None:
        key = dedupe_key(sp.id if sp else None, body.requirement_type_code, body.anchor_wall_index, 1)
        if key in taken:
            raise ApiError(409, "DUPLICATE_SCOPE", "This space already has that item on that wall.",
                           extra={"dedupe_key": key})  # fmt: skip
        instance = 1
    else:
        instance = 1
        while dedupe_key(sp.id if sp else None, body.requirement_type_code, None, instance) in taken:
            instance += 1
        key = dedupe_key(sp.id if sp else None, body.requirement_type_code, None, instance)
    now = db.tx_time(s)
    req = Requirement(
        lead_id=prop.lead_id,
        property_id=prop.id,
        space_id=sp.id if sp else None,
        requirement_type_code=body.requirement_type_code,
        custom_label=body.custom_label,
        necessity_code=body.necessity_code,
        status="ACCEPTED",
        source_code=body.source_code,
        source_ref={"added_by": ctx.user.id, "origin": ORIGIN_OF_SOURCE[body.source_code]},
        anchor_wall_index=body.anchor_wall_index,
        instance_no=instance,
        dedupe_key=key,
        preferences=body.preferences.model_dump(exclude_none=True) if body.preferences else {},
        notes=body.notes,
        decided_by=ctx.user.id,
        decided_on=now,
        decision_reason=body.reason,
    )
    s.add(req)
    s.flush()
    return req


def decide(s: Session, ctx, req: Requirement, body) -> Requirement:
    """Accept, exclude, mark not applicable, or return to proposed. Excluding a MANDATORY requirement needs a reason;
    the audit trail keeps every decision."""
    if (
        body.status != "PROPOSED"
        and req.necessity_code == "MANDATORY"
        and body.status != "ACCEPTED"
        and not body.reason
    ):
        raise ApiError(422, "REASON_REQUIRED", "Say why a mandatory requirement is excluded or not applicable.",
                       errors=[field_error("reason", "REQUIRED", "A reason is required.")])  # fmt: skip
    if body.status == "PROPOSED" and req.source_code not in ("SURVEY_TEMPLATE", "MEASUREMENT_RULE"):
        raise ApiError(422, "INVALID_TRANSITION", "Only a recommendation can go back to proposed.")
    req.status = body.status
    if body.status == "PROPOSED":
        req.decided_by = req.decided_on = req.decision_reason = None
    else:
        req.decided_by, req.decided_on, req.decision_reason = ctx.user.id, db.tx_time(s), body.reason
    return req


def update(s: Session, ctx, req: Requirement, body) -> Requirement:
    data = body.model_dump(exclude_unset=True)
    if "preferences" in data:
        req.preferences = body.preferences.model_dump(exclude_none=True) if body.preferences else {}
    if "notes" in data:
        req.notes = body.notes
    if "necessity_code" in data and req.source_code in ("SURVEY_TEMPLATE", "MEASUREMENT_RULE"):
        raise ApiError(422, "VALIDATION_FAILED", "A recommendation's necessity comes from its rule.",
                       errors=[field_error("necessity_code", "IMMUTABLE_FIELD", "Set by the rule.")])  # fmt: skip
    if "necessity_code" in data:
        req.necessity_code = body.necessity_code
    if "custom_label" in data and req.requirement_type_code == "CUSTOM":
        req.custom_label = body.custom_label
    return req


def classification(req: Requirement) -> str:
    """The six-way reading of a requirement (instruction B2.1): a decision first, then the source, then the strength."""
    if req.status in ("EXCLUDED", "NOT_APPLICABLE"):
        return req.status
    if req.source_code == "CUSTOMER_REQUEST":
        return "CUSTOMER_REQUESTED"
    return req.necessity_code


def present(req: Requirement, spaces: dict[str, PropertySpace] | None = None) -> dict[str, Any]:
    sp = (spaces or {}).get(req.space_id) if req.space_id else None
    itype = rules.item_type(req.requirement_type_code)
    return {
        "id": req.id,
        "version": req.version,
        "property_id": req.property_id,
        "space_id": req.space_id,
        "space_label": sp.label if sp else None,
        "requirement_type_code": req.requirement_type_code,
        "label": req.custom_label or itype.label,
        "custom_label": req.custom_label,
        "necessity_code": req.necessity_code,
        "status": req.status,
        "classification": classification(req),
        "source_code": req.source_code,
        "origin_code": ORIGIN_OF_SOURCE[req.source_code],
        "source_ref": req.source_ref,
        "anchor_wall_index": req.anchor_wall_index,
        "instance_no": req.instance_no,
        "preferences": req.preferences or {},
        "notes": req.notes,
        "catalogue_mapped": itype.card_product is not None,
        "decided_by": req.decided_by,
        "decided_on": clock.to_rfc3339(req.decided_on) if req.decided_on else None,
        "decision_reason": req.decision_reason,
    }


def for_property(s: Session, prop: Property) -> list[Requirement]:
    return list(
        s.execute(
            sa.select(Requirement)
            .where(Requirement.property_id == prop.id)
            .order_by(
                Requirement.space_id.is_(None),
                Requirement.space_id,
                Requirement.requirement_type_code,
                Requirement.dedupe_key,
            )  # fmt: skip
        ).scalars()
    )


def spaces_of(s: Session, prop: Property) -> dict[str, PropertySpace]:
    return {
        sp.id: sp
        for sp in s.execute(
            sa.select(PropertySpace).where(PropertySpace.property_id == prop.id).execution_options(include_deleted=True)
        ).scalars()
    }


def get(s: Session, req_id: str) -> Requirement:
    req = s.get(Requirement, req_id)
    if req is None or req.is_deleted:
        raise not_found()
    return req
