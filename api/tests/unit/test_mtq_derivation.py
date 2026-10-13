"""MTQ B1-T07: the derivation engine (blueprint §6.3) and the recorded tolerance policy (OI-MTQ-01, closure §2)."""

from __future__ import annotations

import pytest

from veda.modules.mtq import derivation as d
from veda.modules.mtq import tolerance as t


def test_square_foot_conversion_is_exact_and_rounds_half_up():
    assert d.mm2_to_sqft_centi(92_903_040 // 1000) == 100  # 92,903.04 mm² → 1 sq ft (floored input, rounds to 100)
    assert d.mm2_to_sqft_centi(3600 * 2700) == 10463  # 104.627 sq ft
    assert d.mm2_to_sqft_centi(0) == 0 and d.mm2_to_sqft_centi(-5) == 0
    assert all(isinstance(d.mm2_to_sqft_centi(n), int) for n in (1, 10, 10**9))


def test_polygon_area_and_perimeter():
    square = [(0, 0), (3000, 0), (3000, 3000), (0, 3000)]
    assert d.shoelace_mm2(square) == 9_000_000
    assert d.polygon_perimeter_mm(square) == 12_000
    ell = [(0, 0), (4000, 0), (4000, 2000), (2000, 2000), (2000, 4000), (0, 4000)]
    assert d.shoelace_mm2(ell) == 12_000_000


def _walls():
    return [
        {"wall_index": 0, "length_mm": 1500, "wall_type_code": "OPEN", "openings": []},
        {"wall_index": 1, "length_mm": 3000, "wall_type_code": "MASONRY",
         "openings": [{"width_mm": 900, "height_mm": 2100, "offset_from_wall_start_mm": 300, "deducts_from_wall_area": True}]},
        {"wall_index": 2, "length_mm": 3000, "wall_type_code": "MASONRY", "height_mm": 2500, "openings": []},
        {"wall_index": 3, "length_mm": 1500, "wall_type_code": "MASONRY", "openings": [
            {"width_mm": 600, "height_mm": 600, "offset_from_wall_start_mm": 0, "deducts_from_wall_area": False}]},
    ]  # fmt: skip


def test_open_edges_count_in_perimeter_not_in_wall_area_and_openings_deduct():
    m = {"shape_code": "RECTANGULAR", "length_mm": 3000, "width_mm": 3000, "ceiling_height_mm": 2800}
    out = d.derive(m, _walls(), "LIVING")
    assert out["derived_floor_area_sqft_centi"] == d.mm2_to_sqft_centi(9_000_000)
    assert out["derived_perimeter_mm"] == 9000  # the OPEN edge is in the perimeter (B1-SCOPE §2.9.2)
    gross = 3000 * 2800 + 3000 * 2500 + 1500 * 2800  # no OPEN edge; wall 2 uses its own height
    assert out["derived_wall_area_gross_sqft_centi"] == d.mm2_to_sqft_centi(gross)
    assert out["derived_wall_area_net_sqft_centi"] == d.mm2_to_sqft_centi(gross - 900 * 2100)  # non-deducting skipped


def test_freeform_uses_the_stated_area_and_staircase_walls_need_their_own_height():
    assert (
        d.derive({"shape_code": "FREEFORM", "stated_floor_area_sqft_centi": 4500}, [], "STORE")[
            "derived_floor_area_sqft_centi"
        ]
        == 4500
    )
    stair = {"shape_code": "RECTANGULAR", "ceiling_height_mm": 3000,
             "attributes": {"staircase": {"run_length_mm": 4000, "width_mm": 1000}}}  # fmt: skip
    walls = [{"wall_index": 1, "length_mm": 4000, "wall_type_code": "MASONRY", "openings": []}]
    out = d.derive(stair, walls, "STAIRCASE")
    assert out["derived_floor_area_sqft_centi"] == d.mm2_to_sqft_centi(4_000_000)  # run × width (B1-SCOPE §2.4)
    assert out["derived_wall_area_gross_sqft_centi"] is None  # never length × CH on a stair (AR-19)
    walls[0]["height_mm"] = 3600
    assert d.derive(stair, walls, "STAIRCASE")["derived_wall_area_gross_sqft_centi"] == d.mm2_to_sqft_centi(4000 * 3600)


def test_usable_segments():
    wall = {"length_mm": 4000, "openings": [{"offset_from_wall_start_mm": 1000, "width_mm": 900},
                                            {"offset_from_wall_start_mm": 3500, "width_mm": 800}]}  # fmt: skip
    assert d.usable_segments(wall) == [[0, 1000], [1900, 3500]]
    assert d.usable_segments({"length_mm": 3000, "openings": []}) == [[0, 3000]]
    assert d.usable_segments({"length_mm": 3000, "openings": [{"width_mm": 900}]}) == []  # unknown without offsets


@pytest.mark.parametrize(
    ("kind", "reference", "expected"),
    [
        ("wall", 6000, 25),
        ("wall", 6001, 50),  # closure §2.1: ±50 mm above 6 m
        ("ceiling", 2900, 25),
        ("opening_size", 900, 20),
        ("opening_position", 300, 25),
        ("staircase", 4000, 10),
        ("space_area", 25000, 250),  # ±1 %
        ("space_area", 2700, 108),  # ±0.1 m² floor for small rooms
        ("property_area", 120000, 1200),
    ],
)
def test_agreement_tolerances_are_the_recorded_values(kind, reference, expected):
    assert t.allowed(kind, reference) == expected


def test_compare_pass_explained_fail():
    assert t.compare("wall", 3000, 3020).verdict == "PASS"
    assert t.compare("wall", 3000, 3040).verdict == "FAIL"  # outside 25, no cause
    assert t.compare("wall", 3000, 3040, cause="tape sag").verdict == "EXPLAINED"
    assert t.compare("wall", 3000, 3060, cause="tape sag").verdict == "FAIL"  # beyond twice the tolerance


def test_site_and_gate_verdicts():
    good = [t.compare("wall", 3000, 3000)] * 40
    area = t.compare("property_area", 100000, 100500)
    assert t.site_verdict(good, [True] * 8, area) == "PASS"
    assert t.site_verdict(good + [t.compare("wall", 3000, 3100)], [True], area) == "FAIL"
    explained = [t.compare("wall", 3000, 3040, cause="reading position")] * 3
    assert t.site_verdict(good[:37] + explained, [True], area) == "FAIL"  # under 95 % PASS
    assert t.gate_verdict([(f"S{i}", "PASS", None) for i in range(9)]) == "INCOMPLETE"
    nine = [(f"S{i}", "PASS", None) for i in range(9)]
    assert t.gate_verdict(nine + [("S9", "FAIL", "laser drift")]) == "PASS"
    assert t.gate_verdict(nine + [("S9", "FAIL", None)]) == "FAIL"  # a failure without a root cause
    eight = [(f"S{i}", "PASS", None) for i in range(8)]
    assert t.gate_verdict(eight + [("S8", "FAIL", "x"), ("S9", "FAIL", "x")]) == "FAIL"
