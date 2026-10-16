"""B1-PE-06: a write into a draft never lands in a revision a concurrent submit has already checked.

Each write into a set's content takes the property lock submit takes and re-reads the set's status under it. The tests
force the dangerous interleaving: the writer reads the set as DRAFT and passes its checks, then pauses; the submit runs
and commits; the writer resumes. The writer must then be refused (the set is frozen), or — where the engine or the
operation already serialises the two (SQLite BEGIN IMMEDIATE; a sync batch locks up front) — the writer must commit
first and the submit's checks must include its write. A SUBMITTED revision never holds a row written after it.
"""

from __future__ import annotations

import hashlib
import threading

import pytest
import sqlalchemy as sa

from tests.support.api import ApiClient
from tests.support.mtq import Site, jpeg, kitchen_payload, photo
from tests.support.race import Hold
from veda.kernel import db
from veda.modules.attachments import service as att_service
from veda.modules.attachments.models import Attachment
from veda.modules.mtq import sets
from veda.modules.mtq.models import MeasurementNote, MeasurementSet, SpaceMeasurement

ON = pytest.mark.settings(mtq_site_enabled=True)


def _ready_site(api, factory) -> tuple[Site, dict]:
    """A FULL draft ready to submit, and an extra out-of-scope space whose measurement never changes completeness."""
    site = Site(api, factory)
    extra = site.as_(site.sales).post(f"/api/v1/properties/{site.property['id']}/spaces",
                                      {"space_type_code": "KITCHEN", "label": "Utility", "is_in_scope": False}).data  # fmt: skip
    site.open_set(survey_level_code="FULL", unit_system_code="MM")
    site.capture_full()
    return site, extra


def _write(kind: str, client: ApiClient, set_id: str, extra: dict):
    """The write under test; returns (accepted, refusal code)."""
    if kind == "space":
        r = client.put(
            f"/api/v1/measurement-sets/{set_id}/spaces/{extra['id']}", kitchen_payload(client_ref="sm-extra")
        )
        return r.status == 201, (r.status, r.code)
    if kind == "note":
        r = client.post(f"/api/v1/measurement-sets/{set_id}/notes",
                        {"client_ref": "race-note", "note_type_code": "RISK", "body": "Seepage behind the counter"})  # fmt: skip
        return r.status == 201, (r.status, r.code)
    if kind == "sync_space":
        op = {"op_id": "op-1", "type": "space", "space_id": extra["id"], "data": kitchen_payload(client_ref="sm-extra")}
        r = client.post(f"/api/v1/measurement-sets/{set_id}/sync", {"batch_id": "race", "operations": [op]})
        assert r.status == 200, r
        res = r.data["results"][0]
        return res["status"] == "APPLIED", (res.get("http_status"), res["status"])
    data = jpeg()
    r = client.post("/api/v1/attachments", {"entity_type": "measurement_set", "entity_id": set_id,
                                            "mime_type": "image/jpeg", "byte_size": len(data),
                                            "sha256": hashlib.sha256(data).hexdigest(), "category_code": "SITE_PHOTO",
                                            "client_ref": "race-photo"})  # fmt: skip
    return r.status == 201, (r.status, r.code)


def _rows(kind: str, s, set_id: str) -> list:
    if kind in ("space", "sync_space"):
        q = sa.select(SpaceMeasurement).where(SpaceMeasurement.measurement_set_id == set_id,
                                              SpaceMeasurement.client_ref == "sm-extra")  # fmt: skip
    elif kind == "note":
        q = sa.select(MeasurementNote).where(MeasurementNote.measurement_set_id == set_id,
                                             MeasurementNote.client_ref == "race-note")  # fmt: skip
    else:
        q = sa.select(Attachment).where(Attachment.entity_id == set_id, Attachment.client_ref == "race-photo")
    return s.execute(q).scalars().all()


@ON
@pytest.mark.parametrize("kind", ["space", "note", "sync_space", "attachment"])
def test_a_write_racing_submit_lands_before_it_or_is_refused(app, api, factory, monkeypatch, kind):
    site, extra = _ready_site(api, factory)
    set_id = site.set["id"]
    token = factory.login(api, site.lead_surveyor)
    writer, submitter = ApiClient(app.test_client()), ApiClient(app.test_client())
    writer.token = submitter.token = token
    version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]

    hold = Hold()
    threads: dict[str, threading.Thread] = {}

    def pause_writer():
        if threading.current_thread() is threads.get("writer"):
            hold.wait()

    if kind == "attachment":  # ATT: after the entity was resolved (writable) and the caller's scope checked
        original_scope = att_service.require_lead_scope

        def scope_then_pause(*a, **kw):
            original_scope(*a, **kw)
            pause_writer()

        monkeypatch.setattr(att_service, "require_lead_scope", scope_then_pause)
    else:  # MTQ: after the writer read the set as DRAFT and checked its capture scope
        original_capture = sets._require_capture

        def capture_then_pause(s, ctx, prop):
            original_capture(s, ctx, prop)
            pause_writer()

        monkeypatch.setattr(sets, "_require_capture", capture_then_pause)

    outcome: dict = {}

    def write():
        outcome["write"] = _write(kind, writer, set_id, extra)

    def submit():
        assert hold.reached.wait(timeout=10), "the writer never reached its pause"
        outcome["submit"] = submitter.post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=version)
        hold.done()

    threads["writer"] = threading.Thread(target=write)
    threads["submitter"] = threading.Thread(target=submit)
    with hold.racing(held=threads["writer"], other=threads["submitter"]):
        for t in threads.values():
            t.start()
        for t in threads.values():
            t.join(timeout=30)
    assert "write" in outcome and "submit" in outcome, outcome
    assert outcome["submit"].status == 200, outcome["submit"]
    accepted, refusal = outcome["write"]

    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, set_id)
        assert mset.status == "SUBMITTED"
        rows = _rows(kind, s, set_id)
        measured = s.execute(
            sa.select(sa.func.count(SpaceMeasurement.id)).where(SpaceMeasurement.measurement_set_id == set_id)
        ).scalar()
        assert mset.summary["spaces"] == measured, "submit's summary covers every space measurement in the revision"
        if accepted:  # committed first: the submit saw it
            assert len(rows) == 1 and rows[0].created_on <= mset.submitted_on
        else:  # refused under the lock: nothing landed in the sealed revision
            assert rows == [], f"a {kind} write landed in a SUBMITTED revision"
            frozen = (409, "SET_FROZEN") if kind != "sync_space" else (409, "FROZEN")
            assert refusal == (frozen if kind != "attachment" else (409, "ENTITY_FROZEN")), refusal
        sqlite = db.is_sqlite()
    # The forced interleaving is exercised, not dodged: PostgreSQL lets the submit commit while the writer is paused
    # (so the writer must be refused); SQLite and the sync batch hold their lock across the pause (writer first).
    assert accepted is (sqlite or kind == "sync_space"), (kind, accepted, refusal)


@ON
@pytest.mark.parametrize("kind", ["space", "note"])
def test_a_free_race_of_writes_and_submit_never_seals_an_unchecked_row(app, api, factory, kind):
    """No forced pause: several writers released together with the submit; whatever the order, the invariant holds."""
    site, extra = _ready_site(api, factory)
    set_id = site.set["id"]
    token = factory.login(api, site.lead_surveyor)
    clients = [ApiClient(app.test_client()) for _ in range(3)]
    for c in clients:
        c.token = token
    version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]
    barrier = threading.Barrier(len(clients))
    results: list = [None] * len(clients)

    def run(i):
        barrier.wait()
        if i == 0:
            results[i] = clients[i].post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=version).status
        else:
            results[i] = _write(kind, clients[i], set_id, extra)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(clients))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert results[0] == 200, results
    with db.unit_of_work(write=False) as s:
        mset = s.get(MeasurementSet, set_id)
        rows = _rows(kind, s, set_id)
        measured = s.execute(
            sa.select(sa.func.count(SpaceMeasurement.id)).where(SpaceMeasurement.measurement_set_id == set_id)
        ).scalar()
        assert mset.status == "SUBMITTED" and mset.summary["spaces"] == measured
        accepted = [r for r in results[1:] if r[0]]
        assert len(rows) == (1 if accepted else 0), (results, rows)
        for r in results[1:]:
            assert r[0] or r[1][0] in (200, 409, 428), results  # 200: same note again; 428: space now exists


@ON
def test_a_draft_rule_withdrawal_racing_submit_lands_before_it_or_is_refused(app, api, factory, monkeypatch):
    """Who may withdraw a set's photo changes at submission (uploader, then a verifier with a reason): the rule is
    decided under the lock, so the uploader's withdrawal never removes a photo from a revision already submitted."""
    site, _ = _ready_site(api, factory)
    set_id = site.set["id"]
    shot = photo(site.as_(site.lead_surveyor), "measurement_set", set_id)
    token = factory.login(api, site.lead_surveyor)
    writer, submitter = ApiClient(app.test_client()), ApiClient(app.test_client())
    writer.token = submitter.token = token
    version = api.get(f"/api/v1/measurement-sets/{set_id}").data["version"]
    hold = Hold()
    threads: dict[str, threading.Thread] = {}
    original_resolve = att_service._resolve

    def resolve_then_pause(*a, **kw):  # the first resolve is the pre-lock read of the withdrawal rule
        out = original_resolve(*a, **kw)
        if threading.current_thread() is threads.get("writer") and not hold.reached.is_set():
            hold.wait()
        return out

    monkeypatch.setattr(att_service, "_resolve", resolve_then_pause)
    outcome: dict = {}

    def write():
        outcome["write"] = writer.post(f"/api/v1/attachments/{shot['id']}/withdraw", {}, if_match=shot["version"])

    def submit():
        assert hold.reached.wait(timeout=10), "the writer never reached its pause"
        outcome["submit"] = submitter.post(f"/api/v1/measurement-sets/{set_id}/submit", if_match=version)
        hold.done()

    threads["writer"] = threading.Thread(target=write)
    threads["submitter"] = threading.Thread(target=submit)
    with hold.racing(held=threads["writer"], other=threads["submitter"]):
        for t in threads.values():
            t.start()
        for t in threads.values():
            t.join(timeout=30)
    assert outcome["submit"].status == 200, outcome["submit"]
    r = outcome["write"]
    with db.unit_of_work(write=False) as s:
        att = s.get(Attachment, shot["id"])
        mset = s.get(MeasurementSet, set_id)
        assert mset.status == "SUBMITTED"
        if r.status == 200:  # withdrawn while still a draft
            assert att.retention_state == "WITHDRAWN" and att.withdrawn_on <= mset.submitted_on
        else:  # decided on the submitted state: only a verifier, with a reason
            assert (r.status, r.code) == (403, "PERMISSION_DENIED"), r
            assert att.retention_state == "ACTIVE"
        sqlite = db.is_sqlite()
    assert (r.status == 200) is sqlite, r
