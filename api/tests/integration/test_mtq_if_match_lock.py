"""PR #88 blocker 2: If-Match is compared against the version read under the property lock.

Two requests start with the same If-Match version. Request B reads the record, then pauses just before it takes the
property lock; request A runs to completion meanwhile. B then resumes. The order the routes follow is lock →
authoritative re-read → If-Match → mutate, so B is refused with the stale-version response (409 ``VERSION_CONFLICT``
and the current version) — not admitted on the version it read before the lock (a lost update), and not refused by a
later state check that only happened to catch it.

On PostgreSQL the interleaving is real: A commits while B is paused, so B is the loser. SQLite write units of work start
under BEGIN IMMEDIATE, so B already holds the database write lock when it pauses: A waits, B commits first and A is the
loser. Either way exactly one request succeeds, the other gets the stale-version response, and no request returns 500.
"""

from __future__ import annotations

import threading

import pytest

from tests.support.api import ApiClient
from tests.support.mtq import FULL_CAPTURE, Site
from veda.kernel import db
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementNote, MeasurementSet, PropertySpace

ON = pytest.mark.settings(mtq_site_enabled=True)
PAUSE = 2.0


def _site(api, factory, *, submitted: bool) -> Site:
    site = Site(api, factory)
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    if submitted:
        r = site.submit()
        assert r.status == 200, r
    return site


def _client(app, factory, api, user) -> ApiClient:
    c = ApiClient(app.test_client())
    c.token = factory.login(api, user)
    return c


def _scenario(kind: str, app, api, factory):
    """(client A, client B, request(client, tag), the record read back) for one If-Match path."""
    submitted = kind in ("verify", "reject")
    site = _site(api, factory, submitted=submitted)
    set_id = site.set["id"]
    url = f"/api/v1/measurement-sets/{set_id}"
    version = api.get(url).data["version"]
    if kind == "patch":
        a = b = site.lead_surveyor
        captures = {"A": {**FULL_CAPTURE, "access_notes": "A"}, "B": {**FULL_CAPTURE, "access_notes": "B"}}

        def call(c, tag):
            return c.patch(url, {"property_capture": captures[tag]}, if_match=version)
    elif kind == "submit":
        a = b = site.lead_surveyor

        def call(c, tag):
            return c.post(f"{url}/submit", if_match=version)
    elif kind in ("verify", "reject"):
        a, b = site.founder, factory.user("ADMIN")

        def call(c, tag):
            if kind == "verify":
                return c.post(f"{url}/verify", {"acknowledgements": []}, if_match=version)
            return c.post(f"{url}/reject", {"reason": f"Re-measure ({tag})"}, if_match=version)
    elif kind == "note_delete":
        a = b = site.lead_surveyor
        note = site.as_(site.lead_surveyor).post(f"{url}/notes", {"client_ref": "n-1", "note_type_code": "RISK",
                                                                 "body": "Seepage near the window"}).data  # fmt: skip
        version = note["version"]

        def call(c, tag):
            return c.delete(f"{url}/notes/{note['id']}", if_match=version)
    else:
        assert kind == "space_patch"
        a = b = site.sales
        sp = next(x for x in site.as_(site.sales).get(f"/api/v1/properties/{site.property['id']}/spaces").data
                  if x["id"] == site.kitchen["id"])  # fmt: skip
        version = sp["version"]

        def call(c, tag):
            return c.patch(f"/api/v1/spaces/{sp['id']}", {"label": f"Kitchen {tag}"}, if_match=version)

    return site, _client(app, factory, api, a), _client(app, factory, api, b), call, version


KINDS = ["patch", "submit", "note_delete", "verify", "reject", "space_patch"]


@ON
@pytest.mark.parametrize("kind", KINDS)
def test_a_stale_if_match_is_refused_after_the_lock(app, api, factory, monkeypatch, kind):
    site, client_a, client_b, call, version = _scenario(kind, app, api, factory)
    paused, a_done = threading.Event(), threading.Event()
    threads: dict[str, threading.Thread] = {}
    original = sets.lock_property

    def pause_before_lock(*args, **kw):  # B has read the record (version n) and is about to take the lock
        if threading.current_thread() is threads.get("B") and not paused.is_set():
            paused.set()
            a_done.wait(timeout=PAUSE)
        return original(*args, **kw)

    monkeypatch.setattr(sets, "lock_property", pause_before_lock)
    out: dict = {}

    def run_b():
        out["B"] = call(client_b, "B")

    def run_a():
        assert paused.wait(timeout=10), "B never reached the lock"
        out["A"] = call(client_a, "A")
        a_done.set()

    threads["B"], threads["A"] = threading.Thread(target=run_b), threading.Thread(target=run_a)
    for t in threads.values():
        t.start()
    for t in threads.values():
        t.join(timeout=30)
    assert set(out) == {"A", "B"}, out
    assert all(r.status != 500 for r in out.values()), out
    won = [tag for tag, r in out.items() if r.status in (200, 204)]
    lost = [tag for tag, r in out.items() if r.status not in (200, 204)]
    assert len(won) == 1 and len(lost) == 1, out
    loser = out[lost[0]]
    assert (loser.status, loser.code) == (409, "VERSION_CONFLICT"), loser
    assert loser.json["current_version"] == version + 1 if kind != "reject" else loser.json["current_version"] > version
    # The forced interleaving: on PostgreSQL A commits while B waits before its lock, so B — whose If-Match matched the
    # version it read before the lock — is the one refused; on SQLite B holds the write lock and wins.
    assert won == (["B"] if db.is_sqlite() else ["A"]), (won, out)

    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, site.set["id"])
        if kind == "patch":
            assert mset.version == version + 1, "exactly one accepted mutation"
            assert mset.property_capture["access_notes"] == won[0], "no silent overwrite by the stale request"
        elif kind == "submit":
            assert mset.status == "SUBMITTED"
        elif kind == "verify":
            assert mset.status == "VERIFIED"
        elif kind == "reject":
            assert mset.status == "REJECTED" and mset.rejection_reason == f"Re-measure ({won[0]})"
            drafts = s.query(MeasurementSet).filter_by(property_id=site.property["id"], status="DRAFT").count()
            assert drafts == 1, "one correction draft, not two"
        elif kind == "note_delete":
            note = s.query(MeasurementNote).execution_options(include_deleted=True).filter_by(client_ref="n-1").one()
            assert note.is_deleted and note.version == version + 1
        else:
            sp = s.get(PropertySpace, site.kitchen["id"])
            assert sp.label == f"Kitchen {won[0]}" and sp.version == version + 1


@ON
@pytest.mark.parametrize("kind", ["patch", "submit"])
def test_a_free_race_on_one_if_match_version_admits_exactly_one(app, api, factory, kind):
    """No forced pause: several requests with the same If-Match released together."""
    site = _site(api, factory, submitted=False)
    url = f"/api/v1/measurement-sets/{site.set['id']}"
    version = api.get(url).data["version"]
    clients = [_client(app, factory, api, site.lead_surveyor) for _ in range(4)]
    barrier = threading.Barrier(len(clients))
    results: list = [None] * len(clients)

    def run(i):
        barrier.wait()
        if kind == "patch":
            results[i] = clients[i].patch(url, {"property_capture": {**FULL_CAPTURE, "access_notes": f"c{i}"}},
                                          if_match=version)  # fmt: skip
        else:
            results[i] = clients[i].post(f"{url}/submit", if_match=version)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(clients))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(r is not None and r.status != 500 for r in results), results
    ok = [i for i, r in enumerate(results) if r.status == 200]
    assert len(ok) == 1, results
    for i, r in enumerate(results):
        if i not in ok:
            assert (r.status, r.code) in ((409, "VERSION_CONFLICT"), (503, "SERVICE_UNAVAILABLE")), r
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, site.set["id"])
        assert mset.version == version + 1
        if kind == "patch":
            assert mset.property_capture["access_notes"] == f"c{ok[0]}"
