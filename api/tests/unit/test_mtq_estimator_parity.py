"""MTQ quantity evaluation ↔ the authoritative estimator engine (PR #91 certification, merge condition 1).

The MTQ BOQ evaluates the rate card's own quantity bases on measured inputs (``quantity.line_quantity``) and prices
with the estimator's ``line_amount_minor``. This proves the two agree on every concept they share, line by line, on the
SYNTHETIC card: units, whole-number counts, decimal precision, rounding (0.01 half up, once), bounds, incompatible
quantity kinds and the amount calculation. Where they differ on purpose, the difference is asserted and explained:

- a missing input: the estimator (a budget) substitutes the card's typical value and lists it as an assumption; the
  BOQ never substitutes a value, it reports the input missing and blocks review;
- a zero quantity: the estimator drops the line; the BOQ keeps it, classified VALID_ZERO (never silently dropped);
- quantity roles: the estimator takes one kitchen RUN for every kitchen line (a budget); the BOQ evaluates each line on
  its own role (the counter run for base units, the wall-unit run for wall units and lofts). Each line still agrees
  with the estimator run on that line's role value;
- precision of a length: the estimator receives a customer-entered value in feet; MTQ derives feet from integer
  millimetres exactly (mm / 304.8, no intermediate rounding), so the only rounding is the shared final one.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from veda.modules.estimator import engine, ratecard
from veda.modules.mtq_commercial import quantity

CARD = ratecard.parse(
    json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
)
UNIT = {"length": "ft", "area": "sqft", "count": "nos"}


def _estimator(product: str, room: str, values: dict, options: dict | None = None) -> engine.Estimate:
    spec = CARD.product(product)
    kinds = {i.name: i.kind for i in spec.inputs}
    sel = engine.Selection(room=room, product=product, options=options or {},
                           measurements={n: engine.Measurement(value=v, unit=UNIT[kinds[n]]) for n, v in values.items()})  # fmt: skip
    req = engine.EstimateRequest(property_type="APARTMENT", home_size="2BHK", project_kind="NEW_HOME",
                                 package="ESSENTIAL", selections=(sel,))  # fmt: skip
    return engine.calculate(CARD, req)


def _mtq(product: str, values: dict, options: dict | None = None) -> dict[str, quantity.LineQuantity]:
    spec = CARD.product(product)
    chosen = {o.name: o.default for o in spec.options} | (options or {})
    overrides = {n: str(v) for n, v in values.items()}  # inputs as entered, in the card's units
    return {
        line.code: quantity.line_quantity(CARD, spec, line, {}, overrides)
        for line in spec.lines
        if all(chosen.get(w.option) in w.is_ for w in line.when)
    }


CASES = [
    # product, room, inputs (card units), options: area with a height input, area with a card height, lump
    ("WARDROBE", "MASTER_BEDROOM", {"WIDTH": 7.33, "HEIGHT": 7.0}, {"GLASS": "YES"}),
    ("WARDROBE", "BEDROOM_2", {"WIDTH": 6.0, "HEIGHT": 7.0}, {"DOOR": "SLIDING", "LOFT": "NO"}),
    # direct, direct × factor (fractional NOS from the card's own basis), rounding half up
    ("FALSE_CEILING", "LIVING", {"AREA": 150.12}, {"DESIGN": "COVE"}),
    ("WINDOW_SEATING", "LIVING", {"WIDTH": 3.3425}, {}),  # 3.3425 × 2 = 6.685 → 6.69 (half up, not half even)
    # count input, lump, areas on a run
    ("KITCHEN", "KITCHEN", {"RUN": 10.5, "DRAWERS": 4}, {}),
    # count constant
    ("BED", "MASTER_BEDROOM", {}, {}),
    ("CEILING_PROFILE_LIGHTING", "LIVING", {"LENGTH": 42.75, "COB": 3}, {}),
]


@pytest.mark.parametrize(("product", "room", "values", "options"), CASES)
def test_same_quantities_and_amounts(product, room, values, options):
    spec = CARD.product(product)
    assert all(i.name in values for i in spec.inputs), "a missing input is the documented difference, tested below"
    est = _estimator(product, room, values, options)
    mtq = _mtq(product, values, options)
    est_lines = {x.code: x for x in est.lines}
    assert est_lines, product
    assert set(est_lines) == {code for code, lq in mtq.items() if lq.quantity}, product
    for code, x in est_lines.items():
        lq = mtq[code]
        assert not (lq.missing or lq.kind_mismatch or lq.not_whole or lq.out_of_bounds), (product, code)
        assert lq.quantity == x.quantity, (product, code, lq.quantity, x.quantity)
        assert engine.line_amount_minor(lq.quantity, x.rate_minor) == x.amount_minor
        line = next(ln for ln in spec.lines if ln.code == code)
        assert x.rate_minor == line.rates["ESSENTIAL"]


def test_rounding_is_half_up_once():
    lq = _mtq("WINDOW_SEATING", {"WIDTH": 3.3425})["SEAT"]
    assert lq.quantity == Decimal("6.69")
    assert _estimator("WINDOW_SEATING", "LIVING", {"WIDTH": 3.3425}).lines[0].quantity == Decimal("6.69")


def test_whole_number_counts_agree():
    with pytest.raises(engine.EstimateError) as err:
        _estimator("KITCHEN", "KITCHEN", {"RUN": 10.0, "DRAWERS": 2.5})
    assert err.value.errors[0]["message"] == "Must be a whole number."
    tandem = _mtq("KITCHEN", {"RUN": 10.0, "DRAWERS": 2.5})["TANDEM"]
    assert tandem.quantity is None and tandem.not_whole == ["DRAWERS 2.5 is not a whole number"]


def test_bounds_agree():
    with pytest.raises(engine.EstimateError) as err:
        _estimator("WINDOW_SEATING", "LIVING", {"WIDTH": 0.4})
    assert err.value.errors[0]["code"] == "OUT_OF_BOUNDS"
    assert _mtq("WINDOW_SEATING", {"WIDTH": 0.4})["SEAT"].out_of_bounds  # a blocking IMPOSSIBLE_QUANTITY in the BOQ


def test_incompatible_kinds_are_refused_by_both():
    spec = CARD.product("WINDOW_SEATING")
    sel = engine.Selection(room="LIVING", product="WINDOW_SEATING",
                           measurements={"WIDTH": engine.Measurement(value=4, unit="nos")})  # fmt: skip
    req = engine.EstimateRequest(property_type="APARTMENT", home_size="2BHK", project_kind="NEW_HOME",
                                 package="ESSENTIAL", selections=(sel,))  # fmt: skip
    with pytest.raises(engine.EstimateError) as err:
        engine.calculate(CARD, req)
    assert err.value.errors[0]["code"] == "INVALID_UNIT"
    seat = next(ln for ln in spec.lines if ln.code == "SEAT")
    count = {"kind": "count", "unit": "nos", "count": 4, "value": "4", "source": "MEASURED"}
    lq = quantity.line_quantity(CARD, spec, seat, {"WIDTH": count}, {})
    assert lq.quantity is None and lq.kind_mismatch == ["WIDTH"]  # a blocking QUANTITY_KIND_MISMATCH in the BOQ


def test_documented_difference_missing_input():
    est = _estimator("WINDOW_SEATING", "LIVING", {})
    assert est.lines[0].typical and est.assumptions  # the budget assumes the card's typical width
    seat = _mtq("WINDOW_SEATING", {})["SEAT"]
    assert seat.quantity is None and seat.missing == ["WIDTH"]  # the BOQ never assumes it


def test_documented_difference_zero_count():
    est = _estimator("CEILING_PROFILE_LIGHTING", "LIVING", {"LENGTH": 20.0, "COB": 0})
    assert "COB" not in {x.code for x in est.lines}  # the estimator drops a zero line
    cob = _mtq("CEILING_PROFILE_LIGHTING", {"LENGTH": 20.0, "COB": 0})["COB"]
    assert cob.quantity == Decimal("0.00")  # the BOQ keeps it (quantity_status VALID_ZERO)


def test_exact_millimetres_then_one_rounding():
    """A measured 2235 mm wardrobe: exact feet (7.3326… ft), multiplied, rounded once. Rounding the length to 7.33 ft
    first (as a customer would type it) can differ in the last place; MTQ never rounds before the product."""
    spec = CARD.product("WARDROBE")
    body = next(ln for ln in spec.lines if ln.code == "BODY")
    dims = {"WIDTH": {"kind": "length", "mm": 2235, "value": "7.33", "source": "MEASURED"},
            "HEIGHT": {"kind": "length", "mm": 2134, "value": "7.00", "source": "MEASURED"}}  # fmt: skip
    lq = quantity.line_quantity(CARD, spec, body, dims, {})
    exact = (Decimal(2235) / Decimal("304.8")) * (Decimal(2134) / Decimal("304.8"))
    assert lq.quantity == quantity.q(exact)


def test_kitchen_roles_agree_line_by_line_with_the_estimator():
    """Counter run 17.72 ft, wall-unit run 13.78 ft: base lines match an estimate with RUN 17.72, wall-unit and loft
    lines match an estimate with RUN 13.78; one estimate on either run would misprice the other lines."""
    from veda.modules.mtq_commercial import rules

    itype = rules.item_type("KITCHEN")
    spec = CARD.product("KITCHEN")
    overrides = {"RUN": "17.72", "WALL_UNIT_RUN": "13.78", "DRAWERS": "4"}
    by_run = {run: {x.code: x for x in _estimator("KITCHEN", "KITCHEN", {"RUN": float(run), "DRAWERS": 4}).lines}
              for run in ("17.72", "13.78")}  # fmt: skip
    for line in spec.lines:
        d, o = quantity.for_line(itype, line.code, {}, overrides)
        lq = quantity.line_quantity(CARD, spec, line, d, o)
        expected = by_run["13.78" if itype.roles_for(line.code) else "17.72"][line.code]
        assert lq.quantity == expected.quantity, line.code
        assert engine.line_amount_minor(lq.quantity, expected.rate_minor) == expected.amount_minor
    assert by_run["17.72"]["WALL"].quantity != by_run["13.78"]["WALL"].quantity  # the roles really differ
