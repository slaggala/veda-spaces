"""Owner decision 2026-10-13: while a revision is SUBMITTED, the property values verification reads stay as submitted.

Verification compares the measured total with the stated built-up (or carpet) area (BUILT_UP_DEVIATION). A PATCH of
those values after submission is refused with 409 ``PROPERTY_REFERENCE_FROZEN``, so it can never change whether the
submitted revision trips the check. Other property fields stay editable, and the freeze ends when the revision is
verified or returned for correction.
"""

from __future__ import annotations

import threading

import pytest

from tests.support.api import ApiClient
from tests.support.mtq import Site
from tests.support.race import Hold
from veda.kernel import db
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementSet, Property

ON = pytest.mark.settings(mtq_site_enabled=True)
FAR_OFF = 1000_00  # sq ft (centi): far outside ±25 % of the Site's measured total


def _site(api, factory, *, submit: bool) -> Site:
    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    if submit:
        r = site.submit()
        assert r.status == 200, r
    return site


def _patch(site: Site, body: dict):
    api = site.as_(site.sales)
    prop = api.get(f"/api/v1/properties/{site.property['id']}").data
    return api.patch(f"/api/v1/properties/{prop['id']}", body, if_match=prop["version"])


def _stated(site: Site) -> tuple:
    with db.unit_of_work(write=False) as s:
        p = s.get(Property, site.property["id"])
        return p.built_up_area_sqft_centi, p.carpet_area_sqft_centi


def _verify(site: Site, acks=None):
    api = site.as_(site.founder)
    cur = api.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    return api.post(f"/api/v1/measurement-sets/{site.set['id']}/verify",
                    {"acknowledgements": acks or []}, if_match=cur["version"])  # fmt: skip


@ON
@pytest.mark.parametrize("field", ["built_up_area_sqft_centi", "carpet_area_sqft_centi"])
def test_a_stated_area_is_frozen_while_a_revision_is_submitted(api, factory, field):
    site = _site(api, factory, submit=True)
    before = _stated(site)
    r = _patch(site, {field: FAR_OFF})
    assert (r.status, r.code) == (409, "PROPERTY_REFERENCE_FROZEN"), r
    assert r.json["fields"] == [field] and r.json["measurement_set_id"] == site.set["id"]
    assert _stated(site) == before


@ON
def test_other_property_fields_stay_editable_and_an_unchanged_area_is_accepted(api, factory):
    site = _site(api, factory, submit=True)
    r = _patch(site, {"notes": "Gate code with the security desk", "pincode": "500081"})
    assert r.status == 200, r
    same = _stated(site)[0]
    assert _patch(site, {"built_up_area_sqft_centi": same, "notes": "Again"}).status == 200


@ON
def test_a_later_patch_cannot_clear_a_built_up_deviation(api, factory):
    """Stated area far off at submission: verification must still raise BUILT_UP_DEVIATION."""
    site = _site(api, factory, submit=False)
    assert _patch(site, {"built_up_area_sqft_centi": FAR_OFF}).status == 200  # draft: editable
    assert site.submit().status == 200
    honest = _stated(site)[0]
    assert _patch(site, {"built_up_area_sqft_centi": 220_00}).code == "PROPERTY_REFERENCE_FROZEN"
    assert _stated(site)[0] == honest
    r = _verify(site)
    assert r.status == 422 and "BUILT_UP_DEVIATION" in {p["code"] for p in r.json["pointers"]}, r


@ON
def test_a_later_patch_cannot_create_a_built_up_deviation(api, factory):
    """Stated area within tolerance at submission: a later PATCH cannot make verification fail on it."""
    site = _site(api, factory, submit=True)
    assert _patch(site, {"built_up_area_sqft_centi": FAR_OFF}).code == "PROPERTY_REFERENCE_FROZEN"
    assert _verify(site).status == 200


@ON
def test_the_freeze_ends_when_the_revision_leaves_submitted(api, factory):
    site = _site(api, factory, submit=True)
    assert _verify(site).status == 200
    assert _patch(site, {"built_up_area_sqft_centi": 230_00}).status == 200  # verified: the snapshot is sealed
    other = _site(api, factory, submit=True)
    founder = other.as_(other.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{other.set['id']}").data
    rej = founder.post(f"/api/v1/measurement-sets/{other.set['id']}/reject", {"reason": "Re-measure"},
                       if_match=cur["version"])  # fmt: skip
    assert rej.status == 200, rej
    assert _patch(other, {"carpet_area_sqft_centi": 200_00}).status == 200  # returned for correction


@ON
def test_a_stated_area_patch_racing_submit_lands_before_it_or_is_refused(app, api, factory, monkeypatch):
    """The PATCH reads the property, then pauses before the lock while the submit commits."""
    site = _site(api, factory, submit=False)
    set_id = site.set["id"]
    surveyor, sales = ApiClient(app.test_client()), ApiClient(app.test_client())
    surveyor.token = factory.login(api, site.lead_surveyor)
    sales.token = factory.login(api, site.sales)
    set_version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]
    prop = sales.get(f"/api/v1/properties/{site.property['id']}").data
    hold = Hold()
    threads: dict[str, threading.Thread] = {}
    original = sets.lock_property

    def pause_then_lock(*a, **kw):
        if threading.current_thread() is threads.get("writer") and not hold.reached.is_set():
            hold.wait()
        return original(*a, **kw)

    monkeypatch.setattr(sets, "lock_property", pause_then_lock)
    out: dict = {}

    def write():
        out["write"] = sales.patch(f"/api/v1/properties/{prop['id']}", {"built_up_area_sqft_centi": 230_00},
                                   if_match=prop["version"])  # fmt: skip

    def submit():
        assert hold.reached.wait(timeout=10), "the PATCH never reached its pause"
        out["submit"] = surveyor.post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=set_version)
        hold.done()

    threads["writer"], threads["submitter"] = threading.Thread(target=write), threading.Thread(target=submit)
    with hold.racing(held=threads["writer"], other=threads["submitter"]):
        for t in threads.values():
            t.start()
        for t in threads.values():
            t.join(timeout=30)
    assert set(out) == {"write", "submit"} and all(r.status != 500 for r in out.values()), out
    assert out["submit"].status == 200, out["submit"]
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, set_id)
        p = s.get(Property, site.property["id"])
        assert mset.status == "SUBMITTED" and p.updated_on <= mset.submitted_on
        sqlite = db.is_sqlite()
    if sqlite:  # BEGIN IMMEDIATE: the PATCH holds the write lock and commits first
        assert out["write"].status == 200, out["write"]
    else:  # the submit committed while the PATCH waited before its lock: refused under it
        assert (out["write"].status, out["write"].code) == (409, "PROPERTY_REFERENCE_FROZEN"), out["write"]
