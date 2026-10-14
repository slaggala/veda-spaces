"""MTQ B2 ruleset and quantity engine (pure): card quantity bases on measured inputs, exact and explainable."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from veda.modules.estimator import ratecard
from veda.modules.mtq_commercial import quantity, rules
from veda.modules.mtq_commercial import vocab as V
from veda.modules.mtq_commercial.site import Facts

CARD = ratecard.parse(
    json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
)


def facts(m: dict, space_type="BEDROOM", zone="INDOOR") -> Facts:
    sp = SimpleNamespace(id="sp1", label="Bedroom 2", space_type_code=space_type, zone_code=zone)
    mset = SimpleNamespace(id="set1", revision_no=1)
    return Facts(prop=SimpleNamespace(id="p1"), mset=mset, spaces={"sp1": sp}, measured={"sp1": {"id": "sm1", **m}})  # type: ignore[arg-type]


def wall(i, length, tags=(), openings=(), height=None):
    return {"id": f"w{i}", "wall_index": i, "length_mm": length, "height_mm": height, "wall_type_code": "MASONRY",
            "is_proposed": False, "usable_for_code": list(tags), "openings": list(openings)}  # fmt: skip


def test_ruleset_is_valid_versioned_and_still_proposed():
    rs = rules.load()
    assert rs.ruleset_version == rules.RULESET_VERSION and len(rules.sha256()) == 64
    assert rs.status == "PROPOSED" and not rs.approved  # OI-MTQ-03/04 not decided: never claimed as approved
    assert set(rs.item_types) == set(V.REQUIREMENT_TYPES)
    for code, t in rs.item_types.items():
        if t.card_product is not None:
            product = CARD.product(t.card_product)
            assert product is not None, code
            names = {i.name for i in product.inputs}
            roles = {role for m in t.line_inputs.values() for role in m.values()}
            assert set(t.inputs) - roles <= names and not roles & names, code  # a role is never a card input name
            lines = {ln.code for ln in product.lines}
            for line, mapping in t.line_inputs.items():  # each role feeds an existing card line's existing input
                assert line in lines and set(mapping) <= names, (code, line)
            for opt, choice in t.fixed_options.items():
                assert choice in next(o for o in product.options if o.name == opt).choices
        else:
            assert t.unmapped_reason


def test_wardrobe_body_is_the_cards_area_basis_on_measured_inputs():
    f = facts({"floor_to_lintel_mm": 2100, "ceiling_height_mm": 2900,
               "walls": [wall(1, 3000, ["NONE"]), wall(2, 3300, ["WARDROBE"])]})  # fmt: skip
    itype = rules.item_type("WARDROBE")
    dims = quantity.derive_inputs(itype, f, "sp1", 2)
    assert dims["WIDTH"]["mm"] == 3300 and dims["WIDTH"]["source"] == "MEASURED"
    assert dims["HEIGHT"]["mm"] == 2100 and dims["HEIGHT"]["source"] == "DERIVED"
    product = CARD.product("WARDROBE")
    body = next(line for line in product.lines if line.code == "BODY")
    lq = quantity.line_quantity(CARD, product, body, dims, {})
    exact = Decimal(3300) * Decimal(2100) / (Decimal("304.8") ** 2)
    assert lq.quantity == exact.quantize(Decimal("0.01")) and lq.formula_kind == "CARD_AREA"
    assert "W2 length 3300 mm" in lq.derivation and lq.derivation.endswith("sq ft")
    loft = next(line for line in product.lines if line.code == "LOFT")
    lq = quantity.line_quantity(CARD, product, loft, dims, {})
    assert "height 2 ft (card basis)" in lq.derivation  # the card's basis, not an invented loft height
    # the loft option comes from the ceiling clearance: 2900 − 2134 = 766 ≥ 450
    assert quantity.options_from_rules(itype, f, "sp1")["LOFT"]["value"] == "YES"


def test_openings_split_the_run_and_missing_lintel_is_an_assumption():
    door = {
        "id": "o1",
        "opening_type_code": "DOOR",
        "width_mm": 900,
        "height_mm": 2100,
        "offset_from_wall_start_mm": 2400,
    }
    f = facts({"ceiling_height_mm": 2900, "walls": [wall(1, 3600, ["WARDROBE"], [door])]})
    dims = quantity.derive_inputs(rules.item_type("WARDROBE"), f, "sp1", None)
    assert dims["WIDTH"]["mm"] == 2400 and dims["WIDTH"]["source"] == "DERIVED"
    assert dims["HEIGHT"]["source"] == "ASSUMED" and dims["HEIGHT"]["mm"] == 2134
    assert quantity.worst_source(dims, {}) == "ASSUMED"


def test_missing_inputs_and_bounds_are_reported_not_guessed():
    f = facts({"walls": [wall(1, 3000, ["NONE"])]})
    dims = quantity.derive_inputs(rules.item_type("KITCHEN"), f, "sp1", None)
    assert dims["RUN"]["source"] == "MISSING" and dims["DRAWERS"]["source"] == "MISSING"
    product = CARD.product("KITCHEN")
    base = next(line for line in product.lines if line.code == "BASE")
    lq = quantity.line_quantity(CARD, product, base, dims, {})
    assert lq.quantity is None and lq.missing == ["RUN"]
    lq = quantity.line_quantity(CARD, product, base, dims, {"RUN": "400"})
    assert lq.quantity == Decimal("1200.00") and lq.out_of_bounds  # 400 ft is outside the card's length bounds


@pytest.mark.parametrize("mm", [1, 999, 304800])
def test_quantities_are_exact_and_rounded_once(mm):
    assert quantity.to_centi(quantity.ft(mm)) == int((Decimal(mm) / Decimal("304.8")).quantize(Decimal("0.01")) * 100)
