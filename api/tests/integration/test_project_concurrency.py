"""Project lifecycle concurrency (PLB-36) under forced interleavings, on SQLite and PostgreSQL.

Each test pauses the first request right after its permission check (it has read the project as the user saw it, and
has not yet taken the project lock) and lets a second, conflicting request run and commit; then the first resumes.
On SQLite the first request already holds the database write lock (BEGIN IMMEDIATE), so it commits first and the
second decides on its result; on PostgreSQL the second commits first and the first decides on it under the project's
row lock. Either way: no IntegrityError, no HTTP 500, no lost update, and the data shows one coherent outcome.
"""

from __future__ import annotations

import threading

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.api import ApiClient
from tests.support.commercial import ok, step
from tests.support.mtq import photo
from tests.support.project import BASE, ON, Projects, install, synthetic_policy
from tests.support.race import Hold
from veda.modules.project import access, creation
from veda.modules.project.models import Project, ProjectBaseline, ProjectTransition

pytestmark = ON


def _race(app, monkeypatch, first_user, second_user, first, second, *, module=access, name="require"):
    a, b = ApiClient(app.test_client()), ApiClient(app.test_client())
    a.token, b.token = first_user.token, second_user.token
    hold = Hold()
    threads: dict[str, threading.Thread] = {}
    original = getattr(module, name)

    def wrapped(*args, **kw):
        result = original(*args, **kw)
        if threading.current_thread() is threads.get("first") and not hold.reached.is_set():
            hold.wait()
        return result

    monkeypatch.setattr(module, name, wrapped)
    out: dict = {}

    def run_first():
        out["first"] = first(a)

    def run_second():
        assert hold.reached.wait(timeout=20), "the first request never reached its pause"
        out["second"] = second(b)
        hold.done()

    threads["first"], threads["second"] = threading.Thread(target=run_first), threading.Thread(target=run_second)
    with hold.racing(held=threads["first"], other=threads["second"]):
        for t in threads.values():
            t.start()
        for t in threads.values():
            t.join(timeout=60)
    monkeypatch.setattr(module, name, original)
    assert "first" in out and "second" in out, out
    for r in out.values():
        assert r.status < 500, r
    return out["first"], out["second"]


@pytest.fixture
def team(api, factory):
    t = Projects(api, factory)
    install(synthetic_policy(PLB_OD_03={"lifecycle_version": "PLB-2026.10.1", "transitions": []}))
    for user in (t.ops, t.manager, t.approver, t.founder, t.designer):
        t.token(user)
    yield t
    install(None)


def _project(t: Projects) -> dict:
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    t.prop, t.q = prop, q  # type: ignore[attr-defined]  # kept apart: each step returns a fresh project
    t.staff(p)
    return p


def test_two_bookings_of_one_accepted_quotation_create_one_project(team, app, monkeypatch):
    t = team
    prop, _, q = t.accepted()
    body = {"quotation_id": q["id"], "property_id": prop["id"]}
    first, second = _race(app, monkeypatch, t.manager, t.founder, lambda c: c.post(BASE, body),
                          lambda c: c.post(BASE, body), module=creation, name="visible_quotation")  # fmt: skip
    assert sorted((first.status, second.status)) == [201, 409]
    assert (first if first.status == 409 else second).code == "PROJECT_EXISTS"
    assert dbh.scalar(sa.select(sa.func.count()).select_from(Project)) == 1
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectBaseline)) == 1


def test_two_simultaneous_transitions_move_the_project_once(team, app, monkeypatch):
    t = team
    p = _project(t)
    t.checklist(p)
    version = t.get(p)["version"]
    move = lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"}, if_match=version)  # noqa: E731
    first, second = _race(app, monkeypatch, t.ops, t.founder, move, move)
    assert sorted((first.status, second.status)) == [201, 409]
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectTransition)
                      .where(ProjectTransition.outcome == "COMPLETED")) == 1  # fmt: skip
    assert t.get(p)["stage"]["code"] == "DESIGN_FINALISATION"


def test_a_checklist_reopened_during_a_transition_never_lets_an_open_item_through(team, app, monkeypatch):
    t = team
    p = _project(t)
    cur = t.checklist(p)
    item = cur["checklist"][0]["items"][0]
    move = lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"},  # noqa: E731
                            if_match=cur["version"])  # fmt: skip
    reopen = lambda c: c.post(f"{BASE}/{p['id']}/checklist/{item['id']}/reopen",  # noqa: E731
                              {"reason": "Customer changed the brief"}, if_match=item["version"])  # fmt: skip
    first, second = _race(app, monkeypatch, t.ops, t.founder, move, reopen)
    after = t.get(p)
    reopened = next(i for i in after["checklist"][0]["items"] if i["id"] == item["id"])["state"] == "OPEN"
    moved = after["stage"]["code"] == "DESIGN_FINALISATION"
    assert reopened != moved  # exactly one of them took effect
    if moved:
        assert second.status == 409 and second.code == "STAGE_COMPLETED"
    else:
        assert first.status == 409 and first.code == "VERSION_CONFLICT"


def test_a_gating_blocker_raised_during_a_transition_is_never_lost(team, app, monkeypatch):
    t = team
    p = _project(t)
    cur = t.checklist(p)
    move = lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "DESIGN_FINALISATION"},  # noqa: E731
                            if_match=cur["version"])  # fmt: skip
    block = lambda c: c.post(f"{BASE}/{p['id']}/blockers", {"category": "DESIGN", "impact": "GATING",  # noqa: E731
                             "title": "Brief changed", "responsible_party": "VEDA",
                             "blocks_stage_code": "DESIGN_FINALISATION"})  # fmt: skip
    first, second = _race(app, monkeypatch, t.ops, t.founder, move, block)
    after = t.get(p)
    assert second.status == 201 and len(after["blockers"]) == 1
    if after["stage"]["code"] == "DESIGN_FINALISATION":
        assert first.status == 201 and first.data["outcome"] == "COMPLETED"  # the move committed before the blocker
    else:
        assert first.status == 409 and first.code == "VERSION_CONFLICT"
        assert t.transition(p, "DESIGN_FINALISATION")["outcome"] == "REFUSED"


def test_a_variation_accepted_during_a_transition_is_recorded_once_and_gates_hold(team, app, monkeypatch):
    t = team
    p = _project(t)
    for to in ("DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS"):
        p = t.advance(p, to)
    t.ready_site(p)
    p = t.advance(p, "PRODUCTION_READINESS")
    v = t.variation(t.q, t.prop)
    step(t.c, v, "submit", t.c.sales)
    step(t.c, v, "approve", t.c.manager)
    v = ok(step(t.c, v, "issue", t.c.manager))
    t.checklist(p)
    cur = t.get(p)
    t.token(t.c.sales)
    move = lambda c: c.post(f"{BASE}/{p['id']}/transitions", {"to_stage": "IN_PRODUCTION"},  # noqa: E731
                            if_match=cur["version"])  # fmt: skip
    current_v = ok(t.as_(t.c.sales).get(f"/api/v1/quotations/{v['id']}"))
    accept = lambda c: c.post(f"/api/v1/quotations/{v['id']}/decision",  # noqa: E731
                              {"decision": "ACCEPTED", "method": "STAFF_RECORDED"}, if_match=current_v["version"])  # fmt: skip
    first, second = _race(app, monkeypatch, t.ops, t.c.sales, move, accept)
    assert second.status == 200
    after = t.get(p)
    assert [b["kind"] for b in after["baseline"]["lineage"]] == ["ORIGINAL", "VARIATION"]  # recorded exactly once
    assert after["baseline"]["verified"] is True
    if first.status == 201 and first.data["outcome"] == "COMPLETED":
        raise AssertionError("the move must never pass while the variation it raced was open")
    if first.status == 201:
        assert {b["code"] for b in first.data["transition"]["blockers"]} == {"VARIATION_OPEN"}
    else:
        assert first.status == 409 and first.code == "VERSION_CONFLICT"
    assert t.transition(p, "IN_PRODUCTION")["outcome"] == "COMPLETED"  # once accepted, the gate passes


def test_a_duplicate_handover_succeeds_once_and_a_snag_racing_it_is_not_lost(team, app, monkeypatch):
    t = team
    p = _project(t)
    order = ("DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS", "PRODUCTION_READINESS", "IN_PRODUCTION",
             "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK", "SNAGGING", "READY_FOR_HANDOVER")  # fmt: skip
    for to in order:
        if to == "PRODUCTION_READINESS":
            t.ready_site(p)
        if to == "SNAGGING":
            for cat in ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"):
                ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", {"category": cat, "result": "PASS"}), 201)
        p = t.advance(p, to)
    t.checklist(p)
    t.package(p)
    att = photo(t.as_(t.founder), "property", t.prop["id"])
    body = {"handover_on": "2026-10-15", "acknowledgement_reference": "HS-77", "evidence_attachment_id": att["id"]}
    cur = t.get(p)
    hand = lambda c: c.post(f"{BASE}/{p['id']}/handover", body, if_match=cur["version"])  # noqa: E731
    first, second = _race(app, monkeypatch, t.ops, t.founder, hand, hand)
    assert sorted((first.status, second.status)) == [201, 409]
    assert dbh.scalar(sa.select(sa.func.count()).select_from(ProjectTransition).where(
        ProjectTransition.kind == "HANDOVER", ProjectTransition.outcome == "COMPLETED")) == 1  # fmt: skip
    after = t.get(p)
    assert after["status"] == "HANDED_OVER" and [e["code"] for e in after["timeline"]].count("HANDED_OVER") == 1


def test_a_snag_raised_while_the_handover_runs_either_stops_it_or_is_refused(team, app, monkeypatch):
    t = team
    p = _project(t)
    order = ("DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS", "PRODUCTION_READINESS", "IN_PRODUCTION",
             "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK", "SNAGGING", "READY_FOR_HANDOVER")  # fmt: skip
    for to in order:
        if to == "PRODUCTION_READINESS":
            t.ready_site(p)
        if to == "SNAGGING":
            for cat in ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES"):
                ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", {"category": cat, "result": "PASS"}), 201)
        p = t.advance(p, to)
    t.checklist(p)
    t.package(p)
    att = photo(t.as_(t.founder), "property", t.prop["id"])
    body = {"handover_on": "2026-10-15", "acknowledgement_reference": "HS-78", "evidence_attachment_id": att["id"]}
    cur = t.get(p)
    hand = lambda c: c.post(f"{BASE}/{p['id']}/handover", body, if_match=cur["version"])  # noqa: E731
    snag = lambda c: c.post(f"{BASE}/{p['id']}/snags", {"category": "DAMAGE", "customer_title": "Scratch on top"})  # noqa: E731
    first, second = _race(app, monkeypatch, t.ops, t.founder, hand, snag)
    after = t.get(p)
    if after["status"] == "HANDED_OVER":
        assert first.status == 201 and second.status == 409 and second.code == "PROJECT_HANDED_OVER"
        assert after["snags"] == []
    else:
        assert second.status == 201 and len(after["snags"]) == 1
        assert first.status == 409 and first.code == "VERSION_CONFLICT"
