"""MTQ B1-T08: electrical points, staircase and L-shape geometry, the door-less W1 convention (B1-SCOPE §2.4, §2.5,
§2.6, §2.9.1, §2.9.2; AR-02, AR-19)."""

from __future__ import annotations

import pytest

from tests.support.mtq import Site, bedroom_payload, photo
from veda.modules.mtq import capture, derivation, geometry, vocab

ON = pytest.mark.settings(mtq_site_enabled=True)


@pytest.fixture
def site(api, factory):
    s = Site(api, factory)
    s.open_set()
    return s


def add_space(site, type_code, label):
    return site.as_(site.sales).post(f"/api/v1/properties/{site.property['id']}/spaces",
                                     {"space_type_code": type_code, "label": label}).data  # fmt: skip


def version_of(site, space):
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    return next(sp["version"] for sp in tree["spaces"] if sp["space_id"] == space["id"])


def test_electrical_literal_equals_the_vocabulary():
    assert set(capture.ElectricalType.__args__) == set(vocab.ELECTRICAL_POINT_TYPES)


def test_l_shape_walls_and_vertices():
    legs = {"turn_code": "RIGHT", "leg_a": {"l_mm": 5000, "w_mm": 3000}, "leg_b": {"l_mm": 2000, "w_mm": 2500}}
    walls = geometry.l_shape_walls(legs)
    assert walls == [3000, 2500, 2000, 2500, 5000, 5000]
    assert sum(walls) == 2 * (5000 + 3000 + 2000)
    assert derivation.shoelace_mm2(geometry.l_shape_vertices(legs)) == 5000 * 3000 + 2000 * 2500
    left = {**legs, "turn_code": "LEFT"}
    assert derivation.shoelace_mm2(geometry.l_shape_vertices(left)) == 5000 * 3000 + 2000 * 2500


# --- electrical ----------------------------------------------------------------------------------------------------
@ON
@pytest.mark.parametrize(
    ("point", "fragment"),
    [
        ({"client_ref": "x", "point_type_code": "SENSOR_LIGHT", "location_code": "CEILING"}, "sensor"),
        (
            {
                "client_ref": "x",
                "point_type_code": "SOCKET_5A",
                "status_code": "SHIFT",
                "wall_index": 2,
                "from_offset_mm": 10,
            },
            "new position",
        ),
        ({"client_ref": "x", "point_type_code": "SOCKET_5A", "status_code": "NEW", "wall_index": 2}, "to_offset_mm"),
        (
            {"client_ref": "x", "point_type_code": "SOCKET_5A", "wall_index": 9, "from_offset_mm": 10},
            "not in this space",
        ),
        ({"client_ref": "x", "point_type_code": "LIGHT_POINT", "location_code": "CEILING", "wall_index": 2}, "no wall"),
        ({"client_ref": "x", "point_type_code": "SOCKET_5A", "wall_index": 2, "from_offset_mm": 9999}, "beyond"),
    ],
)
def test_electrical_points_are_validated(site, point, fragment):
    r = site.put(site.bedroom, bedroom_payload(electrical_points=[point]))
    assert r.status == 422 and fragment in str(r.json), r


@ON
def test_shift_sensor_points_keep_ids_counts_and_copy_into_revisions(site):
    points = bedroom_payload()["electrical_points"] + [
        {"client_ref": "ep-shift", "point_type_code": "SOCKET_5A", "status_code": "SHIFT", "wall_index": 2,
         "from_offset_mm": 800, "from_height_mm": 300, "to_wall_index": 3, "to_offset_mm": 400, "to_height_mm": 300,
         "reason_code": "FURNITURE_CLASH"},
        {"client_ref": "ep-sensor", "point_type_code": "SENSOR_LIGHT", "sensor_type_code": "PIR", "switching_code": "SENSOR",
         "wall_index": 1, "location_code": "FOYER_ENTRY", "from_offset_mm": 50, "quantity": 2},
    ]  # fmt: skip
    first = site.put(site.bedroom, bedroom_payload(electrical_points=points)).data
    shift = next(p for p in first["electrical_points"] if p["client_ref"] == "ep-shift")
    assert shift["wall_index"] == 2 and shift["to_wall_index"] == 3 and shift["status_code"] == "SHIFT"
    counts = {(c["point_type_code"], c["status_code"]): c["count"] for c in first["electrical_counts"]}
    assert counts[("SENSOR_LIGHT", "EXISTING")] == 2 and counts[("SOCKET_5A", "SHIFT")] == 1
    again = site.put(site.bedroom, bedroom_payload(electrical_points=points, base_version=first["version"])).data
    assert next(p for p in again["electrical_points"] if p["client_ref"] == "ep-shift")["id"] == shift["id"]
    fewer = site.put(site.bedroom, bedroom_payload(electrical_points=points[:-1], base_version=again["version"])).data
    assert "ep-sensor" not in {p["client_ref"] for p in fewer["electrical_points"]}
    # A photo of the existing point attaches to the point and counts toward the set.
    att = photo(site.as_(site.lead_surveyor), "space_electrical_point", shift["id"])
    assert att["entity_type"] == "space_electrical_point" and att["available"]


@ON
def test_full_rule_switchboards_on_furniture_walls_need_their_point(site):
    k, b = site.capture_full()
    assert site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/checks").data["ready_to_submit"]
    no_point = bedroom_payload(is_complete=True, electrical_points=[], base_version=b["version"])
    site.put(site.bedroom, no_point)
    problems = (
        site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/checks").data["submit_problems"]
    )
    assert "ELECTRICAL_POINT_MISSING" in {p["code"] for p in problems}


@ON
def test_points_travel_into_a_correction_revision(site):
    site.capture_full()
    assert site.submit().status == 200
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    correction = founder.post(f"/api/v1/measurement-sets/{site.set['id']}/reject", {"reason": "recheck"},
                              if_match=cur["version"]).data["correction"]  # fmt: skip
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{correction['id']}").data
    bed = next(sp for sp in tree["spaces"] if sp["space_id"] == site.bedroom["id"])
    sb = next(p for p in bed["electrical_points"] if p["client_ref"] == "ep-switchboard")
    assert sb["wall_index"] == 2  # re-linked to the copied wall
    wall2 = next(w for w in bed["walls"] if w["wall_index"] == 2)
    original = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    old_bed = next(sp for sp in original["spaces"] if sp["space_id"] == site.bedroom["id"])
    assert wall2["id"] != next(w for w in old_bed["walls"] if w["wall_index"] == 2)["id"]


# --- staircase -----------------------------------------------------------------------------------------------------
def stair_payload(**over):
    body = {
        "shape_code": "RECTANGULAR",
        "attributes": {"staircase": {
            "from_level": 0, "to_level": 1, "turn_type_code": "L", "flight_count": 2, "run_length_mm": 4200,
            "width_mm": 1000, "riser_count": 18, "riser_height_mm": 165, "tread_depth_mm": 270, "headroom_mm": 2150,
            "landing_l_mm": 1000, "landing_w_mm": 1000, "largest_panel_mm": 1100, "handrail_wall_index": 2}},
        "walls": [{"wall_index": i, "length_mm": 2100, "height_mm": 2600 + 400 * i, "usable_for_code": ["NONE"]}
                  for i in (1, 2, 3, 4)],
        "is_complete": True,
    }  # fmt: skip
    body.update(over)
    return body


@ON
def test_staircase_geometry_rules_and_derived_area(site):
    stair = add_space(site, "STAIRCASE", "Staircase")
    no_landing = stair_payload()
    no_landing["attributes"]["staircase"].pop("landing_l_mm")
    assert site.put(stair, no_landing).status == 422  # an L turn needs its landing
    on_bedroom = bedroom_payload(attributes={"staircase": stair_payload()["attributes"]["staircase"]})
    assert site.put(site.bedroom, on_bedroom).status == 422  # staircase geometry only on a staircase
    r = site.put(stair, stair_payload())
    assert r.status == 201, r
    assert r.data["derived_floor_area_sqft_centi"] == derivation.mm2_to_sqft_centi(4200 * 1000)
    assert r.data["derived_wall_area_gross_sqft_centi"] is not None  # per-segment heights
    flat = stair_payload(base_version=r.data["version"])
    flat["walls"][0].pop("height_mm")
    site.put(stair, flat)
    problems = (
        site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/checks").data["submit_problems"]
    )
    mine = {p["code"] for p in problems if p["pointer"].startswith(f"/spaces/{stair['id']}")}
    assert "WALL_HEIGHT_REQUIRED" in mine and "CEILING_HEIGHT_REQUIRED" not in mine
    assert "DIMENSIONS_REQUIRED" not in mine  # a staircase uses run and width, not L and W


@ON
def test_low_headroom_needs_a_risk_note_at_verification(site):
    stair = add_space(site, "STAIRCASE", "Staircase")
    low = stair_payload()
    low["attributes"]["staircase"]["headroom_mm"] = 1900
    site.capture_full()
    site.put(stair, low)
    photo(site.as_(site.lead_surveyor), "property_space", stair["id"])
    assert site.submit().status == 200
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    r = founder.post(f"/api/v1/measurement-sets/{site.set['id']}/verify", {}, if_match=cur["version"])
    assert r.status == 422 and "STAIRCASE_RISK_NOTE_REQUIRED" in {p["code"] for p in r.json["pointers"]}


# --- L-shape -------------------------------------------------------------------------------------------------------
def l_payload(walls, **over):
    body = {
        "shape_code": "L_SHAPE", "length_mm": 5000, "width_mm": 5000, "ceiling_height_mm": 2900,
        "attributes": {"l_shape": {"turn_code": "RIGHT", "leg_a": {"l_mm": 5000, "w_mm": 3000},
                                   "leg_b": {"l_mm": 2000, "w_mm": 2500}}},
        "walls": [{"wall_index": i + 1, "length_mm": n, "usable_for_code": ["NONE"] if i == 0 else []}
                  for i, n in enumerate(walls)],
        "is_complete": True,
    }  # fmt: skip
    body.update(over)
    return body


@ON
def test_l_shape_needs_legs_and_closes_within_50_mm(site):
    living = add_space(site, "LIVING_DINING", "Living and dining")
    no_legs = l_payload(geometry.l_shape_walls(l_payload([])["attributes"]["l_shape"]))
    no_legs["attributes"] = {}
    assert site.put(living, no_legs).status == 422  # a complete L needs its legs
    good = l_payload([3000, 2500, 2000, 2500, 5000, 5000])
    r = site.put(living, good)
    assert r.status == 201
    assert r.data["derived_floor_area_sqft_centi"] == derivation.mm2_to_sqft_centi(5000 * 3000 + 2000 * 2500)
    assert r.data["derived_perimeter_mm"] == 20000
    from veda.kernel import db
    from veda.modules.mtq import sets as mtq_sets
    from veda.modules.mtq import verification
    from veda.modules.mtq.models import MeasurementSet, PropertySpace

    with db.unit_of_work(write=False) as s:
        sp = s.get(PropertySpace, living["id"])
        sm = verification.measurements(s, s.get(MeasurementSet, site.set["id"]))[living["id"]]
        data = mtq_sets.present_measurement(s, sm)
        assert geometry._l_shape_problems(sp, data, "FULL", "verify") == []
        data["walls"][2]["length_mm"] = 2100  # 100 mm off
        assert [p["code"] for p in geometry._l_shape_problems(sp, data, "FULL", "verify")] == ["L_SHAPE_NOT_CLOSED"]


# --- door-less W1, partitions, niches ------------------------------------------------------------------------------
@ON
def test_doorless_open_edge_is_wall_zero_and_counts_in_perimeter_only(site):
    living = add_space(site, "LIVING", "Living")
    bad = {"length_mm": 4000, "width_mm": 3000, "ceiling_height_mm": 2900,
           "walls": [{"wall_index": 0, "length_mm": 1500, "wall_type_code": "MASONRY"}]}  # fmt: skip
    assert site.put(living, bad).status == 422
    ok = {"length_mm": 4000, "width_mm": 3000, "ceiling_height_mm": 2900, "walls": [
        {"wall_index": 0, "length_mm": 1500, "wall_type_code": "OPEN"},
        {"wall_index": 1, "length_mm": 2500, "usable_for_code": ["TV_UNIT"]},
        {"wall_index": 2, "length_mm": 4000}, {"wall_index": 3, "length_mm": 3000}, {"wall_index": 4, "length_mm": 4000}]}  # fmt: skip
    r = site.put(living, ok)
    assert r.status == 201 and r.data["derived_perimeter_mm"] == 15000
    assert r.data["derived_wall_area_gross_sqft_centi"] == derivation.mm2_to_sqft_centi(
        (2500 + 4000 + 3000 + 4000) * 2900
    )


@ON
def test_proposed_partition_and_fridge_niche_are_stored(site):
    k = site.put(site.kitchen, {
        "length_mm": 3600, "width_mm": 2700, "ceiling_height_mm": 2900, "floor_to_lintel_mm": 2100,
        "walls": [
            {"wall_index": 1, "length_mm": 2700, "wall_type_code": "PARTITION", "is_proposed": True},
            {"wall_index": 2, "length_mm": 3600, "usable_for_code": ["KITCHEN_RUN", "TALL_UNIT"], "openings": [
                {"client_ref": "niche-fridge", "opening_type_code": "NICHE", "purpose_code": "FRIDGE", "width_mm": 800,
                 "height_mm": 1900, "depth_mm": 700, "sill_height_mm": 0, "offset_from_wall_start_mm": 2700,
                 "deducts_from_wall_area": True}]},
        ],
    })  # fmt: skip
    assert k.status == 201, k
    w1 = next(w for w in k.data["walls"] if w["wall_index"] == 1)
    niche = next(w for w in k.data["walls"] if w["wall_index"] == 2)["openings"][0]
    assert w1["is_proposed"] is True and niche["purpose_code"] == "FRIDGE" and niche["depth_mm"] == 700
