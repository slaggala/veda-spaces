"""MTQ quantity regression matrix (PR #91 certification, merge blocker 4).

Deterministic fixtures, no database: a verified measurement as B1 presents it, the scope ruleset's derivation, the
SYNTHETIC rate card's quantity basis. Every case pins the measurement input, the measurement ids the value is traced
to, the rule invoked, the exact (unrounded) quantity, the rounded quantity, the unit and the line's quantity status.
Nothing here is a real site, rate or owner value.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from veda.modules.estimator import ratecard
from veda.modules.mtq_commercial import boqs, quantity, rules
from veda.modules.mtq_commercial.models import BoqLine
from veda.modules.mtq_commercial.site import Facts

CARD_RAW = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
CARD = ratecard.parse(CARD_RAW)
FT = Decimal("304.8")


def facts(m: dict[str, Any], space_type: str = "BEDROOM", zone: str = "INDOOR") -> Facts:
    sp = SimpleNamespace(id="sp1", label="Room", space_type_code=space_type, zone_code=zone)
    return Facts(prop=SimpleNamespace(id="p1"), mset=SimpleNamespace(id="set1", revision_no=1), spaces={"sp1": sp},
                 measured={"sp1": {"id": "sm1", **m}})  # fmt: skip


def wall(i: int, length: int, tags=(), openings=(), height: int | None = None) -> dict[str, Any]:
    return {"id": f"w{i}", "wall_index": i, "length_mm": length, "height_mm": height, "wall_type_code": "MASONRY",
            "is_proposed": False, "usable_for_code": list(tags), "openings": list(openings)}  # fmt: skip


def op(kind: str, width: int, offset: int | None, oid: str, height: int = 1200, sill: int | None = None):
    sill = sill if sill is not None else (900 if kind == "WINDOW" else 0)
    return {"id": oid, "opening_type_code": kind, "width_mm": width, "height_mm": height,
            "offset_from_wall_start_mm": offset, "sill_height_mm": sill}  # fmt: skip


def point(kind: str, status: str, qty: int, sensor: str | None = None, switching: str | None = None):
    return {"point_type_code": kind, "status_code": status, "quantity": qty, "sensor_type_code": sensor,
            "switching_code": switching}  # fmt: skip


def run(item_type: str, f: Facts, *, space_id: str | None = "sp1", anchor: int | None = None, card=CARD,
        overrides: dict | None = None, options: dict | None = None, inclusion: str = "INCLUDED"):  # fmt: skip
    """The scope item as scopes._resolve builds it, then its BOQ lines as boqs.generate classifies them."""
    itype = rules.item_type(item_type)
    dims = quantity.derive_inputs(itype, f, space_id, anchor)
    item = SimpleNamespace(
        id="i1", requirement_id="r1", space_id=space_id, item_type_code=item_type, inclusion_code=inclusion,
        necessity_code="RECOMMENDED", card_product_code=itype.card_product, label=itype.label, anchor_wall_index=anchor,
        dimensions={"inputs": dims, "option_rules": quantity.options_from_rules(itype, f, space_id)},
        dimension_overrides=overrides or {}, options=options or {}, dimension_source_code="MEASURED",
    )  # fmt: skip
    out = []
    for data in boqs._lines_for(card, item, SimpleNamespace(preferences={}), f, itype.label):
        issues = data.pop("issues")
        line = BoqLine(issue_codes=issues, **data)
        line.final_quantity_centi = line.calculated_quantity_centi
        line.status = boqs._status(line)
        out.append(line)
    return dims, {x.card_line_code or x.item_type_code: x for x in out}


def centi(value: Decimal) -> int:
    return quantity.to_centi(value)


def codes(line: BoqLine) -> set[str]:
    return {i["code"] for i in boqs.line_blockers(line)}


# --- 1. window seat: the span across the window -------------------------------------------------------------------
def test_window_seat_spans_the_window():
    f = facts({"ceiling_height_mm": 2900,
               "walls": [wall(1, 3000, ["WINDOW_SEATING"], [op("WINDOW", 1500, 750, "o1")])]})  # fmt: skip
    dims, lines = run("WINDOW_SEATING", f, anchor=1)
    assert rules.item_type("WINDOW_SEATING").inputs["WIDTH"].kind == "window_span"
    w = dims["WIDTH"]
    assert w["mm"] == 1500 and w["source"] == "MEASURED"
    assert w["refs"] == {"measurement_set_id": "set1", "measurement_revision_no": 1, "space_measurement_id": "sm1",
                         "wall_id": "w1", "wall_index": 1, "opening_id": "o1"}  # fmt: skip
    seat = lines["SEAT"]
    raw = Decimal(1500) / FT * 2  # card basis: WIDTH × 2 ft
    assert seat.calculated_quantity_centi == centi(raw) == 984 and seat.uom_code == "SFT"
    assert seat.quantity_status == "VALID" and not codes(seat)


def test_window_seat_across_two_windows_and_without_one():
    f = facts(
        {"walls": [wall(1, 4000, ["WINDOW_SEATING"], [op("WINDOW", 900, 500, "o1"), op("WINDOW", 900, 1700, "o2")])]}
    )
    dims, _ = run("WINDOW_SEATING", f, anchor=1)
    assert dims["WIDTH"]["mm"] == 2100 and dims["WIDTH"]["source"] == "DERIVED"  # 500 → 2600 mm
    assert dims["WIDTH"]["refs"]["opening_ids"] == ["o1", "o2"]
    dims, lines = run("WINDOW_SEATING", facts({"walls": [wall(1, 3000, ["WINDOW_SEATING"])]}), anchor=1)
    assert dims["WIDTH"]["source"] == "MISSING"  # no window: never the wall's length
    assert lines["SEAT"].quantity_status == "UNRESOLVED" and "MISSING_MEASUREMENT" in codes(lines["SEAT"])


# --- 2. kitchen base runs -----------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("label", "w1_openings", "expected_mm"),
    [
        ("with a window", [op("WINDOW", 1200, 900, "o1")], 5400),  # the counter continues beneath the window
        ("without a window", [], 5400),
        ("with a door", [op("DOOR", 900, 0, "o1", height=2100)], 4500),  # a door cuts the run
        ("with a floor-level window", [op("WINDOW", 1200, 900, "o1", sill=0)], 4200),  # recorded at floor level
    ],
)
def test_kitchen_base_run(label, w1_openings, expected_mm):
    f = facts({"ceiling_height_mm": 2900, "walls": [wall(1, 3000, ["KITCHEN_RUN"], w1_openings),
                                                     wall(2, 2400, ["KITCHEN_RUN"])]}, space_type="KITCHEN")  # fmt: skip
    dims, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert rules.item_type("KITCHEN").inputs["RUN"].deduct == "floor_openings"
    assert dims["RUN"]["mm"] == expected_mm, label
    assert dims["RUN"]["refs"]["wall_ids"] == ["w1", "w2"]
    base = lines["BASE"]
    raw = Decimal(expected_mm) / FT * 3
    assert base.calculated_quantity_centi == centi(raw) and base.uom_code == "SFT" and base.quantity_status == "VALID"


# --- 3. a wall the openings take entirely --------------------------------------------------------------------------
def test_fully_opened_wall_is_zero_and_invalid_never_full_length():
    f = facts({"floor_to_lintel_mm": 2134, "walls": [wall(1, 1500, ["WARDROBE"], [op("DOOR", 1500, 0, "o1", 2100)])]})
    dims, lines = run("WARDROBE", f, anchor=1)
    assert dims["WIDTH"]["mm"] == 0 and dims["WIDTH"]["source"] == "DERIVED"
    assert "no usable stretch" in dims["WIDTH"]["explain"]
    body = lines["BODY"]  # kept, not dropped
    assert body.calculated_quantity_centi == 0 and body.quantity_status == "INVALID"
    assert "IMPOSSIBLE_QUANTITY" in codes(body)
    # an opening with no offset is a different case: the clear stretch is unknown, so the whole wall is ASSUMED
    f = facts({"floor_to_lintel_mm": 2134, "walls": [wall(1, 1500, ["WARDROBE"], [op("DOOR", 800, None, "o1")])]})
    dims, _ = run("WARDROBE", f, anchor=1)
    assert dims["WIDTH"]["mm"] == 1500 and dims["WIDTH"]["source"] == "ASSUMED"


# --- 4. pooja unit shutter -----------------------------------------------------------------------------------------
def test_pooja_room_shutter_is_its_own_door_frame():
    f = facts({"walls": [wall(1, 1500, ["POOJA_UNIT"]), wall(2, 1200, [], [op("DOOR", 750, 200, "o9", 2100)])]},
              space_type="POOJA")  # fmt: skip
    dims, lines = run("POOJA_UNIT", f, anchor=1)
    d = dims["DOOR_WIDTH"]
    assert d["mm"] == 750 and d["source"] == "MEASURED" and d["refs"]["opening_id"] == "o9"
    door = lines["DOOR"]
    raw = Decimal(750) / FT * Decimal("7.5")
    assert door.calculated_quantity_centi == centi(raw) == 1845 and door.quantity_status == "VALID"


def test_pooja_niche_never_takes_the_room_entrance_door():
    f = facts({"walls": [wall(1, 4000, [], [op("DOOR", 1050, 200, "o1", 2100)]), wall(2, 3000, ["POOJA_UNIT"])]},
              space_type="LIVING")  # fmt: skip
    dims, lines = run("POOJA_UNIT", f, anchor=2)
    assert dims["DOOR_WIDTH"]["source"] == "MISSING" and "entrance door" in dims["DOOR_WIDTH"]["explain"]
    assert lines["DOOR"].quantity_status == "UNRESOLVED" and "MISSING_MEASUREMENT" in codes(lines["DOOR"])
    _, lines = run("POOJA_UNIT", f, anchor=2, overrides={"DOOR_WIDTH": "2"})  # staff enter the shutter width
    assert lines["DOOR"].calculated_quantity_centi == 1500 and lines["DOOR"].quantity_status == "VALID"


# --- 5. counts ------------------------------------------------------------------------------------------------------
def _kitchen():
    return facts({"walls": [wall(1, 3000, ["KITCHEN_RUN"])]}, space_type="KITCHEN")


def test_whole_drawer_count():
    _, lines = run("KITCHEN", _kitchen(), overrides={"DRAWERS": "4"})
    tandem = lines["TANDEM"]
    assert tandem.calculated_quantity_centi == 400 and tandem.uom_code == "NOS" and tandem.quantity_status == "VALID"


def test_fractional_drawer_count_is_invalid():
    _, lines = run("KITCHEN", _kitchen(), overrides={"DRAWERS": "2.5"})
    tandem = lines["TANDEM"]
    assert tandem.calculated_quantity_centi is None and tandem.quantity_status == "INVALID"
    assert "INVALID_COUNT" in codes(tandem)


# --- 6. rate-card quantity kinds -----------------------------------------------------------------------------------
def test_matching_quantity_kind():
    f = facts({"walls": [wall(1, 3000, ["TV_UNIT"])]}, space_type="LIVING")
    _, lines = run("TV_UNIT", f, anchor=1)
    assert lines and all(x.quantity_status == "VALID" for x in lines.values())


def test_wrong_quantity_kind_blocks_and_never_passes_review():
    raw = copy.deepcopy(CARD_RAW)
    for p in raw["products"]:
        if p["code"] == "TV_UNIT":
            for i in p["inputs"]:
                if i["name"] == "WIDTH":
                    i["kind"] = "count"
    f = facts({"walls": [wall(1, 3000, ["TV_UNIT"])]}, space_type="LIVING")
    _, lines = run("TV_UNIT", f, anchor=1, card=ratecard.parse(raw))
    assert lines
    for x in lines.values():
        assert x.calculated_quantity_centi is None and x.quantity_status == "INVALID" and x.status == "ISSUE"
        assert "QUANTITY_KIND_MISMATCH" in codes(x)


# --- 7. sensor-light provisions ------------------------------------------------------------------------------------
def test_sensor_points_need_sensor_and_switching():
    f = facts({"walls": [wall(1, 3000)], "electrical_points": [
        point("SENSOR_LIGHT", "NEW", 2, "PIR", "SENSOR"),
        point("SENSOR_LIGHT", "NEW", 1, "MICROWAVE", "BOTH"),
        point("SENSOR_LIGHT", "NEW", 1, "NONE", "SENSOR"),  # no sensor: not a provision
        point("SENSOR_LIGHT", "NEW", 1, "PIR", None),  # switching not captured
        point("SENSOR_LIGHT", "SHIFT", 2, "PIR", "SENSOR"),  # a shift is point shifting, not a new provision
    ]})  # fmt: skip
    n, why, unresolved = quantity.counted(f, rules.item_type("SENSOR_LIGHTING").measured_count)
    assert (n, unresolved) == (3, 2) and "unresolved" in why
    _, lines = run("SENSOR_LIGHTING", f, space_id=None)
    line = lines["SENSOR_LIGHTING"]
    assert line.calculated_quantity_centi == 300 and line.quantity_status == "UNRESOLVED"
    assert {"UNRESOLVED_SOURCE_POINTS", "UNRESOLVED_CATALOGUE_MAPPING"} <= codes(line)


def test_sensor_points_fully_captured():
    f = facts({"walls": [wall(1, 3000)], "electrical_points": [point("SENSOR_LIGHT", "NEW", 2, "PIR", "SENSOR")]})
    _, lines = run("SENSOR_LIGHTING", f, space_id=None, inclusion="OPTIONAL")
    line = lines["SENSOR_LIGHTING"]
    assert line.calculated_quantity_centi == 200 and line.quantity_status == "VALID"  # the count itself is sound
    assert not codes(line)  # optional: the missing catalogue line is disclosed, not blocking
    assert [i["code"] for i in line.issue_codes] == ["MISSING_CATALOGUE_MAPPING"]


# --- 8. wall panelling with door and window deductions -------------------------------------------------------------
def test_wall_panelling_deducts_door_and_window():
    f = facts({"ceiling_height_mm": 2900, "walls": [wall(1, 4000, ["FEATURE_WALL"], [
        op("DOOR", 900, 0, "o1", 2100), op("WINDOW", 1200, 2000, "o2")], height=2700)]}, space_type="LIVING")  # fmt: skip
    dims, lines = run("WALL_PANELLING", f, anchor=1)
    assert dims["WIDTH"]["mm"] == 1100 and dims["WIDTH"]["source"] == "DERIVED"  # 900→2000 is the longest clear stretch
    assert dims["HEIGHT"]["mm"] == 2700 and dims["HEIGHT"]["refs"]["wall_id"] == "w1"
    pan = lines["PANELLING"]
    raw = Decimal(1100) / FT * (Decimal(2700) / FT)
    assert pan.calculated_quantity_centi == centi(raw) and pan.uom_code == "SFT" and pan.quantity_status == "VALID"


# --- 9. wardrobe and loft ------------------------------------------------------------------------------------------
def test_wardrobe_and_loft():
    f = facts({"ceiling_height_mm": 2900, "floor_to_lintel_mm": 2134, "walls": [wall(1, 2400, ["WARDROBE"])]})
    dims, lines = run("WARDROBE", f, anchor=1)
    assert dims["WIDTH"]["mm"] == 2400 and dims["HEIGHT"]["mm"] == 2134
    raw = Decimal(2400) / FT * (Decimal(2134) / FT)
    assert lines["BODY"].calculated_quantity_centi == centi(raw) == 5513
    loft = lines["LOFT"]  # ceiling 2900 − 2134 = 766 mm ≥ 450: the loft option is on
    assert loft.calculated_quantity_centi == centi(Decimal(2400) / FT * 2) == 1575 and loft.quantity_status == "VALID"
    f = facts({"ceiling_height_mm": 2500, "floor_to_lintel_mm": 2134, "walls": [wall(1, 2400, ["WARDROBE"])]})
    _, lines = run("WARDROBE", f, anchor=1)
    assert "LOFT" not in lines  # 366 mm < 450: no loft line (an option, not a zero quantity)


# --- 10. false ceiling ---------------------------------------------------------------------------------------------
def test_false_ceiling_from_floor_area():
    f = facts({"derived_floor_area_sqft_centi": 15012, "shape_code": "RECTANGLE", "walls": [wall(1, 3000)]},
              space_type="LIVING")  # fmt: skip
    dims, lines = run("FALSE_CEILING", f)
    assert dims["AREA"]["centi"] == 15012 and dims["AREA"]["source"] == "DERIVED"
    assert lines["GYPSUM"].calculated_quantity_centi == 15012 and lines["GYPSUM"].uom_code == "SFT"
    panel = lines["PANEL_LIGHTS"]  # direct × 0.025: 3.753 → 3.75 nos (the card's own basis, as in the estimator)
    assert panel.calculated_quantity_centi == centi(Decimal("150.12") * Decimal("0.025")) == 375
