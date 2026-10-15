"""CQX-01 secure proposal access: opaque links, expiry, revocation, rotation, supersession, enumeration and gating.

SYNTHETIC sites, card and policies only. Results are SYNTHETIC_VALIDATED."""

from __future__ import annotations

import re
from datetime import timedelta

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ALL_ON, load_card
from tests.support.proposal import PROPOSAL_ON, Commercial, Customer, customer, ok, setup, share, step
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context


@PROPOSAL_ON
def test_share_view_rotate_revoke_and_the_token_is_never_stored(api, factory):
    c, prop, est, q = setup(api, factory)
    g = share(c, q)
    assert g["status"] == "CREATED" and re.fullmatch(r"vsp_[A-Za-z0-9_-]{43}", g["token"])
    assert g["link"].endswith("/proposal#t=" + g["token"])  # the token lives in the fragment, never a path or query
    assert q["quotation_number"] not in g["link"] and prop["lead_id"] not in g["link"] and q["id"] not in g["link"]
    from veda.modules.customer_proposal.models import ProposalAccessGrant

    row = dbh.get(ProposalAccessGrant, g["id"])
    assert row.token_sha256 != g["token"] and g["token"] not in str(vars(row))
    listed = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants"))
    assert "token" not in listed[0] and "link" not in listed[0]

    cust = customer(api, g)
    r = cust.get()
    assert r.status == 200 and r.data["state"] == "OPEN"
    assert r.headers["Cache-Control"].startswith("no-store") and "noindex" in r.headers["X-Robots-Tag"]
    assert ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants"))[0]["status"] == "ACTIVE"

    # rotation: the old link stops at once, the new one works, same recipient and expiry
    cur = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants"))[0]
    g2 = ok(c.as_(c.sales).post(f"/api/v1/proposal-access-grants/{g['id']}/rotate", if_match=cur["version"]), 201)
    assert g2["token"] != g["token"] and g2["replaces_grant_id"] == g["id"] and g2["expires_on"] == g["expires_on"]
    r = cust.get()
    assert r.status == 410 and r.code == "PROPOSAL_LINK_REVOKED"
    cust2 = customer(api, g2)
    assert cust2.get().status == 200

    # revocation: immediate
    cur = next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants")) if x["id"] == g2["id"])
    ok(c.as_(c.sales).post(f"/api/v1/proposal-access-grants/{g2['id']}/revoke", if_match=cur["version"]))
    r = cust2.get()
    assert r.status == 410 and r.code == "PROPOSAL_LINK_REVOKED"
    # the message names nothing: no number, amount or identifier
    assert q["quotation_number"] not in str(r.json) and q["id"] not in str(r.json)


@PROPOSAL_ON
def test_invalid_malformed_and_missing_links_answer_the_same_safe_404(api, factory):
    c, prop, est, q = setup(api, factory)
    share(c, q)
    for token in (None, "", "vsp_short", "vsp_" + "A" * 43, "Bearer x", q["id"], "vsp_" + "a" * 42 + "!"):
        hdrs = {} if token is None else {"X-Veda-Proposal": token}
        r = api.get("/api/v1/public/proposal", anonymous=True, headers=hdrs)
        assert r.status == 404 and r.code == "PROPOSAL_LINK_INVALID", token
    # a staff bearer token opens nothing on the customer route
    c.as_(c.founder)
    r = api.get("/api/v1/public/proposal")
    assert r.status == 404 and r.code == "PROPOSAL_LINK_INVALID"
    # the quotation id or number in a URL opens nothing either (no enumeration surface)
    assert api.get(f"/api/v1/public/proposal/{q['id']}", anonymous=True).status == 404
    r = api.get(f"/api/v1/public/proposal?q={q['quotation_number']}", anonymous=True)
    assert r.status in (404, 422) and q["quotation_number"] not in str(r.json)  # an unknown query is refused


@PROPOSAL_ON
def test_link_expiry_is_separate_from_quotation_expiry(api, factory):
    c, prop, est, q = setup(api, factory)
    g = share(c, q, days=1)
    from veda.modules.customer_proposal.models import ProposalAccessGrant

    # the quotation is past its validity but the link is not: the proposal opens, marked expired, with no actions
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        from veda.modules.mtq_commercial.models import Quotation

        row = s.get(Quotation, q["id"])
        row.valid_until = clock.now().date() - timedelta(days=1)
    r = customer(api, g).get()
    assert r.status == 200 and r.data["state"] == "EXPIRED"
    # the link past its own expiry: refused, and recorded EXPIRED
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.get(ProposalAccessGrant, g["id"]).expires_on = clock.now() - timedelta(minutes=1)
    r = customer(api, g).get()
    assert r.status == 410 and r.code == "PROPOSAL_LINK_EXPIRED"
    # the refusal rolls back with its request; staff see the link as EXPIRED at once (the maintenance sweep records it)
    assert ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants"))[0]["status"] == "EXPIRED"


@PROPOSAL_ON
def test_one_live_link_per_recipient_and_only_issued_latest_versions_are_shared(api, factory):
    c, prop, est, q = setup(api, factory)
    share(c, q)
    r = share(c, q, code=409)
    assert r.code == "GRANT_EXISTS"
    share(c, q, kind="CO_OWNER")  # another recipient kind gets its own link
    for days in (0, 31):
        r = c.as_(c.sales).post(f"/api/v1/quotations/{q['id']}/access-grants", {"expires_in_days": days})
        assert r.status == 422
    # a draft is never shared
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    r = share(c, q2, code=409)
    assert r.code == "NOT_SHAREABLE"


@PROPOSAL_ON
def test_a_newer_version_shared_to_the_same_recipient_retires_the_old_link(api, factory):
    c, prop, est, q = setup(api, factory)
    g1 = share(c, q)
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    step(c, q2, "submit", c.estimator)
    step(c, q2, "approve", c.manager)
    q2 = ok(step(c, q2, "issue", c.manager))
    # before the new version is shared, the old link shows the version as superseded (and offers nothing)
    r = customer(api, g1).get()
    assert r.status == 200 and r.data["state"] == "SUPERSEDED"
    g2 = share(c, q2)
    r = customer(api, g1).get()
    assert r.status == 410 and r.code == "PROPOSAL_SUPERSEDED"
    assert customer(api, g2).get().data["state"] == "OPEN"
    # sharing the superseded version again is refused
    r = share(c, q, code=409)
    assert r.code in ("QUOTATION_SUPERSEDED", "NOT_SHAREABLE")


@PROPOSAL_ON
def test_staff_scope_decides_who_may_share(api, factory):
    c, prop, est, q = setup(api, factory)
    other_sales = factory.user("SALES")
    r = c.as_(other_sales).post(f"/api/v1/quotations/{q['id']}/access-grants", {"expires_in_days": 7})
    assert r.status == 404  # not their lead: existence not disclosed
    r = c.as_(c.estimator).post(f"/api/v1/quotations/{q['id']}/access-grants", {"expires_in_days": 7})
    assert r.status == 403  # the estimator previews and reviews requests but does not share
    r = c.as_(c.designer).get(f"/api/v1/quotations/{q['id']}/access-grants")
    assert r.status in (403, 404)


@PROPOSAL_ON
def test_tampered_frozen_document_is_never_shared(api, factory):
    c, prop, est, q = setup(api, factory)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        from veda.modules.mtq_commercial.models import Quotation

        row = s.get(Quotation, q["id"])
        row.snapshot = {**row.snapshot, "summary": {**row.snapshot["summary"], "total": "1.00"}}
    r = share(c, q, code=409)
    assert r.code == "SNAPSHOT_INTEGRITY_FAILED"


@ALL_ON
def test_every_cqx_route_answers_404_while_the_flag_is_off(api, factory):
    load_card()
    c = Commercial(api, factory)
    c.as_(c.founder)
    for method, path in (("POST", f"/api/v1/quotations/{'0' * 32}/access-grants"),
                         ("GET", f"/api/v1/quotations/{'0' * 32}/access-grants"),
                         ("POST", f"/api/v1/proposal-access-grants/{'0' * 32}/revoke"),
                         ("GET", "/api/v1/public/proposal"), ("GET", "/api/v1/public/proposal/"),
                         ("POST", "/api/v1/public/proposal"), ("DELETE", "/api/v1/public/proposal")):  # fmt: skip
        r = api.call(method, path, {} if method != "GET" else None)
        assert r.status == 404 and r.code == "NOT_FOUND", (method, path, r)
    me = ok(api.get("/api/v1/auth/me"))
    assert me["features"]["customer_proposal"] is False


@PROPOSAL_ON
def test_access_events_are_recorded_without_tokens(api, factory):
    c, prop, est, q = setup(api, factory)
    g = share(c, q)
    cust: Customer = customer(api, g)
    cust.get()
    cust.get()  # a repeat view inside the window updates counters only
    from veda.modules.customer_proposal.models import ProposalAccessGrant, ProposalEvent
    from veda.platform.notifications.models import OutboxEvent

    with db.unit_of_work() as s:
        codes = [e.event_code for e in s.execute(sa.select(ProposalEvent).where(ProposalEvent.quotation_id == q["id"])
                                                 .order_by(ProposalEvent.created_on)).scalars()]  # fmt: skip
        outbox = [o.event_type for o in s.execute(sa.select(OutboxEvent)).scalars()]
        everything = str([(e.detail) for e in s.execute(sa.select(ProposalEvent)).scalars()]) + str(
            [o.payload for o in s.execute(sa.select(OutboxEvent)).scalars()]
        )
        assert s.get(ProposalAccessGrant, g["id"]).view_count == 2
    assert codes == ["SHARED", "VIEWED"]
    assert "proposal.shared" in outbox and outbox.count("proposal.viewed") == 1
    assert g["token"] not in everything
