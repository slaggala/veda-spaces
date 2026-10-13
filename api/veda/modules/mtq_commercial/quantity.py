"""The B2 quantity engine (blueprint §8.2), versioned and explainable. Pure: no database, no clock.

Two steps, both deterministic:

1. **Inputs from measurements.** Each scope item type names how every rate-card input of its product (WIDTH, HEIGHT,
   RUN, AREA, DRAWERS…) comes from the verified measurement set: a tagged wall's stretch clear of openings, the space's
   derived floor area, a count of captured electrical points, or a staff entry. Every value keeps its source
   (MEASURED, DERIVED, ASSUMED, STAFF), a sentence explaining it, and the measurement rows it was read from.
2. **Card quantity bases.** A BOQ line's quantity is the rate card's own approved quantity spec for that line (area =
   input × height input or constant; direct; count; lump; × factor), evaluated on those inputs. The engine prices
   nothing and invents no factor: the quantity bases are the card's, the derivations the ruleset's.

Lengths are kept in millimetres until the end; quantities are exact decimals rounded once, to 0.01 half up, which is
the estimator engine's own rounding (``engine._q``). No clearance, corner deduction or wastage is applied (OI-MTQ-04).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from veda.modules.estimator.ratecard import LineSpec, ProductSpec, RateCard
from veda.modules.mtq import derivation as site_derivation

from .rules import InputRule, ItemType
from .site import Facts

QUANTITY_ENGINE_VERSION = "2026.10.1"
MM_PER_FT = Decimal("304.8")
CENTI = Decimal("0.01")
ROUNDING_POLICY = {
    "quantity": "0.01 of the line unit, half up, once (estimator engine rounding, CALCULATION_VERSION 2026.10.2)",
    "intermediate": "exact decimals from integer millimetres; no intermediate rounding",
    "wastage": "none (OI-MTQ-04 not decided)",
    "clearances": "none (OI-MTQ-04 not decided)",
}
SOURCE_RANK = {"MEASURED": 0, "DERIVED": 1, "STAFF": 2, "ASSUMED": 3, "MISSING": 4}
CARD_KIND_UNIT = {"length": "ft", "area": "sq ft", "count": "nos"}
FORMULA_OF = {"area": "CARD_AREA", "direct": "CARD_DIRECT", "count": "CARD_COUNT", "lump": "CARD_LUMP"}


def q(value: Decimal) -> Decimal:
    return value.quantize(CENTI, rounding=ROUND_HALF_UP)


def to_centi(value: Decimal) -> int:
    return int(q(value) * 100)


def ft(mm: int) -> Decimal:
    return Decimal(mm) / MM_PER_FT


def num(value: float | Decimal) -> str:
    """A card constant as written (2, 2.5, 0.025): no float noise, no trailing zeros."""
    d = Decimal(str(value)).normalize()
    return format(d, "f")


def show(value: Decimal, places: str = "0.01") -> str:
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


# --- step 1: inputs ---------------------------------------------------------------------------------------------------
def _length(mm: int, source: str, explain: str, refs: dict) -> dict[str, Any]:
    return {"kind": "length", "unit": "ft", "mm": int(mm), "value": show(ft(mm)), "source": source, "explain": explain,
            "refs": refs}  # fmt: skip


def _area(centi: int, source: str, explain: str, refs: dict) -> dict[str, Any]:
    return {"kind": "area", "unit": "sq ft", "centi": int(centi), "value": show(Decimal(centi) / 100), "source": source,
            "explain": explain, "refs": refs}  # fmt: skip


def _count(n: int, source: str, explain: str, refs: dict) -> dict[str, Any]:
    return {"kind": "count", "unit": "nos", "count": int(n), "value": str(n), "source": source, "explain": explain,
            "refs": refs}  # fmt: skip


def _missing(explain: str, refs: dict | None = None) -> dict[str, Any]:
    return {"kind": None, "value": None, "source": "MISSING", "explain": explain, "refs": refs or {}}


def _anchor_wall(facts: Facts, space_id: str | None, tag: str | None, anchor: int | None) -> dict[str, Any] | None:
    walls = facts.walls(space_id)
    if anchor is not None:
        return next((w for w in walls if w["wall_index"] == anchor), None)
    if tag is None:
        return None
    return next((w for w in walls if tag in (w.get("usable_for_code") or [])), None)


def _clear_stretch(w: dict[str, Any]) -> tuple[int, str, str]:
    """Longest stretch of a wall clear of openings, with its source and a sentence."""
    segs = site_derivation.usable_segments(w)
    label = f"W{w['wall_index']}"
    if not w.get("openings"):
        return int(w["length_mm"]), "MEASURED", f"{label} length {w['length_mm']} mm"
    if not segs:
        return (int(w["length_mm"]), "ASSUMED",
                f"{label} length {w['length_mm']} mm (an opening has no offset, so the clear stretch is unknown)")  # fmt: skip
    longest = max(b - a for a, b in segs)
    return longest, "DERIVED", f"{label}: longest stretch clear of openings {longest} mm of {w['length_mm']} mm"


def _sum_points(facts: Facts, types: tuple[str, ...] | None, statuses: tuple[str, ...]) -> tuple[int, list[str]]:
    n, spaces = 0, []
    for sid in facts.spaces:
        m = facts.m(sid) or {}
        here = sum(int(p["quantity"]) for p in m.get("electrical_points") or []
                   if (types is None or p["point_type_code"] in types) and (not statuses or p["status_code"] in statuses))  # fmt: skip
        if here:
            n += here
            spaces.append(facts.spaces[sid].label)
    return n, spaces


def derive_input(rule: InputRule, facts: Facts, space_id: str | None, anchor: int | None) -> dict[str, Any]:
    m = facts.m(space_id) if space_id else None
    k = rule.kind
    if space_id and m is None and k not in ("staff",):
        return _missing("The space has no measurement in the verified set.")
    if k == "wall_run":
        w = _anchor_wall(facts, space_id, rule.tag, anchor)
        if w is None:
            what = f"wall W{anchor}" if anchor is not None else f"a wall tagged {rule.tag}"
            return _missing(f"The verified set has no {what} in this space.")
        mm, source, why = _clear_stretch(w)
        return _length(mm, source, why, facts.ref(space_id, wall_id=w["id"], wall_index=w["wall_index"]))
    if k == "tagged_run_total":
        tagged = [w for w in facts.walls(space_id) if rule.tag in (w.get("usable_for_code") or [])]
        if not tagged:
            return _missing(f"No wall in this space is tagged {rule.tag}.")
        parts, total, source = [], 0, "MEASURED"
        for w in tagged:
            mm, src, _ = _clear_stretch(w)
            segs = site_derivation.usable_segments(w) if w.get("openings") else [[0, int(w["length_mm"])]]
            run = sum(b - a for a, b in segs) if segs else mm
            total += run
            parts.append(f"W{w['wall_index']} {run} mm")
            if SOURCE_RANK[src] > SOURCE_RANK[source]:
                source = src
        why = f"Σ stretches clear of openings on walls tagged {rule.tag}: " + " + ".join(parts) + f" = {total} mm"
        return _length(total, source, why, facts.ref(space_id, wall_ids=[w["id"] for w in tagged]))
    if k == "lintel_capped":
        cap = int(rule.cap_mm or 0)
        fl = (m or {}).get("floor_to_lintel_mm")
        if fl:
            return _length(min(int(fl), cap), "DERIVED", f"min(floor to lintel {fl} mm, {cap} mm)", facts.ref(space_id))
        return _length(cap, "ASSUMED", f"floor to lintel not captured: {cap} mm assumed (ADR-012 typical height)",
                       facts.ref(space_id))  # fmt: skip
    if k == "wall_height":
        w = _anchor_wall(facts, space_id, rule.tag, anchor)
        if w is None:
            return _missing(f"The verified set has no wall tagged {rule.tag} in this space.")
        h = w.get("height_mm") or (m or {}).get("ceiling_height_mm")
        if not h:
            return _missing(f"W{w['wall_index']} has no height and the space no ceiling height.")
        why = f"W{w['wall_index']} height {h} mm" if w.get("height_mm") else f"ceiling height {h} mm"
        return _length(int(h), "MEASURED", why, facts.ref(space_id, wall_id=w["id"], wall_index=w["wall_index"]))
    if k == "floor_area":
        centi = (m or {}).get("derived_floor_area_sqft_centi")
        if centi is None:
            return _missing("The space has no derived floor area.")
        source = "ASSUMED" if (m or {}).get("shape_code") == "FREEFORM" else "DERIVED"
        return _area(centi, source, f"floor area {Decimal(centi) / 100} sq ft ({(m or {}).get('shape_code', '').lower()})",
                     facts.ref(space_id))  # fmt: skip
    if k == "perimeter":
        perimeter = (m or {}).get("derived_perimeter_mm")
        if not perimeter:
            return _missing("The space has no derived perimeter.")
        return _length(int(perimeter), "DERIVED", f"perimeter {perimeter} mm (Σ wall lengths)", facts.ref(space_id))
    if k == "door_width":
        for w in facts.walls(space_id):
            for o in w.get("openings") or []:
                if o["opening_type_code"] == "DOOR":
                    return _length(int(o["width_mm"]), "MEASURED", f"door on W{w['wall_index']} {o['width_mm']} mm wide",
                                   facts.ref(space_id, wall_id=w["id"], opening_id=o["id"]))  # fmt: skip
        return _missing("No door was captured on this space's walls.")
    if k in ("partition_length", "partition_height"):
        proposed = [w for w in (m or {}).get("walls") or [] if w.get("is_proposed")]
        if not proposed:
            return _missing("No proposed partition was captured in this space.")
        if k == "partition_length":
            total = sum(int(w["length_mm"]) for w in proposed)
            return _length(total, "MEASURED", f"Σ proposed partitions {total} mm",
                           facts.ref(space_id, wall_ids=[w["id"] for w in proposed]))  # fmt: skip
        h = proposed[0].get("height_mm") or (m or {}).get("ceiling_height_mm")
        if not h:
            return _missing("The proposed partition has no height and the space no ceiling height.")
        return _length(int(h), "MEASURED", f"partition height {h} mm", facts.ref(space_id, wall_id=proposed[0]["id"]))
    if k in ("property_floor_area", "property_net_wall_area"):
        col = "derived_floor_area_sqft_centi" if k == "property_floor_area" else "derived_wall_area_net_sqft_centi"
        total, counted = 0, 0
        for sid, sp in facts.spaces.items():
            if rule.zones and sp.zone_code not in rule.zones:
                continue
            v = (facts.m(sid) or {}).get(col)
            if v:
                total += int(v)
                counted += 1
        if not counted:
            return _missing("No in-scope space in these zones has this derived area.")
        what = "floor area" if k == "property_floor_area" else "net wall area (openings deducted)"
        return _area(total, "DERIVED", f"Σ {what} of {counted} {'/'.join(z.lower() for z in rule.zones)} spaces",
                     facts.ref(None))  # fmt: skip
    if k == "electrical_count":
        n, where = _sum_points(facts, rule.types, rule.statuses)
        statuses = "/".join(st.lower() for st in rule.statuses)
        return _count(n, "MEASURED", f"{n} captured {statuses} points" + (f" ({', '.join(where)})" if where else ""),
                      facts.ref(None))  # fmt: skip
    return _missing(rule.explain or "Entered by staff on the scope item (no measurement derivation).")


def derive_inputs(itype: ItemType, facts: Facts, space_id: str | None, anchor: int | None) -> dict[str, dict]:
    return {name: derive_input(rule, facts, space_id, anchor) for name, rule in itype.inputs.items()}


def options_from_rules(itype: ItemType, facts: Facts, space_id: str | None) -> dict[str, dict[str, str]]:
    """Option values the ruleset sets from measured facts, each with its reason."""
    out: dict[str, dict[str, str]] = {}
    m = facts.m(space_id) or {}
    for name, r in itype.option_rules.items():
        ch = m.get("ceiling_height_mm")
        if not ch:
            continue
        clearance = int(ch) - r.above_mm
        choice = r.then if clearance >= r.at_least_mm else r.else_
        out[name] = {"value": choice,
                     "explain": f"ceiling {ch} mm − {r.above_mm} mm = {clearance} mm "
                                f"({'≥' if clearance >= r.at_least_mm else '<'} {r.at_least_mm} mm)"}  # fmt: skip
    return out


def worst_source(dims: dict[str, dict], overrides: dict[str, Any]) -> str:
    worst = "MEASURED"
    for name, d in dims.items():
        src = "STAFF" if name in overrides else d.get("source", "MISSING")
        if SOURCE_RANK.get(src, 4) > SOURCE_RANK[worst]:
            worst = src
    return "ASSUMED" if worst == "MISSING" else worst


# --- step 2: card quantity bases ----------------------------------------------------------------------------------------
@dataclass
class LineQuantity:
    quantity: Decimal | None
    formula_kind: str
    inputs: dict[str, Any] = field(default_factory=dict)
    derivation: str = ""
    missing: list[str] = field(default_factory=list)
    out_of_bounds: list[str] = field(default_factory=list)
    kind_mismatch: list[str] = field(default_factory=list)
    source: str = "MEASURED"


def exact_input(d: dict[str, Any] | None, override: Any, card_kind: str) -> Decimal | None:
    if override is not None:
        return Decimal(str(override))
    if d is None or d.get("value") is None:
        return None
    if d.get("kind") == "length" and d.get("mm") is not None:
        return ft(int(d["mm"]))
    if d.get("kind") == "area" and d.get("centi") is not None:
        return Decimal(int(d["centi"])) / 100
    if d.get("kind") == "count" and d.get("count") is not None:
        return Decimal(int(d["count"]))
    return Decimal(str(d["value"]))


def _input_text(name: str, value: Decimal, d: dict[str, Any] | None, overridden: bool, unit: str) -> str:
    if overridden:
        return f"{name.lower()} {show(value)} {unit} (staff entry)"
    explain = (d or {}).get("explain")
    return f"{name.lower()} {show(value)} {unit}" + (f" ({explain})" if explain else "")


def line_quantity(card: RateCard, product: ProductSpec, line: LineSpec, dims: dict[str, dict],
                  overrides: dict[str, Any]) -> LineQuantity:  # fmt: skip
    """Evaluate the card's quantity spec of ``line`` on the item's inputs (exact), then round once."""
    spec = line.quantity
    kinds = {i.name: i.kind for i in product.inputs}
    result = LineQuantity(quantity=None, formula_kind=FORMULA_OF[spec.kind])
    values: dict[str, Decimal] = {}
    parts: list[str] = []
    for name in (spec.input, spec.height_input):
        if not name:
            continue
        d = dims.get(name)
        if d is None and name not in overrides:
            result.missing.append(name)
            continue
        if d is not None and name not in overrides and d.get("kind") not in (None, kinds[name]):
            result.kind_mismatch.append(name)
            continue
        v = exact_input(d, overrides.get(name), kinds[name])
        if v is None:
            result.missing.append(name)
            continue
        bound = card.bounds[kinds[name]]
        if not Decimal(str(bound.min)) <= v <= Decimal(str(bound.max)):
            result.out_of_bounds.append(
                f"{name} {show(v)} {CARD_KIND_UNIT[kinds[name]]} outside {bound.min:g}–{bound.max:g}"
            )
        values[name] = v
        src = "STAFF" if name in overrides else (d or {}).get("source", "MISSING")
        if SOURCE_RANK.get(src, 4) > SOURCE_RANK[result.source]:
            result.source = src
        result.inputs[name] = {"value": show(v, "0.0001"), "unit": CARD_KIND_UNIT[kinds[name]], "source": src,
                               "refs": (d or {}).get("refs", {})}  # fmt: skip
        parts.append(_input_text(name, v, d, name in overrides, CARD_KIND_UNIT[kinds[name]]))
    if result.missing or result.kind_mismatch:
        return result
    factor = Decimal(str(spec.factor))
    if spec.kind == "area":
        assert spec.input is not None
        height = values[spec.height_input] if spec.height_input else Decimal(str(spec.height))
        if not spec.height_input:
            parts.append(f"height {num(spec.height or 0)} ft (card basis)")
        raw = values[spec.input] * height
        if raw > Decimal(str(card.bounds["area"].max)):
            result.out_of_bounds.append(f"area {show(raw)} sq ft above {card.bounds['area'].max:g}")
    elif spec.kind == "direct":
        assert spec.input is not None
        raw = values[spec.input]
    elif spec.kind == "count":
        raw = values[spec.input] if spec.input else Decimal(str(spec.count))
        if not spec.input:
            parts.append(f"{num(spec.count or 0)} nos (card basis)")
    else:
        raw = Decimal(1)
        parts.append("1 lump sum (card basis)")
    qty = q(raw * factor)
    if factor != 1:
        parts.append(f"× {num(factor)} (card factor)")
    result.quantity = qty
    unit = {"SFT": "sq ft", "RFT": "rft", "NOS": "nos", "LUMP": "lump"}[line.uom]
    op = " × " if spec.kind == "area" else ", "
    result.derivation = (op.join(parts) + f" = {show(qty)} {unit}")[:500]
    return result


def measured_count(facts: Facts, types: tuple[str, ...] | None, statuses: tuple[str, ...]) -> tuple[int, str]:
    n, where = _sum_points(facts, types, statuses)
    st = "/".join(s.lower() for s in statuses)
    return n, f"{n} captured {st} points" + (f" ({', '.join(where)})" if where else "")
