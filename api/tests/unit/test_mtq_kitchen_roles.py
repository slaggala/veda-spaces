"""Kitchen quantity roles (PR #91 final merge condition): the card measures base units, wall units, lofts and their
shutters with one RUN input; the ruleset gives each line its own quantity role. The counter run (RUN) continues
beneath windows; the wall-unit run (WALL_UNIT_RUN, also the loft run) loses every opening that crosses the wall-unit
zone, and is UNRESOLVED and blocking, never the counter run, when the geometry cannot place an opening.
SYNTHETIC fixtures only; no clearance or wall-unit band is assumed (OI-MTQ-04)."""

from __future__ import annotations

from decimal import Decimal

from tests.unit.test_mtq_quantity_matrix import FT, centi, codes, facts, op, run, wall
from veda.modules.mtq_commercial import quantity, rules

WALL_LINES = ("WALL", "SOFT_CLOSE_WALL", "LOFT", "SOFT_CLOSE_LOFT")


def kitchen(*walls, **m):
    return facts({"ceiling_height_mm": 2900, **m, "walls": list(walls)}, space_type="KITCHEN")


def area(run_mm: int, height_ft: str) -> int:
    return centi(Decimal(run_mm) / FT * Decimal(height_ft))


def no_sill(kind: str, width: int, offset: int, oid: str) -> dict:
    return {"id": oid, "opening_type_code": kind, "width_mm": width, "height_mm": 1200,
            "offset_from_wall_start_mm": offset, "sill_height_mm": None}  # fmt: skip


def test_roles_are_declared_per_line():
    itype = rules.item_type("KITCHEN")
    assert {c: itype.roles_for(c) for c in WALL_LINES} == {c: {"RUN": "WALL_UNIT_RUN"} for c in WALL_LINES}
    assert itype.roles_for("BASE") == {} and itype.roles_for("SOFT_CLOSE") == {}  # base units use RUN itself
    assert itype.inputs["WALL_UNIT_RUN"].kind == "wall_unit_run" and itype.inputs["RUN"].deduct == "floor_openings"


# --- the reviewer's exact fixture: A, B, C ------------------------------------------------------------------------
def test_reviewer_fixture_base_kept_wall_units_lose_the_window():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [op("WINDOW", 1200, 900, "o1")]), wall(2, 2400, ["KITCHEN_RUN"]))
    dims, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    base, wall_run = dims["RUN"], dims["WALL_UNIT_RUN"]
    # A. the counter run continues beneath the window
    assert base["mm"] == 5400 and base["role"] == "RUN" and base["status"] == "RESOLVED"
    assert lines["BASE"].calculated_quantity_centi == area(5400, "3") == 5315
    assert lines["SOFT_CLOSE"].calculated_quantity_centi == area(5400, "2.9")
    # B. wall units lose the window: 4200 mm × 2 ft = 27.56 sq ft (was 35.43 on the counter run)
    assert wall_run["mm"] == 4200 and wall_run["source"] == "DERIVED" and wall_run["refs"]["opening_ids"] == ["o1"]
    assert wall_run["refs"]["wall_ids"] == ["w1", "w2"]
    assert (wall_run["role"], wall_run["rule"], wall_run["rule_version"]) == (
        "WALL_UNIT_RUN",
        "wall_unit_run",
        "2026.10.3",
    )
    wall_line = lines["WALL"]
    assert wall_line.calculated_quantity_centi == area(4200, "2") == 2756 != area(5400, "2") == 3543
    assert wall_line.quantity_status == "VALID" and wall_line.uom_code == "SFT"
    assert wall_line.formula_inputs["inputs"]["RUN"]["role"] == "WALL_UNIT_RUN"
    assert wall_line.formula_inputs["inputs"]["RUN"]["refs"]["opening_ids"] == ["o1"]
    assert "wall_unit_run" in wall_line.derivation
    # C. soft-close wall shutters follow the same geometry; the loft run is the wall-unit run (04 KITCHEN_LOFT)
    for code in ("SOFT_CLOSE_WALL", "LOFT", "SOFT_CLOSE_LOFT"):
        assert lines[code].calculated_quantity_centi == area(4200, "2"), code


# --- D, E ----------------------------------------------------------------------------------------------------------
def test_wall_units_without_a_window_take_the_full_run():
    dims, lines = run("KITCHEN", kitchen(wall(1, 3000, ["KITCHEN_RUN"]), wall(2, 2400, ["KITCHEN_RUN"])),
                      overrides={"DRAWERS": "4"})  # fmt: skip
    assert dims["WALL_UNIT_RUN"]["mm"] == dims["RUN"]["mm"] == 5400 and dims["WALL_UNIT_RUN"]["source"] == "MEASURED"
    assert lines["WALL"].calculated_quantity_centi == lines["LOFT"].calculated_quantity_centi == area(5400, "2")


def test_a_door_cuts_both_runs():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [op("DOOR", 900, 0, "d1", height=2100)]))
    dims, _ = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert dims["RUN"]["mm"] == dims["WALL_UNIT_RUN"]["mm"] == 2100
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [{**op("FRENCH_WINDOW", 1200, 1000, "f1"), "sill_height_mm": None}]))
    dims, _ = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert dims["WALL_UNIT_RUN"]["mm"] == 1800  # a full-height opening starts at the floor even without a sill


# --- F -------------------------------------------------------------------------------------------------------------
def test_a_window_without_a_sill_leaves_wall_units_unresolved_and_blocking():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [no_sill("WINDOW", 1200, 900, "o1")]), wall(2, 2400, ["KITCHEN_RUN"]))
    dims, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert dims["RUN"]["mm"] == 5400  # the counter run does not need the sill
    w = dims["WALL_UNIT_RUN"]
    assert w["source"] == "MISSING" and w["status"] == "UNRESOLVED" and "no sill height" in w["explain"]
    assert "never the counter run" in w["explain"] and w["refs"]["wall_ids"] == ["w1", "w2"]
    for code in WALL_LINES:
        x = lines[code]
        assert x.calculated_quantity_centi is None and x.quantity_status == "UNRESOLVED" and x.status == "ISSUE"
        assert "MISSING_MEASUREMENT" in codes(x) and "WALL_UNIT_RUN" in x.issue_codes[0]["message"]
    assert lines["BASE"].quantity_status == "VALID"
    # a counter-run entry is not a wall-unit entry; an explicit wall-unit entry resolves it
    _, lines = run("KITCHEN", f, overrides={"DRAWERS": "4", "RUN": "17"})
    assert lines["WALL"].quantity_status == "UNRESOLVED"
    _, lines = run("KITCHEN", f, overrides={"DRAWERS": "4", "WALL_UNIT_RUN": "13.78"})
    assert (
        lines["WALL"].calculated_quantity_centi == centi(Decimal("13.78") * 2)
        and lines["WALL"].quantity_status == "VALID"
    )
    assert lines["BASE"].calculated_quantity_centi == 5315


def test_no_lintel_or_ceiling_height_leaves_the_zone_unknown():
    f = facts({"walls": [wall(1, 3000, ["KITCHEN_RUN"], [op("WINDOW", 1200, 900, "o1")])]}, space_type="KITCHEN")
    dims, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert dims["WALL_UNIT_RUN"]["source"] == "MISSING" and lines["WALL"].quantity_status == "UNRESOLVED"


# --- G, H ----------------------------------------------------------------------------------------------------------
def test_multiple_windows_and_one_above_the_lintel():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [op("WINDOW", 600, 300, "o1"), op("WINDOW", 900, 1500, "o2"),
                                                 op("VENTILATOR", 450, 2500, "v1", height=300, sill=2200)]),
                floor_to_lintel_mm=2134)  # fmt: skip
    dims, _ = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    w = dims["WALL_UNIT_RUN"]
    assert w["mm"] == 3000 - 600 - 900 and w["refs"]["opening_ids"] == ["o1", "o2"]  # the ventilator is above the zone
    assert dims["RUN"]["mm"] == 3000


def test_overlapping_or_impossible_openings_are_unresolved_never_negative():
    for openings, problem in (
        ([op("WINDOW", 1200, 900, "o1"), op("WINDOW", 900, 1800, "o2")], "overlap"),
        ([op("WINDOW", 1200, 2500, "o1")], "outside"),
        ([{**op("WINDOW", 1200, 0, "o1"), "offset_from_wall_start_mm": None}], "no offset"),
    ):
        dims, lines = run("KITCHEN", kitchen(wall(1, 3000, ["KITCHEN_RUN"], openings)), overrides={"DRAWERS": "4"})
        w = dims["WALL_UNIT_RUN"]
        assert w["source"] == "MISSING" and problem in w["explain"], problem
        assert lines["WALL"].calculated_quantity_centi is None and lines["WALL"].quantity_status == "UNRESOLVED"
    # a wall the openings take entirely is a zero run, kept and blocking (never the counter run)
    dims, lines = run("KITCHEN", kitchen(wall(1, 1200, ["KITCHEN_RUN"], [op("WINDOW", 1200, 0, "o1")])),
                      overrides={"DRAWERS": "4"})  # fmt: skip
    assert dims["WALL_UNIT_RUN"]["mm"] == 0 and dims["RUN"]["mm"] == 1200
    assert lines["WALL"].quantity_status == "INVALID" and "IMPOSSIBLE_QUANTITY" in codes(lines["WALL"])


# --- I, J ----------------------------------------------------------------------------------------------------------
def test_multiple_kitchen_walls_aggregate_once():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [op("WINDOW", 1200, 900, "o1")]),
                wall(2, 2400, ["KITCHEN_RUN"], [op("WINDOW", 600, 900, "o2")]),
                wall(3, 1800, ["KITCHEN_RUN"]), wall(4, 3000, [], [op("DOOR", 900, 100, "d1", height=2100)]))  # fmt: skip
    dims, _ = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    assert dims["RUN"]["mm"] == 3000 + 2400 + 1800  # the untagged wall's door is not on a run
    w = dims["WALL_UNIT_RUN"]
    assert w["mm"] == 1800 + 1800 + 1800 and w["refs"]["wall_ids"] == ["w1", "w2", "w3"]
    assert w["refs"]["opening_ids"] == ["o1", "o2"]


def test_base_wall_loft_and_tall_unit_each_use_their_own_role():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN", "TALL_UNIT"], [op("WINDOW", 1200, 900, "o1")]),
                wall(2, 2400, ["KITCHEN_RUN"]))  # fmt: skip
    dims, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    roles = {code: x.formula_inputs["inputs"].get("RUN", {}).get("role") for code, x in lines.items()}
    assert roles == {"BASE": "RUN", "SOFT_CLOSE": "RUN", "WALL": "WALL_UNIT_RUN", "SOFT_CLOSE_WALL": "WALL_UNIT_RUN",
                     "LOFT": "WALL_UNIT_RUN", "SOFT_CLOSE_LOFT": "WALL_UNIT_RUN", "TANDEM": None, "PLUMBING": None}  # fmt: skip
    assert lines["TANDEM"].calculated_quantity_centi == 400  # accessory count unchanged
    _, tall = run("KITCHEN_TALL_UNIT", f)
    (line,) = tall.values()  # still unmapped: kept, unpriced, no invented rate
    assert line.formula_kind == "UNMAPPED" and line.quantity_status == "UNRESOLVED"


def test_utility_wall_unit_loses_the_window():
    f = facts({"ceiling_height_mm": 2700, "walls": [wall(1, 2400, ["KITCHEN_RUN"], [op("WINDOW", 900, 600, "o1")])]},
              space_type="UTILITY")  # fmt: skip
    dims, lines = run("UTILITY_UNIT", f)
    assert dims["WIDTH"]["mm"] == 1500 and lines["WALL"].calculated_quantity_centi == area(1500, "2")


def test_for_line_never_hands_a_wall_line_the_counter_value():
    itype = rules.item_type("KITCHEN")
    dims = {"RUN": {"mm": 5400}, "WALL_UNIT_RUN": {"mm": 4200}}
    d, o = quantity.for_line(itype, "WALL", dims, {"RUN": "20"})
    assert d["RUN"] == {"mm": 4200} and "RUN" not in o
    d, o = quantity.for_line(itype, "BASE", dims, {"RUN": "20"})
    assert d["RUN"] == {"mm": 5400} and o == {"RUN": "20"}


def test_reviewer_fixture_every_line_keeps_source_rule_unit_raw_rounded_and_status():
    f = kitchen(wall(1, 3000, ["KITCHEN_RUN"], [op("WINDOW", 1200, 900, "o1")]), wall(2, 2400, ["KITCHEN_RUN"]))
    _, lines = run("KITCHEN", f, overrides={"DRAWERS": "4"})
    expected = {  # line: (role, rule, run mm, card height ft, source, rounded centi)
        "BASE": ("RUN", "tagged_run_total", 5400, "3", "MEASURED", 5315),
        "SOFT_CLOSE": ("RUN", "tagged_run_total", 5400, "2.9", "MEASURED", 5138),
        "WALL": ("WALL_UNIT_RUN", "wall_unit_run", 4200, "2", "DERIVED", 2756),
        "SOFT_CLOSE_WALL": ("WALL_UNIT_RUN", "wall_unit_run", 4200, "2", "DERIVED", 2756),
        "LOFT": ("WALL_UNIT_RUN", "wall_unit_run", 4200, "2", "DERIVED", 2756),
        "SOFT_CLOSE_LOFT": ("WALL_UNIT_RUN", "wall_unit_run", 4200, "2", "DERIVED", 2756),
    }
    for code, (role, rule, run_mm, height, source, rounded) in expected.items():
        x = lines[code]
        used = x.formula_inputs["inputs"]["RUN"]
        raw = Decimal(run_mm) / FT * Decimal(height)
        assert (used["role"], used["rule"], used["rule_version"], used["source"]) == (
            role,
            rule,
            "2026.10.3",
            source,
        ), code
        assert Decimal(x.formula_inputs["raw_quantity"]) == raw and x.calculated_quantity_centi == centi(raw) == rounded
        assert x.uom_code == "SFT" and x.quantity_status == "VALID" and x.status == "OK", code
        assert used["refs"]["wall_ids"] == ["w1", "w2"]
        assert used["refs"].get("opening_ids", []) == ([] if role == "RUN" else ["o1"]), code
    assert lines["WALL"].calculated_quantity_centi != 3543  # no longer the counter run's 35.43 sq ft
