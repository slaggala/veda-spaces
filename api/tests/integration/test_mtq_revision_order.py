"""MC-1 (PR #87 review): verification order and supersession.

FULL outranks LITE; a higher revision outranks a lower one; one revision awaits verification at a time; the revision a
verification replaces is decided under a property lock at verification time, never at draft creation.
"""

from __future__ import annotations

import threading

import pytest
import sqlalchemy as sa

from tests.support.api import ApiClient
from tests.support.mtq import Site
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementSet

ON = pytest.mark.settings(mtq_site_enabled=True)


def _verify(site, set_id, api=None):
    api = api or site.as_(site.founder)
    cur = api.get(f"/api/v1/measurement-sets/{set_id}").data
    return api.post(f"/api/v1/measurement-sets/{set_id}/verify", {"acknowledgements": []}, if_match=cur["version"])


def _captured_revision(site, *, level=None, copy_from=None) -> dict:
    """A new revision on the lead surveyor's visit, captured to the FULL rules and submitted."""
    body = {"unit_system_code": "MM", **({"survey_level_code": level} if level else {}),
            **({"copy_from_set_id": copy_from} if copy_from else {})}  # fmt: skip
    visit = site.visits[site.lead_surveyor.id]
    r = site.as_(site.lead_surveyor).post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets", body)
    assert r.status == 201, r
    site.set = r.data
    site.capture_full()
    assert site.submit().status == 200
    return site.set


def _forced_submitted(site, source_id: str, level: str) -> str:
    """A second SUBMITTED revision copied from ``source_id``: a state the workflow no longer allows (one submitted
    revision at a time), forced here to prove verification itself still refuses to break precedence."""
    with actor(system_context()), db.unit_of_work() as s:
        src = s.get(MeasurementSet, source_id)
        top = s.execute(
            sa.select(sa.func.max(MeasurementSet.revision_no)).where(MeasurementSet.property_id == src.property_id)
        ).scalar()
        new = MeasurementSet(property_id=src.property_id, measurement_visit_id=src.measurement_visit_id, revision_no=top + 1,
                             status="DRAFT", survey_level_code=level, method_code=src.method_code,
                             unit_system_code=src.unit_system_code, captured_by=src.captured_by, summary={},
                             property_capture={})  # fmt: skip
        s.add(new)
        s.flush()
        sets.copy_revision(s, src, new, src.captured_by)
        new_id = new.id
    tree = site.as_(site.lead_surveyor).get(f"/api/v1/measurement-sets/{new_id}").data
    for sm in tree["spaces"]:
        site.wall_photos(sm)  # the copy has new wall rows; their photos are taken again
    with actor(system_context()), db.unit_of_work() as s:
        new = s.get(MeasurementSet, new_id)
        new.status, new.submitted_on, new.submitted_by = "SUBMITTED", db.tx_time(s), new.captured_by
    return new_id


def _status(set_id):
    with db.unit_of_work(write=False) as s:
        m = s.get(MeasurementSet, set_id)
        return m.status, m.supersedes_set_id


@ON
def test_lite_never_supersedes_a_verified_full(api, factory):
    site = Site(api, factory)
    rev1 = site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    assert _verify(site, rev1["id"]).status == 200
    # The workflow refuses a Lite draft outright ...
    visit = site.visits[site.lead_surveyor.id]
    r = site.as_(site.lead_surveyor).post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets",
                                          {"survey_level_code": "LITE"})  # fmt: skip
    assert r.status == 422 and r.json["code"] == "LITE_AFTER_FULL"
    # ... and verification refuses a Lite revision that reached SUBMITTED anyway.
    lite = _forced_submitted(site, rev1["id"], "LITE")
    v = _verify(site, lite)
    assert v.status == 422 and v.json["code"] == "LITE_AFTER_FULL"
    assert _status(rev1["id"])[0] == "VERIFIED" and _status(lite)[0] == "SUBMITTED"


@ON
def test_full_supersedes_a_verified_lite_and_records_the_predecessor(api, factory):
    site = Site(api, factory, level="LITE")
    rev1 = site.open_set(survey_level_code="LITE", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    assert _verify(site, rev1["id"]).status == 200
    rev2 = _captured_revision(site, level="FULL", copy_from=rev1["id"])
    r = _verify(site, rev2["id"])
    assert r.status == 200, r
    assert r.data["status"] == "VERIFIED" and r.data["supersedes_set_id"] == rev1["id"]
    assert _status(rev1["id"]) == ("SUPERSEDED", None)
    assert _status(rev2["id"]) == ("VERIFIED", rev1["id"])


@ON
def test_a_pending_full_revision_outranks_a_newer_lite_one(api, factory):
    site = Site(api, factory)
    rev1 = site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    lite2 = _forced_submitted(site, rev1["id"], "LITE")
    first = _verify(site, lite2)
    assert first.status == 409 and first.json["code"] == "HIGHER_REVISION_PENDING"
    assert _verify(site, rev1["id"]).status == 200
    late = _verify(site, lite2)
    assert late.status == 422 and late.json["code"] == "LITE_AFTER_FULL"
    assert _status(rev1["id"])[0] == "VERIFIED"


@ON
def test_an_older_revision_never_replaces_a_newer_verified_one(api, factory):
    site = Site(api, factory)
    rev1 = site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    rev2 = _forced_submitted(site, rev1["id"], "FULL")
    pending = _verify(site, rev1["id"])
    assert pending.status == 409 and pending.json["code"] == "HIGHER_REVISION_PENDING"
    assert _verify(site, rev2).status == 200
    old = _verify(site, rev1["id"])
    assert old.status == 409 and old.json["code"] == "REVISION_OUT_OF_ORDER"
    assert _status(rev2) == ("VERIFIED", None) and _status(rev1["id"])[0] == "SUBMITTED"


@ON
def test_no_new_draft_while_a_revision_awaits_verification(api, factory):
    site = Site(api, factory)
    rev1 = site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    visit = site.visits[site.lead_surveyor.id]
    r = site.as_(site.lead_surveyor).post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets",
                                          {"copy_from_set_id": rev1["id"]})  # fmt: skip
    assert r.status == 409 and r.json["code"] == "SUBMITTED_REVISION_PENDING"
    assert r.json["measurement_set_id"] == rev1["id"]
    # The frozen workflow: return it for correction, then the correction draft is the only open revision.
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{rev1['id']}").data
    back = founder.post(f"/api/v1/measurement-sets/{rev1['id']}/reject", {"reason": "recheck the kitchen"},
                        if_match=cur["version"])  # fmt: skip
    assert back.status == 200 and back.data["correction"]["status"] == "DRAFT"


@ON
def test_concurrent_verifications_leave_exactly_one_authoritative_revision(app, api, factory):
    site = Site(api, factory)
    rev1 = site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    assert site.submit().status == 200
    rev2 = _forced_submitted(site, rev1["id"], "FULL")
    token = factory.login(api, site.founder)
    clients = [ApiClient(app.test_client()) for _ in range(4)]
    for c in clients:
        c.token = token
    versions = {sid: api.get(f"/api/v1/measurement-sets/{sid}").data["version"] for sid in (rev1["id"], rev2)}
    targets = [rev1["id"], rev2, rev2, rev1["id"]]
    barrier = threading.Barrier(len(clients))
    results: list = [None] * len(clients)

    def run(i):
        barrier.wait()
        results[i] = clients[i].post(f"/api/v1/measurement-sets/{targets[i]}/verify", {"acknowledgements": []},
                                     if_match=versions[targets[i]]).status  # fmt: skip

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(clients))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(200) == 1 and all(code in (200, 409, 412) for code in results), results
    with db.unit_of_work(write=False) as s:
        verified = s.execute(sa.select(MeasurementSet.id).where(MeasurementSet.property_id == rev1["property_id"],
                                                                MeasurementSet.status == "VERIFIED")).scalars().all()  # fmt: skip
    assert verified == [rev2], "the highest revision is the one authoritative revision"
    assert _status(rev2) == ("VERIFIED", None) and _status(rev1["id"])[0] == "SUBMITTED"
