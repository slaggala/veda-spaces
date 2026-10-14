"""BOQ revisions (blueprint §8.2, §8.3; instruction B2.4-B2.6).

A BOQ is generated from a CONFIRMED scope and the rate card's product structure (which lines a product has under its
options, and each line's quantity basis), never its rates. Every included or optional scope item becomes one line per
applicable card line; an item the card has no product for becomes an UNMAPPED line (or a MEASURED_COUNT line when the
quantity is a count of captured points), kept and reported, never dropped.

Validation is part of the BOQ: each line carries the issue codes found when it was generated, and the BOQ the
property-level ones. BLOCKING issues stop the review; WARNINGS are disclosed. A quantity override keeps the calculated
value, and needs a reason; it clears the line's missing-measurement and impossible-quantity issues because the line
then states its quantity explicitly. No line is dropped for a zero or missing quantity; each carries a quantity status
(VALID, VALID_ZERO, UNRESOLVED, INVALID). An included item with no catalogue line, a wrong-kind or fractional count
input, unresolved source points or a missing final quantity block the review. Review seals the BOQ (canonical JSON
digest) and supersedes the property's previously reviewed BOQ; regeneration creates a new revision and supersedes the
open one, carrying an override only where the calculated quantity is unchanged.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, db
from veda.kernel.errors import ApiError, field_error
from veda.kernel.jcs import canonical_bytes
from veda.modules.estimator import service as estimator_service
from veda.modules.estimator.models import EstimatorRateCard
from veda.modules.estimator.ratecard import RateCard
from veda.modules.mtq.models import MeasurementSet, Property

from . import lineage, quantity, requirements, rules, scopes, site
from . import vocab as V
from .models import Boq, BoqLine, Requirement, Scope, ScopeItem

BLOCKING = frozenset({
    "MISSING_MEASUREMENT", "IMPOSSIBLE_QUANTITY", "MISSING_QUANTITY_RULE", "UNSUPPORTED_UNIT", "INVALID_OPTION",
    "STALE_MEASUREMENT", "UNVERIFIED_MEASUREMENT", "LITE_SURVEY_NOT_QUOTATION_READY", "UNEXPLAINED_OVERRIDE",
    "QUANTITY_KIND_MISMATCH", "INVALID_COUNT", "UNRESOLVED_SOURCE_POINTS", "MANDATORY_SCOPE_MISMATCH",
    "MISSING_QUANTITY", "UNRESOLVED_CATALOGUE_MAPPING",
})  # fmt: skip
CLEARED_BY_OVERRIDE = frozenset({"MISSING_MEASUREMENT", "IMPOSSIBLE_QUANTITY"})
# How a line's quantity stands (instruction: a line never disappears because its quantity is zero or missing).
# Excluded and not-applicable requirements are not BOQ lines: they are recorded on the scope (exclusions) and listed
# in the BOQ summary (excluded_items, requirement_exclusions).
INVALID_CODES = frozenset({"QUANTITY_KIND_MISMATCH", "INVALID_COUNT", "IMPOSSIBLE_QUANTITY", "UNSUPPORTED_UNIT"})
UNIT_TEXT = {"SFT": "sq ft", "RFT": "rft", "NOS": "nos", "LUMP": "lump"}

MESSAGES = {
    "MISSING_MEASUREMENT": "{what}: {detail} Capture it in a new measurement revision, enter it on the scope item with a "
    "reason, or override the line quantity with a reason.",
    "IMPOSSIBLE_QUANTITY": "{what}: {detail} Check the measurement (unit mistake?) or override the quantity with a reason.",
    "MISSING_QUANTITY_RULE": "{what}: the ruleset gives no derivation for card input {detail}. Enter it on the scope item "
    "or override the line quantity.",
    "UNSUPPORTED_UNIT": "{what}: the card line's unit {detail} is not a BOQ unit.",
    "INVALID_OPTION": "{what}: {detail} Choose one of the card's choices on the scope item.",
    "MISSING_CATALOGUE_MAPPING": "{what}: {detail} It stays in the BOQ unpriced; pricing it needs a rate-card line "
    "(owner decision OI-MTQ-05).",
    "ASSUMED_DIMENSION": "{what}: uses an assumed value ({detail}); it is listed as an assumption.",
    "DUPLICATE_SCOPE": "{what}: another included item in the same space maps to the same catalogue product and wall.",
    "STALE_MEASUREMENT": "A newer verified measurement set exists; regenerate the scope and BOQ.",
    "UNVERIFIED_MEASUREMENT": "The measurement set is not verified.",
    "LITE_SURVEY_NOT_QUOTATION_READY": "The measurements are a Lite survey; only a Full survey is quotation-ready "
    "(B1-02).",
    "RULESET_NOT_APPROVED": "The scope ruleset {detail} is not approved (OI-MTQ-03, OI-MTQ-04); quantities are "
    "reviewable but not customer-issuable.",
    "QUANTITY_KIND_MISMATCH": "{what}: {detail} The ruleset's derivation and the rate card's input disagree on the "
    "kind of quantity; no conversion is approved, so the line cannot be quantified.",
    "INVALID_COUNT": "{what}: {detail} Counts are whole numbers (as in the estimator); correct the entry on the scope "
    "item.",
    "UNRESOLVED_SOURCE_POINTS": "{what}: {detail} Complete the points in a new measurement revision.",
    "MANDATORY_SCOPE_MISMATCH": "{what}: a mandatory requirement is quoted as optional; include it, or exclude it "
    "with a note.",
    "MISSING_QUANTITY": "{what}: the line has no final quantity.",
    "UNRESOLVED_CATALOGUE_MAPPING": "{what}: {detail} An included item with no catalogue line cannot be reviewed for "
    "pricing; exclude it, offer it as optional, or wait for its rate-card line (owner decision OI-MTQ-05).",
}


def issue(code: str, *, what: str = "", detail: str = "", **refs) -> dict[str, Any]:
    return {"code": code, "severity": "BLOCKING" if code in BLOCKING else "WARNING",
            "message": MESSAGES[code].format(what=what, detail=detail), **refs}  # fmt: skip


def _unmapped(item: ScopeItem, what: str, detail: str) -> dict[str, Any]:
    """An item with no catalogue line: blocking when it is in the committed scope, disclosed when it is optional."""
    code = "MISSING_CATALOGUE_MAPPING" if item.inclusion_code == "OPTIONAL" else "UNRESOLVED_CATALOGUE_MAPPING"
    return issue(code, what=what, detail=detail)


def require_status(boq: Boq, status: str) -> None:
    if boq.status != status:
        raise ApiError(409, "BOQ_FROZEN" if boq.status != "GENERATED" else "INVALID_STATE",
                       f"BOQ revision {boq.revision_no} is {boq.status.lower()}.", extra={"status": boq.status})  # fmt: skip


def active_catalogue(s: Session) -> tuple[EstimatorRateCard, RateCard]:
    try:
        return estimator_service.active_card(s)
    except ApiError as err:
        raise ApiError(409, "CATALOGUE_UNAVAILABLE", "No active rate card: the BOQ needs its product lines.") from err


def _next_revision(s: Session, property_id: str) -> int:
    top = s.execute(
        sa.select(sa.func.max(Boq.revision_no))
        .where(Boq.property_id == property_id)
        .execution_options(include_deleted=True)
    ).scalar()
    return int(top or 0) + 1


def _what(item: ScopeItem, spaces: dict) -> str:
    sp = spaces.get(item.space_id) if item.space_id else None
    return f"{item.label} ({sp.label if sp else 'project'})"


def _lines_for(card: RateCard, item: ScopeItem, req: Requirement, facts: site.Facts, what: str) -> list[dict[str, Any]]:
    """The BOQ lines of one scope item (dicts of BoqLine columns plus generation issues)."""
    itype = rules.item_type(item.item_type_code)
    dims = (item.dimensions or {}).get("inputs") or {}
    overrides = item.dimension_overrides or {}
    base = {"scope_item_id": item.id, "requirement_id": item.requirement_id, "space_id": item.space_id,
            "item_type_code": item.item_type_code, "is_optional": item.inclusion_code == "OPTIONAL"}  # fmt: skip
    source_ref = {**facts.ref(item.space_id), "anchor_wall_index": item.anchor_wall_index}
    if item.card_product_code is None:
        if itype.measured_count is not None:
            n, why, unresolved = quantity.counted(facts, itype.measured_count)
            issues = [_unmapped(item, what, itype.unmapped_reason or "")]
            if unresolved:
                issues.append(issue("UNRESOLVED_SOURCE_POINTS", what=what,
                                    detail=f"{unresolved} captured point(s) lack the sensor type or switching the "
                                           "count needs."))  # fmt: skip
            return [{**base, "card_product_code": None, "card_line_code": None, "label": item.label, "uom_code": "NOS",
                     "formula_kind": "MEASURED_COUNT", "formula_inputs": {"count": n, "unresolved": unresolved},
                     "derivation": f"{why} = {n} nos", "measurement_source": facts.ref(None),
                     "calculated_quantity_centi": n * 100, "dimension_source_code": "MEASURED", "issues": issues}]  # fmt: skip
        return [{**base, "card_product_code": None, "card_line_code": None, "label": item.label, "uom_code": None,
                 "formula_kind": "UNMAPPED", "formula_inputs": {}, "derivation": "No catalogue line: not quantified.",
                 "measurement_source": source_ref, "calculated_quantity_centi": None,
                 "dimension_source_code": item.dimension_source_code,
                 "issues": [_unmapped(item, what, itype.unmapped_reason or "")]}]  # fmt: skip
    product = card.product(item.card_product_code)
    if product is None:
        return [{**base, "card_product_code": item.card_product_code, "card_line_code": None, "label": item.label,
                 "uom_code": None, "formula_kind": "UNMAPPED", "formula_inputs": {},
                 "derivation": f"Rate card {card.version} has no product {item.card_product_code}.",
                 "measurement_source": source_ref, "calculated_quantity_centi": None,
                 "dimension_source_code": item.dimension_source_code,
                 "issues": [_unmapped(item, what, f"rate card {card.version} has no product {item.card_product_code}.")]}]  # fmt: skip
    options = {o.name: o.default for o in product.options}
    chosen = scopes.effective_options(item, req)
    bad = []
    for name, choice in chosen.items():
        spec = next((o for o in product.options if o.name == name), None)
        if spec is None or choice not in spec.choices:
            bad.append(f"{name}={choice}")
        else:
            options[name] = choice
    item_issues = (
        [issue("INVALID_OPTION", what=what, detail=f"Unknown option or choice: {', '.join(bad)}.")] if bad else []
    )
    if item.necessity_code == "MANDATORY" and item.inclusion_code == "OPTIONAL":
        item_issues.append(issue("MANDATORY_SCOPE_MISMATCH", what=what))
    out = []
    for line in product.lines:
        if any(options.get(w.option) not in w.is_ for w in line.when):
            continue
        ldims, lover = quantity.for_line(itype, line.code, dims, overrides)  # this line's quantity roles
        lq = quantity.line_quantity(card, product, line, ldims, lover)
        issues = list(item_issues)
        if line.uom not in V.UOMS:
            issues.append(issue("UNSUPPORTED_UNIT", what=what, detail=line.uom))
        no_rule = [n for n in lq.missing + lq.kind_mismatch if n not in itype.inputs and n not in lover]
        kinds = {i.name: i.kind for i in product.inputs}
        mismatch = [f"{n} is derived as a {(ldims.get(n) or {}).get('kind')} but card {card.version} takes a {kinds[n]}."
                    for n in lq.kind_mismatch if n not in no_rule]  # fmt: skip
        if mismatch:
            issues.append(issue("QUANTITY_KIND_MISMATCH", what=what, detail=" ".join(mismatch)))
        if lq.not_whole:
            issues.append(issue("INVALID_COUNT", what=what, detail="; ".join(lq.not_whole) + "."))
        if no_rule:
            issues.append(issue("MISSING_QUANTITY_RULE", what=what, detail=", ".join(no_rule)))
        elif lq.missing:
            why = "; ".join(f"{(ldims.get(n) or {}).get('role', n)}: {(ldims.get(n) or {}).get('explain', 'not entered')}"
                            for n in lq.missing)  # fmt: skip
            issues.append(issue("MISSING_MEASUREMENT", what=what, detail=why))
        if lq.out_of_bounds:
            issues.append(issue("IMPOSSIBLE_QUANTITY", what=what, detail="; ".join(lq.out_of_bounds) + "."))
        if lq.source == "ASSUMED":
            used = [n for n in (line.quantity.input, line.quantity.height_input) if n]
            assumed = [
                f"{(ldims.get(n) or {}).get('role', n)} {(ldims.get(n) or {}).get('explain')}"
                for n in used
                if (ldims.get(n) or {}).get("source") == "ASSUMED" and n not in lover
            ]
            issues.append(issue("ASSUMED_DIMENSION", what=what, detail="; ".join(assumed)))
        # A zero quantity is kept and classified (quantity_status), never dropped: a zero count is a valid zero, a zero
        # length or area is out of the card's bounds (IMPOSSIBLE_QUANTITY above). The estimator skips zero lines; the
        # BOQ keeps them for the audit trail (documented difference, MTQ/estimator parity test).
        label = f"{product.label} — {line.label}"[:300]
        out.append({**base, "card_product_code": product.code, "card_line_code": line.code, "label": label,
                    "uom_code": line.uom if line.uom in V.UOMS else None, "formula_kind": lq.formula_kind,
                    "formula_inputs": {"inputs": lq.inputs, "options": options,
                                       "quantity_basis": _basis(line),
                                       # the exact quantity before the one rounding (decimal string, no float)
                                       "raw_quantity": format(lq.raw.normalize(), "f") if lq.raw is not None else None},
                    "derivation": lq.derivation or "Not quantified: " + "; ".join(i["code"] for i in issues),
                    "measurement_source": source_ref,
                    "calculated_quantity_centi": quantity.to_centi(lq.quantity) if lq.quantity is not None else None,
                    "dimension_source_code": "ASSUMED" if lq.source in ("ASSUMED", "MISSING") else lq.source,
                    "issues": issues})  # fmt: skip
    return out


def _basis(line) -> dict[str, Any]:
    """The card line's quantity spec, numbers as decimal strings (no floats in sealed JSON)."""
    return {k: (format(Decimal(str(v)), "f") if isinstance(v, float) else v)
            for k, v in line.quantity.model_dump(exclude_none=True).items()}  # fmt: skip


def effective_issues(line: BoqLine) -> list[dict[str, Any]]:
    out = []
    for i in line.issue_codes or []:
        if line.override_quantity_centi is not None and i["code"] in CLEARED_BY_OVERRIDE:
            continue
        out.append(i)
    return out


def _status(line: BoqLine) -> str:
    line.quantity_status = quantity_status(line)
    return "ISSUE" if any(i["severity"] == "BLOCKING" for i in line_blockers(line)) else "OK"


def quantity_status(line: BoqLine) -> str:
    """VALID, VALID_ZERO (a measured or entered zero the card admits), UNRESOLVED (no catalogue line, a missing input,
    unresolved source points) or INVALID (an impossible, fractional or wrong-kind quantity)."""
    codes = {i["code"] for i in effective_issues(line)}
    if codes & INVALID_CODES:
        return "INVALID"
    if line.formula_kind == "UNMAPPED" or line.final_quantity_centi is None or "UNRESOLVED_SOURCE_POINTS" in codes:
        return "UNRESOLVED"
    return "VALID_ZERO" if line.final_quantity_centi == 0 else "VALID"


def line_blockers(line: BoqLine) -> list[dict[str, Any]]:
    """Every blocking issue of a line, including a missing final quantity on a line the card quantifies."""
    out = [i for i in effective_issues(line) if i["severity"] == "BLOCKING"]
    if line.final_quantity_centi is None and line.formula_kind != "UNMAPPED" and not out:
        out.append(issue("MISSING_QUANTITY", what=line.label))
    return out


def generate(s: Session, ctx, scope: Scope, prop: Property) -> Boq:
    if scope.status != "CONFIRMED":
        raise ApiError(409, "SCOPE_NOT_CONFIRMED", "A BOQ is generated from a confirmed scope revision.",
                       extra={"status": scope.status})  # fmt: skip
    mset = s.get(MeasurementSet, scope.measurement_set_id)
    assert mset is not None
    if scope.property_id != prop.id or mset.property_id != prop.id:
        raise ApiError(422, "LINEAGE_MISMATCH", "The scope's lineage does not belong to this property.")
    reasons = lineage.scope_reasons(s, scope)
    if reasons:
        raise ApiError(409, "SCOPE_STALE", "The scope is out of date; create and confirm a new scope revision first.",
                       extra={"reasons": reasons})  # fmt: skip
    card_row, card = active_catalogue(s)
    previous = s.execute(
        sa.select(Boq).where(Boq.property_id == prop.id, Boq.status == "GENERATED")
    ).scalar_one_or_none()
    carried: dict[tuple, BoqLine] = {}
    if previous is not None:
        for old in lines(s, previous):
            if old.override_quantity_centi is not None:
                carried[(old.requirement_id, old.card_product_code, old.card_line_code)] = old
        previous.status = "SUPERSEDED"
        s.flush()  # one GENERATED per property
    boq = Boq(
        lead_id=prop.lead_id,
        property_id=prop.id,
        scope_id=scope.id,
        scope_revision_no=scope.revision_no,
        scope_snapshot_sha256=scope.snapshot_sha256,
        measurement_set_id=mset.id,
        measurement_revision_no=mset.revision_no,
        revision_no=_next_revision(s, prop.id),
        supersedes_boq_id=previous.id if previous else None,
        status="GENERATED",
        quantity_engine_version=quantity.QUANTITY_ENGINE_VERSION,
        ruleset_version=scope.ruleset_version,
        catalogue_card_id=card_row.id,
        catalogue_card_version=card_row.card_version,
        catalogue_card_sha256=card_row.document_sha256,
        rounding_policy=quantity.ROUNDING_POLICY,
    )
    s.add(boq)
    s.flush()
    facts = site.load(s, prop, mset)
    spaces = requirements.spaces_of(s, prop)
    items = scopes.items(s, scope)
    reqs = {r.id: r for r in s.execute(sa.select(Requirement).where(Requirement.property_id == prop.id)).scalars()}
    dup = _duplicates(items)
    position = 0
    for item in items:
        if item.inclusion_code == "EXCLUDED":
            continue
        what = _what(item, spaces)
        for data in _lines_for(card, item, reqs[item.requirement_id], facts, what):
            position += 1
            issues = data.pop("issues")
            if item.id in dup:
                issues.append(issue("DUPLICATE_SCOPE", what=what))
            line = BoqLine(boq_id=boq.id, position=position, issue_codes=issues, **data)
            kept = carried.get((line.requirement_id, line.card_product_code, line.card_line_code))
            if kept is not None and kept.calculated_quantity_centi == line.calculated_quantity_centi:
                line.override_quantity_centi, line.override_reason = kept.override_quantity_centi, kept.override_reason
                line.override_by, line.override_on = kept.override_by, kept.override_on
            line.final_quantity_centi = (
                line.override_quantity_centi
                if line.override_quantity_centi is not None
                else line.calculated_quantity_centi
            )
            line.status = _status(line)
            s.add(line)
    s.flush()
    recompute(s, boq)
    return boq


def _duplicates(items: list[ScopeItem]) -> set[str]:
    seen: dict[tuple, list[str]] = {}
    for i in items:
        if i.inclusion_code == "EXCLUDED" or i.card_product_code is None:
            continue
        seen.setdefault((i.space_id, i.card_product_code, i.anchor_wall_index, i.item_type_code), []).append(i.id)
    return {iid for ids in seen.values() if len(ids) > 1 for iid in ids}


def recompute(s: Session, boq: Boq) -> None:
    """The BOQ-level issues and the room-wise / project summary (recomputable from the lines at any time)."""
    rows = lines(s, boq)
    scope = s.get(Scope, boq.scope_id)
    mset = s.get(MeasurementSet, boq.measurement_set_id)
    assert scope is not None and mset is not None
    prop = s.get(Property, boq.property_id)
    assert prop is not None
    spaces = requirements.spaces_of(s, prop)
    top: list[dict[str, Any]] = []
    for r in lineage.boq_reasons(s, boq):
        if r["code"] == "MEASUREMENT_REVISED":
            top.append(issue("STALE_MEASUREMENT"))
    if mset.status not in ("VERIFIED", "SUPERSEDED"):
        top.append(issue("UNVERIFIED_MEASUREMENT"))
    if mset.survey_level_code != "FULL":
        top.append(issue("LITE_SURVEY_NOT_QUOTATION_READY"))
    if scope.ruleset_status != rules.APPROVED_STATUS:
        top.append(issue("RULESET_NOT_APPROVED", detail=scope.ruleset_version))
    for line in rows:
        if line.override_quantity_centi is not None and not (line.override_reason or "").strip():
            top.append(issue("UNEXPLAINED_OVERRIDE", line_id=line.id))
    boq.issues = top
    rooms: OrderedDict[str | None, dict[str, Any]] = OrderedDict()
    project: OrderedDict[tuple, dict[str, Any]] = OrderedDict()
    by_uom: dict[str, int] = {}
    blocking = warning = 0
    assumptions = []
    for line in rows:
        eff = effective_issues(line)
        blocking += sum(1 for i in eff if i["severity"] == "BLOCKING")
        warning += sum(1 for i in eff if i["severity"] == "WARNING")
        sp = spaces.get(line.space_id) if line.space_id else None
        room = rooms.setdefault(line.space_id, {"space_id": line.space_id, "space_label": sp.label if sp else "Project",
                                                "lines": 0, "by_uom": {}, "optional_lines": 0})  # fmt: skip
        room["lines"] += 1
        room["optional_lines"] += int(line.is_optional)
        if line.final_quantity_centi is not None and line.uom_code:
            room["by_uom"][line.uom_code] = room["by_uom"].get(line.uom_code, 0) + line.final_quantity_centi
            by_uom[line.uom_code] = by_uom.get(line.uom_code, 0) + line.final_quantity_centi
            key = (line.card_product_code, line.card_line_code, line.uom_code, line.is_optional)
            p = project.setdefault(key, {"card_product_code": line.card_product_code,
                                         "card_line_code": line.card_line_code, "label": line.label,
                                         "uom_code": line.uom_code, "is_optional": line.is_optional,
                                         "quantity_centi": 0, "lines": 0})  # fmt: skip
            p["quantity_centi"] += line.final_quantity_centi
            p["lines"] += 1
        if line.dimension_source_code == "ASSUMED":
            assumptions.append({"line_id": line.id, "label": line.label, "space_label": sp.label if sp else None,
                                "derivation": line.derivation})  # fmt: skip
    blocking += sum(1 for i in top if i["severity"] == "BLOCKING")
    warning += sum(1 for i in top if i["severity"] == "WARNING")
    excluded = [{"scope_item_id": i.id, "label": i.label,
                 "space_label": spaces[i.space_id].label if i.space_id and i.space_id in spaces else None}
                for i in scopes.items(s, scope) if i.inclusion_code == "EXCLUDED"]  # fmt: skip
    boq.summary = {
        "rooms": list(rooms.values()),
        "project": list(project.values()),
        "totals_by_uom": by_uom,
        "line_count": len(rows),
        "overridden_lines": sum(1 for line in rows if line.override_quantity_centi is not None),
        "issue_counts": {"blocking": blocking, "warning": warning},
        "assumptions": assumptions,
        "excluded_items": excluded,
        "requirement_exclusions": scope.exclusions or [],
    }


def override(s: Session, ctx, line: BoqLine, boq: Boq, quantity_centi: int, reason: str) -> BoqLine:
    require_status(boq, "GENERATED")
    if line.uom_code is None:
        raise ApiError(422, "UNSUPPORTED_UNIT", "This line has no catalogue unit; it cannot be quantified here.")
    if line.formula_kind in ("CARD_COUNT", "MEASURED_COUNT") and quantity_centi % 100:
        raise ApiError(422, "VALIDATION_FAILED", "A count is a whole number.",
                       errors=[field_error("quantity", "NOT_WHOLE", "Must be a whole number.")])  # fmt: skip
    line.override_quantity_centi = quantity_centi
    line.override_reason = reason.strip()
    line.override_by, line.override_on = ctx.user.id, db.tx_time(s)
    line.final_quantity_centi = quantity_centi
    line.status = _status(line)
    s.flush()
    recompute(s, boq)
    return line


def clear_override(s: Session, ctx, line: BoqLine, boq: Boq) -> BoqLine:
    require_status(boq, "GENERATED")
    line.override_quantity_centi = line.override_reason = line.override_by = line.override_on = None
    line.final_quantity_centi = line.calculated_quantity_centi
    line.status = _status(line)
    s.flush()
    recompute(s, boq)
    return line


def review(s: Session, ctx, boq: Boq) -> Boq:
    require_status(boq, "GENERATED")
    recompute(s, boq)
    reasons = lineage.boq_reasons(s, boq)
    if reasons:
        raise ApiError(409, "BOQ_STALE", "The scope or measurements changed; regenerate the BOQ.",
                       extra={"reasons": reasons})  # fmt: skip
    blocking = [i for i in boq.issues if i["severity"] == "BLOCKING"]
    for line in lines(s, boq):
        line.status = _status(line)
        blocking += [{**i, "line_id": line.id} for i in line_blockers(line)]
    if blocking:
        raise ApiError(409, "BOQ_HAS_BLOCKING_ISSUES", f"{len(blocking)} blocking issue(s) must be resolved first.",
                       extra={"issues": blocking})  # fmt: skip
    previous = latest_reviewed(s, boq.property_id)
    if previous is not None:  # one reviewed BOQ per property: the earlier one is superseded (and reported stale)
        previous.status = "SUPERSEDED"
        s.flush()
    digest = snapshot_sha256(s, boq)  # computed first: the sealed-row CHECK needs it with the status
    boq.status, boq.reviewed_on, boq.reviewed_by = "REVIEWED", db.tx_time(s), ctx.user.id
    boq.snapshot_sha256 = digest
    return boq


LINE_FIELDS = ("id", "scope_item_id", "requirement_id", "space_id", "position", "item_type_code", "card_product_code",
               "card_line_code", "label", "uom_code", "formula_kind", "formula_inputs", "derivation",
               "measurement_source", "calculated_quantity_centi", "override_quantity_centi", "override_reason",
               "final_quantity_centi", "is_optional", "dimension_source_code", "quantity_status")  # fmt: skip


def snapshot_sha256(s: Session, boq: Boq) -> str:
    doc = {"boq_id": boq.id, "revision_no": boq.revision_no, "scope_id": boq.scope_id,
           "scope_snapshot_sha256": boq.scope_snapshot_sha256, "catalogue": boq.catalogue_card_sha256,
           "quantity_engine_version": boq.quantity_engine_version,
           "lines": [{k: getattr(line, k) for k in LINE_FIELDS} for line in lines(s, boq)]}  # fmt: skip
    return hashlib.sha256(canonical_bytes(doc)).hexdigest()


def lines(s: Session, boq: Boq) -> list[BoqLine]:
    return list(s.execute(sa.select(BoqLine).where(BoqLine.boq_id == boq.id).order_by(BoqLine.position)).scalars())


def latest_reviewed(s: Session, property_id: str) -> Boq | None:
    return s.execute(
        sa.select(Boq)
        .where(Boq.property_id == property_id, Boq.status == "REVIEWED")
        .order_by(Boq.revision_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def _key(line: BoqLine) -> tuple:
    return (line.requirement_id, line.card_product_code or line.item_type_code, line.card_line_code or "")


def diff(s: Session, a: Boq, b: Boq) -> dict[str, Any]:
    """Line deltas between two BOQ revisions of one property, keyed by requirement and catalogue line."""
    if a.property_id != b.property_id:
        raise ApiError(422, "VALIDATION_FAILED", "Both BOQ revisions must belong to the same property.")
    left, right = {_key(x): x for x in lines(s, a)}, {_key(x): x for x in lines(s, b)}
    out = []
    for key in list(OrderedDict.fromkeys([*left, *right])):
        la, rb = left.get(key), right.get(key)
        if la is None or rb is None:
            line = rb or la
            assert line is not None
            out.append({"change": "ADDED" if la is None else "REMOVED", "label": line.label,
                        "space_id": line.space_id, "uom_code": line.uom_code,
                        "from_quantity_centi": la.final_quantity_centi if la else None,
                        "to_quantity_centi": rb.final_quantity_centi if rb else None})  # fmt: skip
            continue
        if la.final_quantity_centi != rb.final_quantity_centi or la.derivation != rb.derivation:
            out.append({"change": "CHANGED", "label": rb.label, "space_id": rb.space_id, "uom_code": rb.uom_code,
                        "from_quantity_centi": la.final_quantity_centi, "to_quantity_centi": rb.final_quantity_centi,
                        "from_derivation": la.derivation, "to_derivation": rb.derivation,
                        "cause": "MEASUREMENT" if a.measurement_set_id != b.measurement_set_id else "SCOPE_OR_OVERRIDE"})  # fmt: skip
    return {"from_boq_id": a.id, "to_boq_id": b.id, "from_revision": a.revision_no, "to_revision": b.revision_no,
            "lines": out}  # fmt: skip


def present_line(line: BoqLine, spaces: dict) -> dict[str, Any]:
    sp = spaces.get(line.space_id) if line.space_id else None
    eff = effective_issues(line)
    return {
        **{k: getattr(line, k) for k in LINE_FIELDS},
        "version": line.version,
        "space_label": sp.label if sp else None,
        "unit_text": UNIT_TEXT.get(line.uom_code or "", ""),
        "override_by": line.override_by,
        "override_on": clock.to_rfc3339(line.override_on) if line.override_on else None,
        "status": line.status,
        "issues": eff,
        "quantity": str(Decimal(line.final_quantity_centi) / 100) if line.final_quantity_centi is not None else None,
    }


def present(s: Session, boq: Boq, *, full: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": boq.id,
        "version": boq.version,
        "property_id": boq.property_id,
        "lead_id": boq.lead_id,
        "revision_no": boq.revision_no,
        "status": boq.status,
        "scope_id": boq.scope_id,
        "scope_revision_no": boq.scope_revision_no,
        "scope_snapshot_sha256": boq.scope_snapshot_sha256,
        "measurement_set_id": boq.measurement_set_id,
        "measurement_revision_no": boq.measurement_revision_no,
        "supersedes_boq_id": boq.supersedes_boq_id,
        "quantity_engine_version": boq.quantity_engine_version,
        "ruleset_version": boq.ruleset_version,
        "catalogue_card_version": boq.catalogue_card_version,
        "catalogue_card_sha256": boq.catalogue_card_sha256,
        "rounding_policy": boq.rounding_policy,
        "summary": boq.summary or {},
        "issues": boq.issues or [],
        "reviewed_on": clock.to_rfc3339(boq.reviewed_on) if boq.reviewed_on else None,
        "reviewed_by": boq.reviewed_by,
        "snapshot_sha256": boq.snapshot_sha256,
        "created_on": clock.to_rfc3339(boq.created_on),
        "lineage": lineage.boq_state(s, boq),
    }
    if full:
        prop = s.get(Property, boq.property_id)
        assert prop is not None
        spaces = requirements.spaces_of(s, prop)
        out["lines"] = [present_line(line, spaces) for line in lines(s, boq)]
    return out
