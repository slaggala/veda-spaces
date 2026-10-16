"""Customer Project Portal: release gate, staff-granted access and passwordless sign-in (CPP-001, CPP-002).
SYNTHETIC data only."""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.portal import ON, PUBLIC, Portal
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.modules.portal import identity
from veda.modules.portal.models import PortalAccount, PortalEvent, PortalSession, PortalSignIn

pytestmark = ON
ROUTES = (("POST", f"{PUBLIC}/sign-in"), ("POST", f"{PUBLIC}/session"), ("POST", f"{PUBLIC}/sign-out"),
          ("GET", f"{PUBLIC}/home"), ("GET", f"{PUBLIC}/properties/x"), ("GET", f"{PUBLIC}/quotations/x"),
          ("PATCH", f"{PUBLIC}/home"), ("GET", "/api/v1/leads/x/portal-access"),
          ("POST", "/api/v1/leads/x/portal-access"), ("POST", "/api/v1/portal-access/x/revoke"))  # fmt: skip


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                      customer_portal_enabled=False)  # fmt: skip
def test_every_portal_route_answers_404_while_the_flag_is_off(api, factory):
    t = Portal(api, factory)
    t.as_(t.founder)
    for method, path in ROUTES:
        r = api.call(method, path, {} if method in ("POST", "PATCH") else None)
        assert r.status == 404, (method, path, r)
        r = api.call(method, path, {} if method in ("POST", "PATCH") else None, anonymous=True)
        assert r.status == 404, (method, path, r)
    assert ok_me(api)["features"]["customer_portal"] is False


def ok_me(api):
    r = api.get("/api/v1/auth/me")
    assert r.status == 200, r
    return r.data


def test_staff_give_access_and_the_customer_signs_in_by_the_emailed_link(api, factory):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    r = t.grant(prop["lead_id"], "Asha.Customer@Example.test", display_name="Asha")
    row = r.data[0]
    assert row["status"] == "ACTIVE" and row["relationship"] == "PRIMARY_CUSTOMER"
    assert row["account"]["email"] == "asha.customer@example.test" and row["account"]["last_signed_in_on"] is None
    assert t.grant(prop["lead_id"], "asha.customer@example.test", status=409).code == "PORTAL_ACCESS_EXISTS"
    me = t.sign_in("asha.customer@example.test")
    home = me.home()
    assert home.status == 200 and home.data["customer"]["name"] == "Asha"
    assert [p["property"]["reference"] for e in home.data["enquiries"] for p in e["properties"]] == [
        prop["property_number"]
    ]
    # the link works once
    token = t.link_token("asha.customer@example.test")
    r = api.post(f"{PUBLIC}/session", {"token": token}, anonymous=True)
    assert r.status == 400 and r.code == "PORTAL_LINK_INVALID"
    assert t.access(prop["lead_id"])[0]["account"]["last_signed_in_on"] is not None
    codes = [e.event_code for e in dbh.rows(sa.select(PortalEvent).order_by(PortalEvent.created_on))]
    assert codes[:3] == ["ACCESS_GRANTED", "SIGN_IN_LINK_SENT", "SIGNED_IN"] and "SIGN_IN_REFUSED" in codes


def test_sign_in_requests_never_disclose_whether_an_email_has_access(api, factory, monkeypatch):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    t.grant(prop["lead_id"], "known@example.test")
    t.sign_in("known@example.test")
    api.post(f"{PUBLIC}/sign-in", {"email": "known@example.test"}, anonymous=True)
    assert t.emails_to("known@example.test") == 1  # at most one link a minute: the invitation was just sent
    monkeypatch.setattr(identity, "RESEND_GAP", timedelta(0))
    for email in ("known@example.test", "stranger@example.test"):
        r = api.post(f"{PUBLIC}/sign-in", {"email": email}, anonymous=True)
        assert r.status == 202 and r.data["sent"] is True and r.data["message"].startswith("If this email")
    assert t.emails_to("stranger@example.test") == 0
    assert t.emails_to("known@example.test") == 2  # the invitation, then one sign-in link
    rows = dbh.rows(sa.select(PortalSignIn).order_by(PortalSignIn.created_on))
    assert rows[0].used_on is not None and rows[1].used_on is None and rows[1].purpose == "SIGN_IN"


def test_a_newer_link_invalidates_the_older_and_an_expired_link_is_refused(api, factory, monkeypatch):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    t.grant(prop["lead_id"], "two@example.test")
    first = t.link_token("two@example.test")
    t.sign_in("two@example.test", first)
    monkeypatch.setattr(identity, "RESEND_GAP", timedelta(0))
    api.post(f"{PUBLIC}/sign-in", {"email": "two@example.test"}, anonymous=True)
    second = t.link_token("two@example.test")
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        for row in s.execute(sa.select(PortalSignIn).where(PortalSignIn.used_on.is_(None))).scalars():
            row.expires_on = clock.now() - timedelta(minutes=1)
    r = api.post(f"{PUBLIC}/session", {"token": second}, anonymous=True)
    assert r.status == 400 and r.code == "PORTAL_LINK_INVALID"
    for bad in ("", "x" * 43, "not a token", "vpp_" + "a" * 43):
        r = api.post(f"{PUBLIC}/session", {"token": bad} if bad else {"token": "?"}, anonymous=True)
        assert r.status in (400, 422), r


def test_portal_and_staff_credentials_never_cross(api, factory):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    me = t.invite(prop["lead_id"], "cross@example.test")
    # a staff bearer token is not a portal session
    t.as_(t.founder)
    assert api.get(f"{PUBLIC}/home").status == 401
    # a portal session is not a staff credential
    for path in (
        "/api/v1/auth/me",
        f"/api/v1/leads/{prop['lead_id']}",
        f"/api/v1/leads/{prop['lead_id']}/portal-access",
    ):
        assert api.get(path, headers={"X-Veda-Portal": me.token}, anonymous=True).status == 401
        assert api.get(path, headers={"Authorization": f"Bearer {me.token}"}, anonymous=True).status == 401
    # no session, a malformed one, an unknown one
    for token in (None, "nonsense", "vpp_" + "A" * 43):
        assert me.get(f"{PUBLIC}/home", token=token or "").status == 401


def test_sign_out_and_revocation_end_access_from_the_next_request(api, factory, monkeypatch):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    me = t.invite(prop["lead_id"], "rev@example.test")
    assert me.call("POST", f"{PUBLIC}/sign-out").status == 200
    assert me.home().status == 401
    monkeypatch.setattr(identity, "RESEND_GAP", timedelta(0))
    api.post(f"{PUBLIC}/sign-in", {"email": "rev@example.test"}, anonymous=True)
    me = t.sign_in("rev@example.test")
    assert me.property(prop["id"]).status == 200
    row = t.access(prop["lead_id"])[0]
    r = t.as_(t.c.sales).post(f"/api/v1/portal-access/{row['id']}/revoke", {}, if_match=row["version"])
    assert r.status == 200 and r.data[0]["status"] == "REVOKED" and r.data[0]["revoke_reason_code"] == "STAFF_REVOKED"
    assert me.home().status == 401 and me.property(prop["id"]).status == 401
    assert all(s.ended_on is not None for s in dbh.rows(sa.select(PortalSession)))
    r = t.as_(t.c.sales).post(f"/api/v1/portal-access/{row['id']}/revoke", {}, if_match=r.data[0]["version"])
    assert r.status == 409
    # no sign-in link is sent once access is gone
    api.post(f"{PUBLIC}/sign-in", {"email": "rev@example.test"}, anonymous=True)
    assert t.emails_to("rev@example.test") == 2


def test_staff_access_management_needs_the_capability_within_lead_scope(api, factory):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    lead = prop["lead_id"]
    other_sales = factory.user("SALES")
    designer = factory.user("DESIGNER")
    assert t.as_(designer).get(f"/api/v1/leads/{lead}/portal-access").status == 403
    assert t.as_(designer).post(f"/api/v1/leads/{lead}/portal-access", {"email": "d@example.test"}).status == 403
    assert t.as_(other_sales).get(f"/api/v1/leads/{lead}/portal-access").status == 404  # not their enquiry
    assert t.as_(other_sales).post(f"/api/v1/leads/{lead}/portal-access", {"email": "d@example.test"}).status == 404
    t.grant(lead, "owner-sales@example.test")  # the enquiry's own consultant (SALES, OWN)
    row = t.access(lead)[0]
    r = t.as_(other_sales).post(f"/api/v1/portal-access/{row['id']}/revoke", {}, if_match=row["version"])
    assert r.status == 404
    r = t.grant(lead, "bad", status=422)
    assert r.json["errors"][0]["field"] == "email"
    r = t.as_(t.c.sales).post(
        f"/api/v1/leads/{lead}/portal-access", {"email": "x@example.test", "relationship": "BOSS"}
    )
    assert r.status == 422


def test_erasing_the_enquiry_ends_access_and_erases_an_account_left_without_any(api, factory):
    t = Portal(api, factory)
    prop_a, _, _ = t.issued("2BHK")
    prop_b, _, _ = t.issued("3BHK")
    solo = t.invite(prop_a["lead_id"], "solo@example.test")
    t.grant(prop_a["lead_id"], "both@example.test")
    t.grant(prop_b["lead_id"], "both@example.test")
    both = t.sign_in("both@example.test")
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, prop_a["lead_id"]), legal_basis="SYNTHETIC erasure test",
                               request_ref=None)  # fmt: skip
    assert solo.home().status == 401
    home = both.home()
    assert home.status == 200
    assert [p["property"]["reference"] for e in home.data["enquiries"] for p in e["properties"]] == [
        prop_b["property_number"]
    ]
    assert both.property(prop_a["id"]).status == 404
    accounts = {a.email_normalized: a for a in dbh.rows(sa.select(PortalAccount))}
    assert "solo@example.test" not in accounts and "both@example.test" in accounts
    erased = [a for a in accounts.values() if a.erased_on is not None]
    assert len(erased) == 1 and erased[0].status == "DISABLED" and erased[0].display_name == "[erased]"
