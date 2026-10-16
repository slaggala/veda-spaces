"""Customer Project Portal: one customer never reaches another's data (CPP-003). SYNTHETIC data only.

Customer A and customer B each have their own enquiry, property and quotation. Every portal route is tried with the
other customer's identifiers, with guessed ones, without a session, and on rows that exist but were never issued to
the customer; each answers exactly as for a row that does not exist (404) or asks for a session (401).
"""

from __future__ import annotations

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok, step
from tests.support.portal import ON, PUBLIC, Portal
from veda.modules.mtq_commercial.models import Quotation

pytestmark = ON


def _two(t: Portal):
    prop_a, est_a, q_a = t.issued("2BHK")
    prop_b, _, q_b = t.issued("3BHK")
    a = t.invite(prop_a["lead_id"], "a@example.test")
    b = t.invite(prop_b["lead_id"], "b@example.test")
    return (prop_a, est_a, q_a, a), (prop_b, q_b, b)


def test_customer_a_never_reads_customer_b(api, factory):
    t = Portal(api, factory)
    (prop_a, _, q_a, a), (prop_b, q_b, b) = _two(t)
    assert a.property(prop_a["id"]).status == 200 and a.quotation(q_a["id"]).status == 200
    for r in (a.property(prop_b["id"]), a.quotation(q_b["id"]), b.property(prop_a["id"]), b.quotation(q_a["id"])):
        assert r.status == 404 and r.code == "NOT_FOUND", r
    for guessed in ("00000000000070008000000000000001", prop_b["lead_id"], q_b["id"]):  # well-formed: not found
        assert a.property(guessed).status == 404
    for guessed in ("00000000000070008000000000000001", prop_b["lead_id"], prop_b["id"]):
        assert a.quotation(guessed).status == 404
    for malformed in ("x" * 32, "../home", "1 OR 1=1"):  # refused before any lookup; nothing disclosed
        assert a.property(malformed).status in (404, 422)
        assert a.quotation(malformed).status in (404, 422)
    home_a = a.home().data
    seen = {p["property"]["reference"] for e in home_a["enquiries"] for p in e["properties"]}
    assert seen == {prop_a["property_number"]} and prop_b["property_number"] not in str(home_a)
    assert q_b["id"] not in str(home_a) and q_b["id"] not in str(a.property(prop_a["id"]).data)


def test_without_a_session_nothing_is_reachable(api, factory):
    t = Portal(api, factory)
    (prop_a, _, q_a, a), _ = _two(t)
    for path in (f"{PUBLIC}/home", f"{PUBLIC}/properties/{prop_a['id']}", f"{PUBLIC}/quotations/{q_a['id']}"):
        r = api.get(path, anonymous=True)
        assert r.status == 401 and r.code == "PORTAL_SESSION_INVALID", r
        assert "a@example.test" not in str(r.json)
    assert api.call("POST", f"{PUBLIC}/sign-out", None, anonymous=True).status == 401


def test_a_quotation_never_issued_to_the_customer_is_not_reachable_by_id(api, factory):
    t = Portal(api, factory)
    (prop_a, est_a, q_a, a), _ = _two(t)
    # a new version in preparation (DRAFT, then INTERNAL_REVIEW, then APPROVED): never the customer's
    v2 = ok(step(t.c, q_a, "versions", t.c.estimator, {"cost_estimate_id": est_a["id"]}, code=201))
    assert a.quotation(v2["id"]).status == 404
    step(t.c, v2, "submit", t.c.estimator)
    assert a.quotation(v2["id"]).status == 404
    step(t.c, v2, "approve", t.c.manager)
    assert a.quotation(v2["id"]).status == 404
    view = a.property(prop_a["id"]).data
    assert v2["id"] not in str(view)
    assert {d["id"] for d in view["documents"]} == {q_a["id"]}


def test_portal_routes_change_nothing_commercial(api, factory):
    t = Portal(api, factory)
    (prop_a, _, q_a, a), _ = _two(t)
    before = dbh.rows(sa.select(Quotation).order_by(Quotation.id))
    snap = [(q.id, q.status, q.version, q.total_minor, q.snapshot_sha256, q.updated_on) for q in before]
    a.home(), a.property(prop_a["id"]), a.quotation(q_a["id"])
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for path in (f"{PUBLIC}/quotations/{q_a['id']}", f"{PUBLIC}/properties/{prop_a['id']}", f"{PUBLIC}/home"):
            assert a.call(method, path, {}).status in (404, 405)
    after = dbh.rows(sa.select(Quotation).order_by(Quotation.id))
    assert [(q.id, q.status, q.version, q.total_minor, q.snapshot_sha256, q.updated_on) for q in after] == snap
