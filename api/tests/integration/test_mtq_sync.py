"""MTQ B1-T09: offline batch sync (blueprint §6.1, §11.1 /sync; B1-SCOPE §2.8, §2.9.3)."""

from __future__ import annotations

import hashlib

import pytest
import sqlalchemy as sa

from tests.support.mtq import Site, bedroom_payload, jpeg, kitchen_payload
from veda.kernel import db
from veda.kernel.errors import ApiError
from veda.modules.attachments.models import Attachment
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementNote, SpaceMeasurement

ON = pytest.mark.settings(mtq_site_enabled=True)


@pytest.fixture
def site(api, factory):
    s = Site(api, factory)
    s.open_set()
    return s


def sync(site, ops, user=None, batch="batch-1", headers=None, mset=None):
    api = site.as_(user or site.lead_surveyor)
    m = mset or site.set
    return api.post(f"/api/v1/measurement-sets/{m['id']}/sync", {"batch_id": batch, "operations": ops},
                    headers=headers)  # fmt: skip


def space_op(op_id, space, data):
    return {"op_id": op_id, "type": "space", "space_id": space["id"], "data": data}


def photo_op(op_id, space):
    data = jpeg()
    return {"op_id": op_id, "type": "attachment", "data": {
        "entity_type": "property_space", "entity_id": space["id"], "mime_type": "image/jpeg", "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "client_ref": f"photo-{op_id}"}}  # fmt: skip


def test_sync_is_404_while_the_flag_is_off(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    assert api.post(f"/api/v1/measurement-sets/{'0' * 32}/sync", {"batch_id": "b", "operations": []}).status == 404


@ON
def test_a_batch_applies_in_order_and_answers_per_operation(site):
    ops = [
        space_op("op-1", site.kitchen, kitchen_payload()),
        {"op_id": "op-2", "type": "note", "data": {"client_ref": "n-1", "space_id": site.kitchen["id"],
                                                    "note_type_code": "RISK", "body": "Damp patch near the sink"}},
        {"op_id": "op-3", "type": "property_capture", "data": {"floor_number": 4, "lift_available": True}},
        photo_op("op-4", site.kitchen),
    ]  # fmt: skip
    r = sync(site, ops)
    assert r.status == 200, r
    assert [x["status"] for x in r.data["results"]] == ["APPLIED"] * 4
    assert [x["op_id"] for x in r.data["results"]] == ["op-1", "op-2", "op-3", "op-4"]
    assert r.data["results"][3]["upload"]["required"] is True  # metadata before bytes
    assert r.data["space_versions"][site.kitchen["id"]] == r.data["results"][0]["version"]
    state = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/sync-state").data
    assert state["set_status"] == "DRAFT" and state["spaces"][0]["space_id"] == site.kitchen["id"]


@ON
def test_retries_never_duplicate_and_replays_return_the_first_answer(site):
    first_ops = [
        space_op("op-1", site.kitchen, kitchen_payload()),
        {"op_id": "op-2", "type": "note", "data": {"client_ref": "n-1", "note_type_code": "OBSERVATION", "body": "Lift slow"}},
        photo_op("op-3", site.kitchen),
    ]  # fmt: skip
    first = sync(site, first_ops).data
    assert [x["status"] for x in first["results"]] == ["APPLIED"] * 3
    # The client never saw the answer and resends the same queue unchanged (a create carries no base_version).
    again = sync(site, first_ops, batch="batch-1-retry").data
    assert [x["status"] for x in again["results"]] == ["DUPLICATE", "DUPLICATE", "DUPLICATE"]
    other = sync(site, [space_op("op-1b", site.kitchen, kitchen_payload(length_mm=3700))], batch="b-other").data
    assert other["results"][0]["status"] == "CONFLICT"  # same space, no base, different content: never overwritten
    with db.unit_of_work(write=False) as s:
        assert s.execute(sa.select(sa.func.count(SpaceMeasurement.id))).scalar() == 1
        assert s.execute(sa.select(sa.func.count(MeasurementNote.id))).scalar() == 1
        assert s.execute(sa.select(sa.func.count(Attachment.id))).scalar() == 1
    key = {"Idempotency-Key": "sync-batch-key-000000001"}
    one = sync(site, [space_op("op-9", site.bedroom, bedroom_payload())], batch="b9", headers=key)
    two = sync(site, [space_op("op-9", site.bedroom, bedroom_payload())], batch="b9", headers=key)
    assert one.status == two.status == 200 and one.json == two.json


@ON
def test_partial_failure_keeps_the_rest(site):
    ops = [
        space_op("op-1", site.kitchen, kitchen_payload()),
        space_op("op-2", site.bedroom, {"length_mm": -1}),
        {"op_id": "op-3", "type": "note", "data": {"note_type_code": "OBSERVATION", "body": "Owner travelling"}},
    ]
    r = sync(site, ops).data
    assert [x["status"] for x in r["results"]] == ["APPLIED", "REJECTED", "APPLIED"]
    assert r["results"][1]["code"] == "VALIDATION_FAILED" and r["results"][1]["errors"]
    assert r["counts"] == {"APPLIED": 2, "REJECTED": 1}
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    assert {sp["space_id"] for sp in tree["spaces"]} == {site.kitchen["id"]} and len(tree["notes"]) == 1


@ON
def test_offline_conflict_between_two_surveyors_is_explicit(site):
    site.start(site.second)
    base = sync(site, [space_op("op-1", site.bedroom, bedroom_payload())], user=site.second).data
    v1 = base["results"][0]["version"]
    online = sync(site, [space_op("op-2", site.bedroom, bedroom_payload(base_version=v1, length_mm=3310))],
                  user=site.lead_surveyor, batch="lead-online").data  # fmt: skip
    assert online["results"][0]["status"] == "APPLIED"
    queued = sync(site, [space_op("op-3", site.bedroom, bedroom_payload(base_version=v1, length_mm=3290))],
                  user=site.second, batch="second-offline").data  # fmt: skip
    res = queued["results"][0]
    assert (
        res["status"] == "CONFLICT"
        and res["conflicting_fields"] == ["length_mm"]
        and res["server"]["length_mm"] == 3310
    )
    resolved = sync(site, [space_op("op-4", site.bedroom,
                                    bedroom_payload(base_version=res["current_version"], length_mm=3290))],
                    user=site.second, batch="second-resolved").data  # fmt: skip
    assert resolved["results"][0]["status"] == "APPLIED"
    site.start(site.third)
    claimed = sync(site, [space_op("op-5", site.bedroom, bedroom_payload(base_version=resolved["results"][0]["version"]))],
                   user=site.third, batch="third").data  # fmt: skip
    assert claimed["results"][0]["status"] == "CLAIMED"


@ON
def test_frozen_revisions_point_at_the_current_draft(site):
    site.capture_full()
    assert site.submit().status == 200
    late = sync(
        site, [space_op("op-1", site.kitchen, kitchen_payload(base_version=1)), photo_op("op-2", site.kitchen)]
    ).data
    assert [x["status"] for x in late["results"]] == ["FROZEN", "APPLIED"]  # space photos are not revision-scoped
    assert late["results"][0]["current_draft_id"] is None
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    correction = founder.post(f"/api/v1/measurement-sets/{site.set['id']}/reject", {"reason": "recheck"},
                              if_match=cur["version"]).data["correction"]  # fmt: skip
    again = sync(site, [space_op("op-3", site.kitchen, kitchen_payload(base_version=1))], batch="b3").data
    assert again["results"][0]["status"] == "FROZEN" and again["results"][0]["current_draft_id"] == correction["id"]
    state = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}/sync-state").data
    assert state["current_draft_id"] == correction["id"]


@ON
def test_batches_are_bounded_and_well_formed(site):
    too_many = [
        {"op_id": f"op-{i}", "type": "note", "data": {"note_type_code": "OBSERVATION", "body": "x"}} for i in range(51)
    ]
    assert sync(site, too_many).status == 422
    dup = [{"op_id": "same", "type": "note", "data": {"note_type_code": "OBSERVATION", "body": "x"}}] * 2
    assert sync(site, dup).status == 422
    assert sync(site, [{"op_id": "a", "type": "space", "data": {}}]).status == 422  # names no space
    assert (
        sync(site, [{"op_id": "a", "type": "release", "space_id": site.kitchen["id"], "data": {"x": 1}}]).status == 422
    )


@ON
def test_two_writes_to_one_space_in_one_batch_apply_in_order(site):
    first = space_op("op-1", site.kitchen, kitchen_payload())
    r = sync(site, [first]).data
    v = r["results"][0]["version"]
    second = space_op("op-2", site.kitchen, kitchen_payload(base_version=v, length_mm=3620))
    third = space_op("op-3", site.kitchen, kitchen_payload(base_version=v, length_mm=3630))  # same base as op-2
    out = sync(site, [second, third], batch="b2").data
    assert [x["status"] for x in out["results"]] == ["APPLIED", "CONFLICT"]  # op-3 edited the version op-2 replaced
    assert out["results"][1]["conflicting_fields"] == ["length_mm"]
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{site.set['id']}").data
    assert tree["spaces"][0]["length_mm"] == 3620


@ON
def test_a_rolled_back_operation_does_not_break_version_tracking(site, monkeypatch):
    v = sync(site, [space_op("op-0", site.kitchen, kitchen_payload())]).data["results"][0]["version"]
    calls = {"n": 0}

    def flaky(s, sm, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ApiError(422, "VALIDATION_FAILED", "simulated failure after the row was written")

    monkeypatch.setattr(sets, "AFTER_SPACE_WRITE", [flaky, *sets.AFTER_SPACE_WRITE])
    out = sync(site, [space_op("op-1", site.kitchen, kitchen_payload(base_version=v, length_mm=3610)),
                      space_op("op-2", site.kitchen, kitchen_payload(base_version=v, length_mm=3620))], batch="b1").data  # fmt: skip
    assert [x["status"] for x in out["results"]] == ["REJECTED", "APPLIED"]
    assert out["results"][1]["version"] == v + 1  # the applied write still advanced the version
    stale = sync(
        site, [space_op("op-3", site.kitchen, kitchen_payload(base_version=v, length_mm=3700))], batch="b2"
    ).data
    assert stale["results"][0]["status"] == "CONFLICT"  # a client still on the old version cannot overwrite it
