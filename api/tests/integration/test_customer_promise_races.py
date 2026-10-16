"""Customer Promise concurrency (CPA-28) under forced interleavings, on SQLite and PostgreSQL.

Each test pauses the first request after its permission check (it has read the version as the user saw it) and lets a
second, conflicting request run and commit; then the first resumes. Exactly one of the two may succeed, and the data
must show only that one: no duplicate publication, no second open draft, no review landing on a version that a
conflicting decision already moved. On SQLite the first request holds the write lock across the pause, so it commits
first and the second is refused; on PostgreSQL the second commits first and the first is refused under the row lock.
"""

from __future__ import annotations

import threading

import sqlalchemy as sa

from tests.support.api import ApiClient
from tests.support.promise import BASE, ON, SENSITIVE, Team
from tests.support.race import Hold
from veda.kernel import db
from veda.modules.customer_promise import service
from veda.modules.customer_promise.models import OPEN_STATUSES, CustomerPromisePack, CustomerPromiseReview

pytestmark = ON


def _race(app, monkeypatch, first_token: str, second_token: str, first, second, *, pause_on: str = "_need"):
    """Run ``first(client)`` and ``second(client)`` with the first paused after its permission check."""
    a, b = ApiClient(app.test_client()), ApiClient(app.test_client())
    a.token, b.token = first_token, second_token
    hold = Hold()
    threads: dict[str, threading.Thread] = {}
    original = getattr(service, pause_on)

    def wrapped(*args, **kw):
        result = original(*args, **kw)
        if threading.current_thread() is threads.get("first") and not hold.reached.is_set():
            hold.wait()
        return result

    monkeypatch.setattr(service, pause_on, wrapped)
    out: dict = {}

    def run_first():
        out["first"] = first(a)

    def run_second():
        assert hold.reached.wait(timeout=10), "the first request never reached its pause"
        out["second"] = second(b)
        hold.done()

    threads["first"] = threading.Thread(target=run_first)
    threads["second"] = threading.Thread(target=run_second)
    with hold.racing(held=threads["first"], other=threads["second"]):
        for t in threads.values():
            t.start()
        for t in threads.values():
            t.join(timeout=30)
    assert "first" in out and "second" in out, out
    return out["first"], out["second"]


def test_two_publishers_publish_one_version_once(app, api, factory, monkeypatch):
    t = Team(api, factory)
    second_publisher = factory.user("ESTIMATOR", mfa=True)
    for code in ("customer_promise.view", "customer_promise.publish"):
        factory.grant(second_publisher, code)
    p = t.full_draft()
    t.act(p, "submit", t.author)
    t.review_all(p)
    p = t.act(p, "approve", t.approver)
    one, two = factory.login(api, t.publisher), factory.login(api, second_publisher)

    def publish(client):
        return client.post(f"{BASE}/versions/{p['id']}/publish", None, if_match=p["version"])

    r1, r2 = _race(app, monkeypatch, one, two, publish, publish)
    assert sorted([r1.status, r2.status]) == [200, 409], (r1, r2)
    with db.unit_of_work(write=False) as s:
        assert s.execute(sa.select(sa.func.count()).select_from(CustomerPromisePack)
                         .where(CustomerPromisePack.status == "PUBLISHED")).scalar() == 1  # fmt: skip
        sqlite = db.is_sqlite()
    assert (r1.status == 200) is sqlite  # the interleaving was forced, not avoided


def test_two_new_drafts_at_once_leave_one_open_version(app, api, factory, monkeypatch):
    t = Team(api, factory)
    other = factory.user("SALES_MANAGER", mfa=True)
    one, two = factory.login(api, t.author), factory.login(api, other)

    def create(client):
        return client.post(f"{BASE}/versions", {})

    r1, r2 = _race(app, monkeypatch, one, two, create, create, pause_on="open_version")
    assert sorted([r1.status, r2.status]) == [201, 409], (r1, r2)
    with db.unit_of_work(write=False) as s:
        opened = s.execute(sa.select(CustomerPromisePack).where(CustomerPromisePack.status.in_(OPEN_STATUSES))).all()
        assert len(opened) == 1
        sqlite = db.is_sqlite()
    assert (r1.status == 201) is sqlite


def test_conflicting_reviews_of_one_section_resolve_to_one_decision(app, api, factory, monkeypatch):
    t = Team(api, factory)
    second_legal = factory.user("ESTIMATOR", mfa=True)
    for code in ("customer_promise.view", "customer_promise.review.sensitive"):
        factory.grant(second_legal, code)
    p = t.full_draft()
    p = t.act(p, "submit", t.author)
    section = SENSITIVE[0]
    one, two = factory.login(api, t.legal), factory.login(api, second_legal)

    def approve(client):
        return client.post(f"{BASE}/versions/{p['id']}/sections/{section}/review", {"decision": "APPROVED"},
                           if_match=p["version"])  # fmt: skip

    def request_changes(client):
        return client.post(f"{BASE}/versions/{p['id']}/sections/{section}/review",
                           {"decision": "CHANGES_REQUESTED", "comment": "SYNTHETIC: please reword"},
                           if_match=p["version"])  # fmt: skip

    r1, r2 = _race(app, monkeypatch, one, two, approve, request_changes)
    assert sorted([r1.status, r2.status]) == [200, 409], (r1, r2)
    with db.unit_of_work(write=False) as s:
        rows = (
            s.execute(sa.select(CustomerPromiseReview).where(CustomerPromiseReview.pack_id == p["id"])).scalars().all()
        )
        assert len(rows) == 1
        status = s.get(CustomerPromisePack, p["id"]).status
        assert status == ("IN_REVIEW" if rows[0].decision == "APPROVED" else "DRAFT")
