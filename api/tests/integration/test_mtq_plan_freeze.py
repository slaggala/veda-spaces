"""PR #88 blocker 1: a property's plan is frozen while a revision is SUBMITTED.

Verification and the derived counts read the live plan (the in-scope spaces of the property), so every plan mutation
— add, edit, scope change, archive, reorder, seed from a template — takes the property lock submit takes, re-reads
the property under it and is refused (409 ``PROPERTY_PLAN_FROZEN``) while a revision awaits verification. A draft's
plan stays editable; returning the revision for correction reopens it.
"""

from __future__ import annotations

import threading

import pytest
import sqlalchemy as sa

from tests.support.api import ApiClient
from tests.support.mtq import Site
from veda.kernel import db
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementSet, Property, PropertySpace

ON = pytest.mark.settings(mtq_site_enabled=True)
PAUSE = 2.0  # seconds the paused writer waits for the submit (on SQLite the submit waits on the writer's lock instead)


def _submitted(api, factory) -> Site:
    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    r = site.submit()
    assert r.status == 200, r
    return site


def _plan(property_id: str) -> tuple:
    """The plan as verification sees it, plus the property's derived counts."""
    with db.unit_of_work(write=False) as s:
        rows = s.execute(
            sa.select(
                PropertySpace.id,
                PropertySpace.label,
                PropertySpace.is_in_scope,
                PropertySpace.sort_order,
                PropertySpace.parent_space_id,
                PropertySpace.is_deleted,
            )  # fmt: skip
            .where(PropertySpace.property_id == property_id)
            .order_by(PropertySpace.id)
            .execution_options(include_deleted=True)
        ).all()
        prop = s.get(Property, property_id)
        counts = (prop.derived_bedroom_count, prop.derived_toilet_count, prop.derived_level_count, prop.version)
    return tuple(tuple(r) for r in rows), counts


def _space(api, space_id: str) -> dict:
    return next(sp for sp in api.get(f"/api/v1/properties/{_pid(space_id)}/spaces").data if sp["id"] == space_id)


def _pid(space_id: str) -> str:
    with db.unit_of_work(write=False) as s:
        return s.get(PropertySpace, space_id).property_id


def _mutate(kind: str, api, site: Site):
    pid = site.property["id"]
    if kind == "add":
        return api.post(f"/api/v1/properties/{pid}/spaces", {"space_type_code": "BEDROOM", "label": "Guest room"})
    if kind == "edit":
        sp = _space(api, site.kitchen["id"])
        return api.patch(f"/api/v1/spaces/{sp['id']}", {"label": "Open kitchen"}, if_match=sp["version"])
    if kind == "scope_out":
        sp = _space(api, site.kitchen["id"])
        return api.patch(f"/api/v1/spaces/{sp['id']}", {"is_in_scope": False}, if_match=sp["version"])
    if kind == "archive":
        sp = _space(api, site.bedroom["id"])
        return api.delete(f"/api/v1/spaces/{sp['id']}", {"reason": "Merged with the hall"}, if_match=sp["version"])
    if kind == "reorder":
        ids = [sp["id"] for sp in api.get(f"/api/v1/properties/{pid}/spaces").data]
        return api.put(f"/api/v1/properties/{pid}/spaces/order", {"space_ids": list(reversed(ids))})
    assert kind == "template"
    return api.post(f"/api/v1/properties/{pid}/spaces/from-template", {"template_key": "APARTMENT_2BHK"})


KINDS = ["add", "edit", "scope_out", "archive", "reorder", "template"]


@ON
@pytest.mark.parametrize("kind", KINDS)
def test_A_to_F_a_plan_mutation_is_refused_while_a_revision_is_submitted(api, factory, kind):
    site = _submitted(api, factory)
    before = _plan(site.property["id"])
    r = _mutate(kind, site.as_(site.sales), site)
    assert (r.status, r.code) == (409, "PROPERTY_PLAN_FROZEN"), r
    assert r.json["measurement_set_id"] == site.set["id"]
    assert _plan(site.property["id"]) == before, "the plan the revision was submitted on did not move"
    with db.unit_of_work(write=False) as s:
        assert s.get(MeasurementSet, site.set["id"]).status == "SUBMITTED"


@ON
def test_C_a_measured_space_never_leaves_verification_after_submission(api, factory):
    """The reviewer's probe: the kitchen is measured and in scope; taking it out of scope after submit is refused, so
    verification still checks it and the derived area still counts it."""
    site = _submitted(api, factory)
    api_ = site.as_(site.sales)
    sp = _space(api_, site.kitchen["id"])
    r = api_.patch(f"/api/v1/spaces/{sp['id']}", {"is_in_scope": False}, if_match=sp["version"])
    assert (r.status, r.code) == (409, "PROPERTY_PLAN_FROZEN"), r
    assert _space(api_, site.kitchen["id"])["is_in_scope"] is True
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    v = founder.post(f"/api/v1/measurement-sets/{site.set['id']}/verify", {"acknowledgements": []},
                     if_match=cur["version"])  # fmt: skip
    assert v.status == 200, v
    assert site.kitchen["id"] in {
        sp["space_id"] for sp in founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data["spaces"]
    }


@ON
@pytest.mark.parametrize("kind", KINDS)
def test_G_a_draft_plan_stays_editable(api, factory, kind):
    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    if kind == "template":  # seeding needs an empty property: a fresh one of the same lead
        p = (
            site.as_(site.sales)
            .post("/api/v1/properties", {"lead_id": site.lead["id"], "property_type_code": "APARTMENT"})
            .data
        )
        r = site.api.post(f"/api/v1/properties/{p['id']}/spaces/from-template", {"template_key": "APARTMENT_2BHK"})
        assert r.status == 201, r
        return
    r = _mutate(kind, site.as_(site.sales), site)
    assert r.status in (200, 201, 204), r


@ON
def test_G_returning_the_revision_for_correction_reopens_the_plan(api, factory):
    site = _submitted(api, factory)
    founder = site.as_(site.founder)
    cur = founder.get(f"/api/v1/measurement-sets/{site.set['id']}").data
    r = founder.post(f"/api/v1/measurement-sets/{site.set['id']}/reject", {"reason": "Kitchen walls re-measure"},
                     if_match=cur["version"])  # fmt: skip
    assert r.status == 200, r
    assert _mutate("add", site.as_(site.sales), site).status == 201


def _race(app, api, factory, monkeypatch, kind: str):
    """The plan writer reads the property, checks its scope, then pauses before the lock; the submit runs meanwhile."""
    from veda.modules.mtq import properties as P

    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    set_id = site.set["id"]
    surveyor, sales = ApiClient(app.test_client()), ApiClient(app.test_client())
    surveyor.token = factory.login(api, site.lead_surveyor)
    sales.token = factory.login(api, site.sales)
    version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]
    kitchen = sales.get(f"/api/v1/properties/{site.property['id']}/spaces").data[0]
    paused, submitted = threading.Event(), threading.Event()
    threads: dict[str, threading.Thread] = {}
    original = P.lock_plan

    def pause_then_lock(*a, **kw):
        if threading.current_thread() is threads.get("writer") and not paused.is_set():
            paused.set()
            submitted.wait(timeout=PAUSE)
        return original(*a, **kw)

    monkeypatch.setattr(P, "lock_plan", pause_then_lock)
    out: dict = {}

    def write():
        if kind == "add":
            out["write"] = sales.post(f"/api/v1/properties/{site.property['id']}/spaces",
                                      {"space_type_code": "STORE", "label": "Store", "is_in_scope": False})  # fmt: skip
        else:
            out["write"] = sales.patch(f"/api/v1/spaces/{kitchen['id']}", {"is_in_scope": False},
                                       if_match=kitchen["version"])  # fmt: skip

    def submit():
        assert paused.wait(timeout=10), "the plan writer never reached its pause"
        out["submit"] = surveyor.post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=version)
        submitted.set()

    threads["writer"], threads["submitter"] = threading.Thread(target=write), threading.Thread(target=submit)
    for t in threads.values():
        t.start()
    for t in threads.values():
        t.join(timeout=30)
    return site, out


@ON
@pytest.mark.parametrize("kind", ["add", "scope_out"])
def test_H_a_plan_mutation_racing_submit_lands_before_it_or_is_refused(app, api, factory, monkeypatch, kind):
    site, out = _race(app, api, factory, monkeypatch, kind)
    assert "write" in out and "submit" in out, out
    assert out["write"].status != 500 and out["submit"].status != 500, out
    assert out["submit"].status == 200, out["submit"]
    accepted = out["write"].status in (200, 201)
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, site.set["id"])
        assert mset.status == "SUBMITTED"
        last_plan_write = s.execute(
            sa.select(sa.func.max(PropertySpace.updated_on))
            .where(PropertySpace.property_id == site.property["id"])
            .execution_options(include_deleted=True)
        ).scalar()
        assert last_plan_write <= mset.submitted_on, "no plan row changed after the revision was submitted"
        sqlite = db.is_sqlite()
    if not accepted:
        assert (out["write"].status, out["write"].code) == (409, "PROPERTY_PLAN_FROZEN"), out["write"]
    # The interleaving is forced, not dodged: on PostgreSQL the submit commits while the writer is paused before its
    # lock, so the writer must be refused under it; SQLite's BEGIN IMMEDIATE runs the writer first.
    assert accepted is sqlite, (kind, out["write"])


@ON
def test_H_a_free_race_of_plan_mutations_and_submit_never_moves_a_submitted_plan(app, api, factory):
    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    set_id = site.set["id"]
    version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]
    surveyor = ApiClient(app.test_client())
    surveyor.token = factory.login(api, site.lead_surveyor)
    writers = [ApiClient(app.test_client()) for _ in range(3)]
    token = factory.login(api, site.sales)
    for w in writers:
        w.token = token
    barrier = threading.Barrier(1 + len(writers))
    results: list = [None] * (1 + len(writers))

    def run(i):
        barrier.wait()
        if i == 0:
            results[0] = surveyor.post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=version)
        else:
            results[i] = writers[i - 1].post(f"/api/v1/properties/{site.property['id']}/spaces",
                                             {"space_type_code": "STORE", "label": f"Store {i}", "is_in_scope": False})  # fmt: skip

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(results))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(r is not None and r.status != 500 for r in results), results
    assert results[0].status == 200, results[0]
    for r in results[1:]:
        assert r.status == 201 or (r.status, r.code) in ((409, "PROPERTY_PLAN_FROZEN"), (503, "SERVICE_UNAVAILABLE")), r
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, set_id)
        last = s.execute(
            sa.select(sa.func.max(PropertySpace.updated_on)).where(PropertySpace.property_id == site.property["id"])
        ).scalar()
        assert mset.status == "SUBMITTED" and last <= mset.submitted_on


def test_the_plan_lock_is_the_canonical_property_lock():
    """No second locking implementation: plan writes go through sets.lock_property (via sets.lock_for_write)."""
    import inspect

    from veda.modules.mtq import properties as P

    assert "sets.lock_for_write" in inspect.getsource(P.lock_plan)
    assert "sets.lock_property" in inspect.getsource(P.require_plan_open)
    assert "with_for_update" not in inspect.getsource(P)
    assert sets.lock_for_write.__module__ == "veda.modules.mtq.sets"
