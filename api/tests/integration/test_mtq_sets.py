"""MTQ B1-T06: measurement sets, revisions, per-space claims and explicit conflicts (blueprint §6.2; B1-SCOPE
§2.3, §2.7, §2.9.3)."""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa

from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.mtq.models import MeasurementSet, SpaceWall

ON = pytest.mark.settings(mtq_site_enabled=True)


class Site:
    """A property with two in-scope spaces (kitchen, bedroom), a visit in progress and a draft set."""

    def __init__(self, api, factory):
        self.api, self.factory = api, factory
        self.sales = factory.user("SALES")
        self.lead_surveyor = factory.user("SURVEYOR")
        self.second = factory.user("SURVEYOR")
        self.third = factory.user("SURVEYOR")
        self.founder = factory.user(founder=True)
        factory.login(api, self.sales)
        self.lead = api.post(
            "/api/v1/leads", {"name": "Ravi K", "phone": "+91 90000 44444", "source_code": "PHONE"}
        ).data
        self.property = api.post(
            "/api/v1/properties", {"lead_id": self.lead["id"], "property_type_code": "APARTMENT"}
        ).data
        pid = self.property["id"]
        self.kitchen = api.post(
            f"/api/v1/properties/{pid}/spaces", {"space_type_code": "KITCHEN", "label": "Kitchen"}
        ).data
        self.bedroom = api.post(
            f"/api/v1/properties/{pid}/spaces", {"space_type_code": "BEDROOM", "label": "Bedroom"}
        ).data
        self.visits = {}
        for who in (self.lead_surveyor, self.second, self.third):
            v = api.post("/api/v1/measurement-visits", {"property_id": pid, "assigned_to": who.id,
                                                        "scheduled_start_on": clock.to_rfc3339(clock.now() + timedelta(hours=1))}).data  # fmt: skip
            self.visits[who.id] = v

    def as_(self, user):
        self.factory.login(self.api, user)
        return self.api

    def start(self, user):
        v = self.visits[user.id]
        r = self.as_(user).post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "IN_PROGRESS"},
                                if_match=v["version"])  # fmt: skip
        assert r.status == 200, r
        self.visits[user.id] = r.data
        return r.data

    def open_set(self, **body):
        self.start(self.lead_surveyor)
        r = self.as_(self.lead_surveyor).post(
            f"/api/v1/measurement-visits/{self.visits[self.lead_surveyor.id]['id']}/measurement-sets", body
        )
        assert r.status == 201, r
        self.set = r.data
        return r.data


def kitchen_payload(**over):
    body = {
        "client_ref": "sm-kitchen",
        "shape_code": "RECTANGULAR",
        "length_mm": 3600,
        "width_mm": 2700,
        "ceiling_height_mm": 2900,
        "floor_to_lintel_mm": 2100,
        "flooring_code": "VITRIFIED",
        "existing_condition_code": "BARE_SHELL",
        "attributes": {"has_gas_line": True, "has_water_inlet": True, "has_drain": True, "counter_existing": False},
        "walls": [
            {"wall_index": 1, "length_mm": 2700, "usable_for_code": ["NONE"],
             "openings": [{"client_ref": "op-door", "opening_type_code": "DOOR", "width_mm": 900, "height_mm": 2100,
                           "offset_from_wall_start_mm": 300, "swing_code": "IN"}]},
            {"wall_index": 2, "length_mm": 3600, "usable_for_code": ["KITCHEN_RUN"],
             "obstructions": [{"kind": "PIPE", "offset_mm": 1200, "width_mm": 50}],
             "openings": [{"client_ref": "op-window", "opening_type_code": "WINDOW", "width_mm": 1200,
                           "height_mm": 1200, "sill_height_mm": 1050, "offset_from_wall_start_mm": 1500,
                           "swing_code": "SLIDING"}]},
            {"wall_index": 3, "length_mm": 2700},
            {"wall_index": 4, "length_mm": 3600},
        ],
    }  # fmt: skip
    body.update(over)
    return body


@pytest.fixture
def site(api, factory):
    return Site(api, factory)


def put(api, mset, space, body):
    return api.put(f"/api/v1/measurement-sets/{mset['id']}/spaces/{space['id']}", body)


def test_set_routes_are_404_while_the_flag_is_off(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    zero = "0" * 32
    assert api.get(f"/api/v1/measurement-sets/{zero}").status == 404
    assert api.put(f"/api/v1/measurement-sets/{zero}/spaces/{zero}", {}).status == 404


@ON
def test_draft_needs_a_started_visit_its_assignee_and_is_unique(site):
    v = site.visits[site.lead_surveyor.id]
    api = site.as_(site.lead_surveyor)
    assert api.post(f"/api/v1/measurement-visits/{v['id']}/measurement-sets", {}).status == 409  # not started
    site.start(site.lead_surveyor)
    other = site.as_(site.second)
    assert other.post(f"/api/v1/measurement-visits/{v['id']}/measurement-sets", {}).status == 403  # not theirs
    api = site.as_(site.lead_surveyor)
    r = api.post(f"/api/v1/measurement-visits/{v['id']}/measurement-sets", {"unit_system_code": "MM"})
    assert r.status == 201 and r.data["status"] == "DRAFT" and r.data["revision_no"] == 1
    assert r.data["survey_level_code"] == "FULL"  # the visit's planned level
    again = api.post(f"/api/v1/measurement-visits/{v['id']}/measurement-sets", {})
    assert again.status == 409 and again.code == "DRAFT_EXISTS"


@ON
def test_capture_keeps_wall_and_opening_ids_and_refuses_stale_writes(site):
    mset = site.open_set()
    api = site.as_(site.lead_surveyor)
    first = put(api, mset, site.kitchen, kitchen_payload())
    assert first.status == 201, first
    sm = first.data
    wall2 = next(w for w in sm["walls"] if w["wall_index"] == 2)
    window = wall2["openings"][0]
    assert put(api, mset, site.kitchen, kitchen_payload()).status == 428  # base_version required now
    edited = kitchen_payload(base_version=sm["version"], length_mm=3610)
    second = put(api, mset, site.kitchen, edited)
    assert second.status == 200 and second.data["length_mm"] == 3610
    wall2_again = next(w for w in second.data["walls"] if w["wall_index"] == 2)
    assert wall2_again["id"] == wall2["id"] and wall2_again["openings"][0]["id"] == window["id"]
    stale = put(api, mset, site.kitchen, kitchen_payload(base_version=sm["version"], width_mm=2650))
    assert stale.status == 409 and stale.code == "VERSION_CONFLICT"
    assert "width_mm" in stale.json["conflicting_fields"] and "length_mm" in stale.json["conflicting_fields"]
    assert stale.json["server"]["length_mm"] == 3610  # the client sees the server state to resolve explicitly
    fewer = kitchen_payload(base_version=second.data["version"], walls=kitchen_payload()["walls"][:3])
    third = put(api, mset, site.kitchen, fewer)
    assert [w["wall_index"] for w in third.data["walls"]] == [1, 2, 3]
    with db.unit_of_work(write=False) as s:
        gone = s.execute(
            sa.select(SpaceWall).where(SpaceWall.space_measurement_id == sm["id"], SpaceWall.wall_index == 4)
            .execution_options(include_deleted=True)
        ).scalar_one()  # fmt: skip
        assert gone.is_deleted


@ON
@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"shape_code": "FREEFORM"}, "stated area"),
        ({"shape_code": "POLYGON"}, "vertices"),
        ({"walls": [{"wall_index": 1, "length_mm": 1000}, {"wall_index": 1, "length_mm": 1200}]}, "repeat"),
        ({"walls": [{"wall_index": 1, "length_mm": 1000, "usable_for_code": ["NONE", "WARDROBE"]}]}, "NONE"),
        ({"walls": [{"wall_index": 1, "length_mm": 1000, "is_proposed": True}]}, "partition"),
        (
            {
                "walls": [
                    {
                        "wall_index": 1,
                        "length_mm": 1000,
                        "openings": [
                            {"client_ref": "n1", "opening_type_code": "NICHE", "width_mm": 700, "height_mm": 1800}
                        ],
                    }
                ]
            },
            "depth",
        ),
        ({"walls": [{"wall_index": 1, "length_mm": 0}]}, "greater"),
        ({"attributes": {"colour": "blue"}}, "UNKNOWN_FIELD"),
        ({"walls": [{"wall_index": 1, "length_mm": 1000, "obstructions": [{"kind": "PIPE"}]}]}, "offset"),
    ],
)
def test_capture_payloads_are_closed_and_bounded(site, override, fragment):
    mset = site.open_set()
    r = put(site.as_(site.lead_surveyor), mset, site.kitchen, kitchen_payload(**override))
    assert r.status == 422, r
    assert fragment.lower() in str(r.json).lower()


@ON
def test_two_surveyors_claims_release_takeover_and_explicit_conflicts(site):
    mset = site.open_set()
    site.start(site.second)
    site.start(site.third)
    b = site.as_(site.second)
    bed = {"client_ref": "sm-bed", "length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900,
           "walls": [{"wall_index": i, "length_mm": 3000 + (i % 2) * 300} for i in range(1, 5)]}  # fmt: skip
    r = put(b, mset, site.bedroom, bed)
    assert r.status == 201 and r.data["captured_by"] == site.second.id and r.data["claim_expires_on"]
    v1 = r.data["version"]
    c = site.as_(site.third)
    claimed = put(c, mset, site.bedroom, {**bed, "base_version": v1})
    assert claimed.status == 409 and claimed.code == "SPACE_CLAIMED" and claimed.json["claimed_by"] == site.second.id
    # Same field changed differently by the lead surveyor and the claim holder: never last-write-wins.
    lead = site.as_(site.lead_surveyor)
    assert put(lead, mset, site.bedroom, {**bed, "base_version": v1, "length_mm": 3310}).status == 200
    b = site.as_(site.second)
    conflict = put(b, mset, site.bedroom, {**bed, "base_version": v1, "length_mm": 3290})
    assert conflict.status == 409 and conflict.code == "VERSION_CONFLICT"
    assert conflict.json["conflicting_fields"] == ["length_mm"] and conflict.json["server"]["length_mm"] == 3310
    resolved = put(b, mset, site.bedroom, {**bed, "base_version": conflict.json["current_version"], "length_mm": 3290})
    assert resolved.status == 200 and resolved.data["length_mm"] == 3290  # resolved explicitly, on the new base
    released = b.post(f"/api/v1/measurement-sets/{mset['id']}/spaces/{site.bedroom['id']}/release")
    assert released.status == 200
    c = site.as_(site.third)
    current = released.data["version"]
    no_takeover = put(c, mset, site.bedroom, {**bed, "base_version": current})
    assert no_takeover.status == 409 and no_takeover.code == "CLAIM_TAKE_OVER_REQUIRED"
    taken = put(c, mset, site.bedroom, {**bed, "base_version": current, "take_over": True})
    assert taken.status == 200 and taken.data["captured_by"] == site.third.id
    clock.advance(timedelta(hours=5))  # claims lapse after four hours without a write
    b = site.as_(site.second)
    lapsed = put(b, mset, site.bedroom, {**bed, "base_version": taken.data["version"], "take_over": True})
    assert lapsed.status == 200 and lapsed.data["captured_by"] == site.second.id


@ON
def test_notes_are_idempotent_and_risk_acks_belong_to_verification(site):
    mset = site.open_set()
    api = site.as_(site.lead_surveyor)
    body = {"client_ref": "note-1", "space_id": site.kitchen["id"], "note_type_code": "CUSTOMER_REQUEST",
            "body": "Fridge on the left"}  # fmt: skip
    first = api.post(f"/api/v1/measurement-sets/{mset['id']}/notes", body)
    again = api.post(f"/api/v1/measurement-sets/{mset['id']}/notes", body)
    assert first.status == 201 and again.status == 200 and again.data["id"] == first.data["id"]
    assert api.post(f"/api/v1/measurement-sets/{mset['id']}/notes", {**body, "body": "other"}).status == 409
    ack = api.post(f"/api/v1/measurement-sets/{mset['id']}/notes", {"note_type_code": "RISK_ACK", "body": "ok"})
    assert ack.status == 422


def _complete_both(site, mset):
    api = site.as_(site.lead_surveyor)
    k = put(api, mset, site.kitchen, kitchen_payload(is_complete=True)).data
    bed = {"length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900, "is_complete": True,
           "walls": [{"wall_index": i, "length_mm": 3000 + (i % 2) * 300} for i in range(1, 5)]}  # fmt: skip
    b = put(api, mset, site.bedroom, bed).data
    return k, b


@ON
def test_submit_freezes_the_revision(site):
    mset = site.open_set()
    api = site.as_(site.lead_surveyor)
    put(api, mset, site.kitchen, kitchen_payload(is_complete=True))
    fresh = api.get(f"/api/v1/measurement-sets/{mset['id']}").data
    incomplete = api.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=fresh["version"])
    assert incomplete.status == 422 and incomplete.code == "MEASUREMENT_INCOMPLETE"
    assert [p["code"] for p in incomplete.json["pointers"]] == ["NOT_MEASURED"]
    _complete_both(site, mset)
    site.start(site.second)
    second = site.as_(site.second)
    fresh = second.get(f"/api/v1/measurement-sets/{mset['id']}").data
    assert second.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=fresh["version"]).status == 403
    api = site.as_(site.lead_surveyor)
    done = api.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=fresh["version"])
    assert done.status == 200 and done.data["status"] == "SUBMITTED" and done.data["summary"]["spaces"] == 2
    frozen = put(api, mset, site.kitchen, kitchen_payload(base_version=1))
    assert frozen.status == 409 and frozen.code == "SET_FROZEN"
    # Both visits that worked on the shared draft can now complete (B1-SCOPE §2.9.3).
    for who in (site.lead_surveyor, site.second):
        v = site.visits[who.id]
        r = site.as_(who).post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "COMPLETED"},
                               if_match=v["version"])  # fmt: skip
        assert r.status == 200, r


@ON
def test_return_for_correction_opens_a_copied_revision_and_diff_is_keyed_by_space(site):
    mset = site.open_set()
    _complete_both(site, mset)
    api = site.as_(site.lead_surveyor)
    fresh = api.get(f"/api/v1/measurement-sets/{mset['id']}").data
    api.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=fresh["version"])
    submitted = api.get(f"/api/v1/measurement-sets/{mset['id']}").data
    assert (
        api.post(f"/api/v1/measurement-sets/{mset['id']}/reject", {"reason": "x"}, if_match=submitted["version"]).status
        == 403
    )  # fmt: skip  (a surveyor does not verify)
    founder = site.as_(site.founder)
    r = founder.post(f"/api/v1/measurement-sets/{mset['id']}/reject", {"reason": "Kitchen wall 3 missing a window"},
                     if_match=submitted["version"])  # fmt: skip
    assert r.status == 200, r
    assert r.data["rejected"]["status"] == "REJECTED" and r.data["correction"]["status"] == "DRAFT"
    correction = r.data["correction"]
    assert correction["revision_no"] == 2 and correction["captured_by"] == site.lead_surveyor.id
    api = site.as_(site.lead_surveyor)
    tree = api.get(f"/api/v1/measurement-sets/{correction['id']}").data
    kitchen = next(sp for sp in tree["spaces"] if sp["space_id"] == site.kitchen["id"])
    assert kitchen["length_mm"] == 3600 and len(kitchen["walls"]) == 4  # copied
    edit = put(api, correction, site.kitchen, kitchen_payload(base_version=kitchen["version"], length_mm=3650,
                                                              is_complete=True))  # fmt: skip
    assert edit.status == 200
    d = api.get(f"/api/v1/measurement-sets/{mset['id']}/diff/{correction['id']}").data
    assert d["from_revision"] == 1 and d["to_revision"] == 2
    change = next(x for x in d["spaces"] if x["space_id"] == site.kitchen["id"])
    assert change["fields"]["length_mm"] == {"from": 3600, "to": 3650}
    original = api.get(f"/api/v1/measurement-sets/{mset['id']}").data
    assert next(sp for sp in original["spaces"] if sp["space_id"] == site.kitchen["id"])["length_mm"] == 3600


@ON
def test_four_eyes_on_return_for_correction(site):
    site.as_(site.founder)
    pid = site.property["id"]
    plan = site.api.post(f"/api/v1/properties/{pid}/measurement-sets", {})
    assert (
        plan.status == 201 and plan.data["method_code"] == "PLAN_DRAWING" and plan.data["survey_level_code"] == "LITE"
    )
    assert plan.data["measurement_visit_id"] is None
    _complete_both_as(site, site.founder, plan.data)
    fresh = site.api.get(f"/api/v1/measurement-sets/{plan.data['id']}").data
    sub = site.api.post(f"/api/v1/measurement-sets/{plan.data['id']}/submit", if_match=fresh["version"]).data
    own = site.api.post(f"/api/v1/measurement-sets/{plan.data['id']}/reject", {"reason": "x"}, if_match=sub["version"])
    assert own.status == 403 and own.code == "FOUR_EYES_REQUIRED"


def _complete_both_as(site, user, mset):
    api = site.as_(user)
    put(api, mset, site.kitchen, kitchen_payload(is_complete=True))
    bed = {"length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900, "is_complete": True,
           "walls": [{"wall_index": i, "length_mm": 3000} for i in range(1, 5)]}  # fmt: skip
    put(api, mset, site.bedroom, bed)


@ON
def test_lite_never_supersedes_a_verified_full_set(site):
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        now = db.tx_time(s)
        s.add(MeasurementSet(property_id=site.property["id"], revision_no=1, status="VERIFIED", survey_level_code="FULL",
                             method_code="LASER", unit_system_code="MM", captured_by=site.lead_surveyor.id,
                             submitted_on=now, verified_on=now, verified_by=site.founder.id,
                             snapshot_sha256="a" * 64))  # fmt: skip
    site.as_(site.founder)
    r = site.api.post(f"/api/v1/properties/{site.property['id']}/measurement-sets", {})
    assert r.status == 422 and r.code == "LITE_AFTER_FULL"
    site.start(site.lead_surveyor)
    api = site.as_(site.lead_surveyor)
    full = api.post(f"/api/v1/measurement-visits/{site.visits[site.lead_surveyor.id]['id']}/measurement-sets", {})
    assert full.status == 201 and full.data["revision_no"] == 2 and full.data["supersedes_set_id"]


@ON
def test_wall_photos_follow_the_set_and_freeze_with_it(site):
    import base64
    import hashlib
    import io

    from PIL import Image

    mset = site.open_set()
    api = site.as_(site.lead_surveyor)
    sm = put(api, mset, site.kitchen, kitchen_payload(is_complete=True)).data
    wall = next(w for w in sm["walls"] if w["wall_index"] == 2)
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (1, 2, 3)).save(buf, "JPEG")
    data = buf.getvalue()
    decl = {"entity_type": "space_wall", "entity_id": wall["id"], "mime_type": "image/jpeg", "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(), "category_code": "LASER_READING"}  # fmt: skip
    r = api.post("/api/v1/attachments", decl)
    assert r.status == 201
    api.put(f"/api/v1/attachments/{r.data['id']}/content", {"data_base64": base64.b64encode(data).decode()})
    assert api.post(f"/api/v1/attachments/{r.data['id']}/complete").data["available"]
    bed = {"length_mm": 3300, "width_mm": 3000, "ceiling_height_mm": 2900, "is_complete": True,
           "walls": [{"wall_index": i, "length_mm": 3000} for i in range(1, 5)]}  # fmt: skip
    put(api, mset, site.bedroom, bed)
    fresh = api.get(f"/api/v1/measurement-sets/{mset['id']}").data
    api.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=fresh["version"])
    late = api.post("/api/v1/attachments", {**decl, "sha256": "b" * 64})
    assert late.status == 409 and late.code == "ENTITY_FROZEN"
    att = api.get(f"/api/v1/attachments/{r.data['id']}").data
    withdraw = api.post(f"/api/v1/attachments/{r.data['id']}/withdraw", {}, if_match=att["version"])
    assert withdraw.status == 403  # a submitted set's photo is withdrawn only by a verifier, with a reason


def test_capture_literals_equal_the_frozen_vocabularies():
    from veda.modules.mtq import capture, vocab

    assert set(capture.WallTag.__args__) == set(vocab.WALL_TAGS)
    assert set(capture.ObstructionKind.__args__) == set(vocab.OBSTRUCTION_KINDS)
    assert set(capture.OpeningType.__args__) == set(vocab.OPENING_TYPES)
    assert set(capture.Flooring.__args__) == set(vocab.FLOORINGS)
    assert set(capture.Condition.__args__) == set(vocab.EXISTING_CONDITIONS)
    assert capture.FURNITURE_TAGS == set(vocab.WALL_TAGS) - {"PARTITION_EDGE", "NONE"}
