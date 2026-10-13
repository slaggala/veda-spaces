"""MTQ B1-T07: Lite and Full capture rules, fail-closed verification, sealing and supersession (blueprint §6.2;
B1-SCOPE §2.3; blocker closure §2.3 and AR rows)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from tests.support.mtq import FULL_CAPTURE, Site, bedroom_payload, kitchen_payload, photo
from veda.kernel import db
from veda.modules.mtq import verification
from veda.modules.mtq.models import MeasurementNote, MeasurementSet, Property

ON = pytest.mark.settings(mtq_site_enabled=True)


@pytest.fixture
def site(api, factory):
    return Site(api, factory)


def codes(resp) -> set[str]:
    return {p["code"] for p in resp.json["pointers"]}


def checks(site, user=None):
    return site.as_(user or site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/checks").data


def verify(site, user, acks=None):
    api = site.as_(user)
    cur = api.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    return api.post(f"/api/v1/measurement-sets/{site.set['id']}/verify", {"acknowledgements": acks or []},
                    if_match=cur["version"])  # fmt: skip


@ON
def test_lite_needs_dimensions_ceiling_photo_and_the_complete_mark(api, factory):
    site = Site(api, factory, level="LITE")
    site.open_set()
    assert site.set["survey_level_code"] == "LITE"
    site.put(site.kitchen, {"length_mm": 3600, "width_mm": 2700, "is_complete": True})
    site.put(site.bedroom, {"length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900})
    r = site.submit()
    assert r.status == 422 and {"CEILING_HEIGHT_REQUIRED", "OVERVIEW_PHOTO_REQUIRED", "NOT_COMPLETE"} <= codes(r)
    assert "NO_TAGGED_WALL" not in codes(r) and "WALLS_REQUIRED" not in codes(r)  # Full-only rules
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    v = {sp["space_id"]: sp["version"] for sp in tree["spaces"]}
    site.put(site.kitchen, {"length_mm": 3600, "width_mm": 2700, "ceiling_height_mm": 2900, "is_complete": True,
                            "base_version": v[site.kitchen["id"]]})  # fmt: skip
    site.put(site.bedroom, {"length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900, "is_complete": True,
                            "base_version": v[site.bedroom["id"]]})  # fmt: skip
    site.overview_photos()
    assert site.submit().status == 200


@ON
def test_outdoor_spaces_need_no_ceiling_height(api, factory):
    site = Site(api, factory, level="LITE")
    site.as_(site.sales)
    terrace = api.post(f"/api/v1/properties/{site.property['id']}/spaces",
                       {"space_type_code": "TERRACE", "label": "Terrace"}).data  # fmt: skip
    assert terrace["zone_code"] == "OUTDOOR"
    site.open_set()
    site.put(terrace, {"length_mm": 5000, "width_mm": 4000, "is_complete": True})
    pointers = checks(site)["submit_problems"]
    assert not [
        p for p in pointers if p["pointer"] == f"/spaces/{terrace['id']}" and p["code"] == "CEILING_HEIGHT_REQUIRED"
    ]


@ON
def test_full_rules_one_by_one(site):
    site.open_set()
    bare = bedroom_payload(is_complete=True, floor_to_lintel_mm=None, attributes={}, walls=[
        {"wall_index": 1, "length_mm": 3000, "openings": [{"client_ref": "d", "opening_type_code": "DOOR",
                                                           "width_mm": 900, "height_mm": 2100}]},
        {"wall_index": 2, "length_mm": 3300, "usable_for_code": ["WARDROBE"]},
    ])  # fmt: skip
    site.put(site.bedroom, bare)
    k = kitchen_payload(is_complete=True, flooring_code=None)
    k["walls"][1]["obstructions"] = [{"kind": "SWITCHBOARD", "offset_mm": 100}]  # no PIPE on the kitchen run
    k["walls"][1]["openings"][0]["sill_height_mm"] = None
    site.put(site.kitchen, k)
    r = site.submit()
    got = codes(r)
    for code in ("WALLS_REQUIRED", "OBSTRUCTIONS_REQUIRED", "WALL_PHOTO_REQUIRED", "OPENING_OFFSET_REQUIRED",
                 "OPENING_SWING_REQUIRED", "FLOOR_TO_LINTEL_REQUIRED", "ATTRIBUTE_REQUIRED", "FLOORING_REQUIRED",
                 "OBSTRUCTION_KIND_REQUIRED", "SILL_REQUIRED", "OVERVIEW_PHOTO_REQUIRED"):  # fmt: skip
        assert code in got, (code, got)
    assert all(p["pointer"].startswith("/spaces/") for p in r.json["pointers"])


@ON
def test_tag_rules_and_none_marker(site):
    site.open_set()
    no_tags = bedroom_payload(is_complete=True)
    for w in no_tags["walls"]:
        w["usable_for_code"] = []
        w["obstructions"] = []
    site.put(site.bedroom, no_tags)
    pointers = checks(site)["submit_problems"]
    mine = {p["code"] for p in pointers if p["pointer"].startswith(f"/spaces/{site.bedroom['id']}")}
    assert {"NO_TAGGED_WALL", "TAG_REQUIRED"} <= mine
    marker = bedroom_payload(is_complete=True)
    marker["walls"][1]["obstructions"] = [{"kind": "NONE"}]  # explicit "nothing on this furniture wall"
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    marker["base_version"] = tree["spaces"][0]["version"]
    assert site.put(site.bedroom, marker).status == 200
    mine = {
        p["code"] for p in checks(site)["submit_problems"] if p["pointer"].startswith(f"/spaces/{site.bedroom['id']}")
    }
    assert "OBSTRUCTIONS_REQUIRED" not in mine and "NO_TAGGED_WALL" not in mine


@ON
def test_derived_values_are_stored_on_write(site):
    site.open_set()
    k = site.put(site.kitchen, kitchen_payload()).data
    assert k["derived_floor_area_sqft_centi"] == 10463 and k["derived_perimeter_mm"] == 12600
    assert k["derived_wall_area_net_sqft_centi"] < k["derived_wall_area_gross_sqft_centi"]
    segments = checks(site)["usable_segments"][site.kitchen["id"]]
    assert segments["2"] == [[0, 1500], [2700, 3600]]  # the window on the kitchen run


@ON
def test_verify_happy_path_seals_and_updates_the_property(site):
    site.open_set()
    site.capture_full()
    assert site.submit().status == 200
    ready = checks(site, site.founder)
    assert ready["ready_to_verify"] is True, ready["verify_problems"]
    r = verify(site, site.founder)
    assert r.status == 200, r
    assert (
        r.data["status"] == "VERIFIED"
        and len(r.data["snapshot_sha256"]) == 64
        and r.data["verified_by"] == site.founder.id
    )
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, site.set["id"])
        assert verification.snapshot_sha256(s, mset) == mset.snapshot_sha256  # reproducible, tamper evident
        prop = s.get(Property, site.property["id"])
        assert prop.derived_measured_floor_area_sqft_centi == mset.summary["total_floor_area_sqft_centi"] > 0
    summary = site.as_(site.sales).get(f"/api/v1/properties/{site.property['id']}/summary").data
    assert summary["latest_verified_set"]["id"] == site.set["id"]
    assert verify(site, site.founder).status == 409  # already verified


@ON
def test_four_eyes_for_verification(api, factory):
    site = Site(api, factory)
    site.as_(site.founder)
    plan = api.post(f"/api/v1/properties/{site.property['id']}/measurement-sets", {}).data
    site.set = plan
    site.put(site.kitchen, kitchen_payload(is_complete=True), user=site.founder)
    site.put(site.bedroom, bedroom_payload(is_complete=True), user=site.founder)
    site.overview_photos(site.founder)
    cur = api.get(f"/api/v1/measurement-sets/{plan['id']}").data
    api.patch(f"/api/v1/measurement-sets/{plan['id']}", {"property_capture": {"floor_number": 2, "lift_available": False}},
              if_match=cur["version"])  # fmt: skip
    assert site.submit(user=site.founder).status == 200
    r = verify(site, site.founder)
    assert r.status == 422 and "FOUR_EYES_REQUIRED" in codes(r)


@ON
def test_attachments_must_be_clean_before_verification(site):
    site.open_set()
    site.capture_full()
    photo(site.as_(site.lead_surveyor), "measurement_set", site.set["id"], complete=False)  # still uploading
    assert site.submit().status == 200  # uploads may still drain at submission (B1-SCOPE §2.8)
    r = verify(site, site.founder)
    assert r.status == 422 and "ATTACHMENTS_NOT_CLEAN" in codes(r)


@ON
def test_geometry_and_unit_plausibility_fail_closed(site):
    site.open_set()
    site.capture_full()
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    v = {sp["space_id"]: sp["version"] for sp in tree["spaces"]}
    bad = kitchen_payload(is_complete=True, ceiling_height_mm=290, base_version=v[site.kitchen["id"]])  # cm, not mm
    bad["walls"][1]["openings"][0]["offset_from_wall_start_mm"] = 3000  # 3000 + 1200 > 3600
    assert site.put(site.kitchen, bad).status == 200
    k = tree["spaces"]
    assert k
    assert site.submit().status == 200
    r = verify(site, site.founder)
    assert r.status == 422 and {"IMPLAUSIBLE_CEILING_HEIGHT", "OPENING_EXCEEDS_WALL"} <= codes(r)


@ON
def test_built_up_deviation_needs_an_acknowledgement(site):
    site.as_(site.sales)
    p = site.api.get(f"/api/v1/properties/{site.property['id']}").data
    site.api.patch(f"/api/v1/properties/{p['id']}", {"built_up_area_sqft_centi": 100_00}, if_match=p["version"])
    site.open_set()
    site.capture_full()
    assert site.submit().status == 200
    r = verify(site, site.founder)
    assert r.status == 422 and "BUILT_UP_DEVIATION" in codes(r)
    ok = verify(site, site.founder, [{"code": "BUILT_UP_DEVIATION", "note": "Stated area excludes the balcony"}])
    assert ok.status == 200 and ok.data["status"] == "VERIFIED"
    with db.unit_of_work(write=False) as s:
        acks = s.execute(sa.select(MeasurementNote).where(MeasurementNote.measurement_set_id == site.set["id"],
                                                          MeasurementNote.note_type_code == "RISK_ACK")).scalars().all()  # fmt: skip
        assert len(acks) == 1 and acks[0].created_by == site.founder.id and "balcony" in acks[0].body


@ON
def test_full_property_capture_is_required_at_verification(site):
    site.open_set()
    site.capture_full()
    api = site.as_(site.lead_surveyor)
    cur = api.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    partial = {k: v for k, v in FULL_CAPTURE.items() if k != "db_location"}
    api.patch(f"/api/v1/measurement-sets/{site.set['id']}", {"property_capture": partial}, if_match=cur["version"])
    assert site.submit().status == 200
    r = verify(site, site.founder)
    assert r.status == 422 and "PROPERTY_CAPTURE_REQUIRED" in codes(r)


@ON
def test_a_second_verified_revision_supersedes_the_first(site):
    site.open_set()
    site.capture_full()
    site.submit()
    assert verify(site, site.founder).status == 200
    first = site.set
    visit = site.visits[site.lead_surveyor.id]
    api = site.as_(site.lead_surveyor)
    # A re-measure on the same visit (still in progress) copies the verified revision into a new draft.
    r = api.post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets", {"copy_from_set_id": first["id"]})
    assert r.status == 201 and r.data["revision_no"] == 2 and r.data["supersedes_set_id"] == first["id"]
    site.set = r.data
    site.capture_full()
    assert site.submit().status == 200
    assert verify(site, site.founder).status == 200
    with db.unit_of_work(write=False) as s:
        statuses = dict(s.execute(sa.select(MeasurementSet.revision_no, MeasurementSet.status)
                                  .where(MeasurementSet.property_id == site.property["id"])).all())  # fmt: skip
    assert statuses == {1: "SUPERSEDED", 2: "VERIFIED"}


def test_b1_creates_no_boq_pricing_or_quotation_tables(app):
    with db.engine().connect() as conn:
        names = set(sa.inspect(conn).get_table_names())
    for deferred in ("scope", "scope_item", "boq", "boq_line", "cost_estimate", "quotation", "requirement"):
        assert deferred not in names
