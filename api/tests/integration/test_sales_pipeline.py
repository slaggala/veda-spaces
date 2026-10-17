"""Sales pipeline (SCA-005/006): the flag, RBAC and OWN scope, the evidence-derived stage through the real flows
(activity, visit, quotation, proposal link, acceptance, won), claims without records, quoted-amount gating, and that
no internal or customer text leaks. SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.project import Projects, install, no_four_eyes
from tests.support.proposal import customer, share
from tests.support.sales import FLAGS, INTERNAL_KEYS, SALES, keys, progression

pytestmark = pytest.mark.settings(**FLAGS)


@pytest.fixture
def team(api, factory):
    install(no_four_eyes())
    t = Projects(api, factory)
    yield t
    install(None)


def _lead(api, factory, user, **fields) -> dict:
    factory.login(api, user)
    return factory.lead(api, user.token, **fields)


def test_every_route_is_404_before_authentication_while_the_flag_is_off(app, api, factory):
    from veda.config import settings

    settings().sales_experience_enabled = False
    try:
        user = factory.user(founder=True)
        factory.login(api, user)
        for path in (f"{SALES}/pipeline", f"{SALES}/funnel", f"{SALES}/demo", f"{SALES}/leads/x/progression"):
            assert api.get(path).status == 404, path
            assert api.get(path, anonymous=True).status == 404, path
        r = api.post("/api/v1/public/acquisition/events", {"event": "site_visit", "client": "c" * 20}, anonymous=True)
        assert r.status == 404
    finally:
        settings().sales_experience_enabled = True


def test_default_grants_follow_the_sales_roles():
    from veda.platform.rbac.registry import MATRIX

    assert MATRIX["sales.pipeline.view"] == {"FOUNDER": "A", "ADMIN": "A", "SALES": "O", "SALES_MANAGER": "A"}
    assert MATRIX["sales.funnel.view"] == {"FOUNDER": "✓", "ADMIN": "✓", "SALES_MANAGER": "✓"}
    assert MATRIX["sales.demo.view"] == {"FOUNDER": "✓", "ADMIN": "✓", "SALES": "✓", "SALES_MANAGER": "✓"}


def test_roles_without_a_grant_are_refused(api, factory):
    for role in ("ACCOUNTANT", "DESIGNER", "SURVEYOR", "ESTIMATOR"):
        user = factory.user(role, mfa=role == "ACCOUNTANT")
        factory.login(api, user)
        for path in (f"{SALES}/pipeline", f"{SALES}/funnel", f"{SALES}/demo"):
            assert api.get(path).status == 403, (role, path)
    sales = factory.user("SALES")
    factory.login(api, sales)
    assert api.get(f"{SALES}/funnel").status == 403  # the funnel is a whole-business aggregate
    assert api.get(f"{SALES}/demo").status == 200
    assert api.get(f"{SALES}/pipeline").status == 200


def test_own_scope_shows_only_the_actors_leads_and_never_discloses_others(api, factory):
    a, b = factory.user("SALES"), factory.user("SALES")
    mine = _lead(api, factory, a)
    theirs = _lead(api, factory, b)
    factory.login(api, a)
    rows = ok(api.get(f"{SALES}/pipeline"))
    assert [r["lead"]["id"] for r in rows] == [mine["id"]]
    assert api.get(f"{SALES}/leads/{theirs['id']}/progression").status == 404
    assert api.get(f"{SALES}/leads/{mine['id']}/progression").status == 200
    manager = factory.user("SALES_MANAGER", mfa=True)
    factory.login(api, manager)
    assert {r["lead"]["id"] for r in ok(api.get(f"{SALES}/pipeline"))} >= {mine["id"], theirs["id"]}


def test_a_new_lead_starts_new_and_a_logged_meeting_is_a_consultation(api, factory):
    sales = factory.user("SALES")
    lead = _lead(api, factory, sales, source_code="REFERRAL")
    p = progression(api, lead["id"])
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("NEW", "NONE")
    assert p["channel"]["code"] == "REFERRAL" and p["source"]["code"] == "REFERRAL"
    assert {a["code"] for a in p["attention"]} == {"NO_FOLLOW_UP_PLANNED"}  # created just now: not quiet
    assert p["quoted"] is None and p["facts"]["quotation"] is None and p["facts"]["visits"] == []
    r = api.post(f"/api/v1/leads/{lead['id']}/activities",
                 {"activity_type": "CALL", "subject": "First call", "activity_status": "COMPLETED"})  # fmt: skip
    assert r.status == 201, r
    p = progression(api, lead["id"])
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("CONTACTED", "ACTIVITY")
    r = api.post(f"/api/v1/leads/{lead['id']}/activities",
                 {"activity_type": "MEETING", "subject": "Design consultation", "activity_status": "COMPLETED"})  # fmt: skip
    assert r.status == 201, r
    p = progression(api, lead["id"])
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("CONSULTATION", "ACTIVITY")
    assert p["facts"]["consultation_on"] is not None


def test_a_staff_status_with_no_record_is_shown_as_a_claim(api, factory):
    sales = factory.user("SALES")
    lead = _lead(api, factory, sales)
    r = api.post(f"/api/v1/leads/{lead['id']}/status", {"to_status": "QUOTATION_SENT"}, if_match=lead["version"])
    assert r.status == 200, r
    p = progression(api, lead["id"])
    assert p["stage"] == {"code": "QUOTATION_ISSUED", "label": "Quotation issued", "basis": "LEAD_STATUS",
                          "basis_label": "Status recorded by staff", "claimed_without_record": True}  # fmt: skip


def test_the_measurement_quotation_proposal_and_acceptance_records_drive_the_stage(team, api, factory):
    t = team
    prop, est, q = t.issued()
    lead_id = prop["lead_id"]
    founder = t.founder
    t.as_(founder)
    p = progression(api, lead_id)
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("QUOTATION_ISSUED", "QUOTATION_RECORD")
    assert p["facts"]["visits"] and all(v["status"] != "CANCELLED" for v in p["facts"]["visits"])
    assert p["facts"]["quotation"]["status"] == "ISSUED" and "total_minor" not in p["facts"]["quotation"]
    assert p["quoted"] == {"amount_minor": q["total_minor"], "currency": "INR"}  # the founder holds quotation.read
    assert p["customer_action"] == "Decision on the issued quotation"
    assert p["facts"]["proposal"] is None and p["lead"]["status"] == "QUOTATION_SENT"

    grant = share(t.c, q)
    t.as_(founder)
    p = progression(api, lead_id)
    assert p["facts"]["proposal"]["links"] == 1 and p["facts"]["proposal"]["first_viewed_on"] is None
    assert "PROPOSAL_NOT_OPENED" in {a["code"] for a in p["attention"]}
    assert p["stage"]["code"] == "QUOTATION_ISSUED"
    assert customer(api, grant).get("").status == 200  # the customer opens the link
    t.as_(founder)
    p = progression(api, lead_id)
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("CUSTOMER_CONSIDERING", "PROPOSAL_RECORD")
    assert p["facts"]["proposal"]["first_viewed_on"] is not None and p["facts"]["proposal"]["view_count"] == 1

    from tests.support.commercial import step

    q = ok(step(t.c, q, "decision", t.c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}))
    t.as_(founder)
    p = progression(api, lead_id)
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("ACCEPTED", "QUOTATION_RECORD")
    assert (
        p["facts"]["accepted"]["method"] == "SIGNED_COPY"
        and p["facts"]["accepted"]["quotation_number"] == q["quotation_number"]
    )
    assert "ACCEPTED_NOT_CLOSED" in {a["code"] for a in p["attention"]} and p["customer_action"] is None
    # The lead is still open: nothing here changed its status. Staff close it through the lead's own endpoint.
    lead = ok(api.get(f"/api/v1/leads/{lead_id}"))
    assert lead["status"] in ("QUOTATION_SENT", "NEGOTIATION")
    r = api.post(f"/api/v1/leads/{lead_id}/status", {"to_status": "WON"}, if_match=lead["version"])
    assert r.status == 200, r
    p = progression(api, lead_id)
    assert (p["stage"]["code"], p["stage"]["basis"], p["stage"]["claimed_without_record"]) == (
        "WON",
        "LEAD_STATUS",
        False,
    )
    assert p["attention"] == []
    rows = ok(
        api.get(
            f"{SALES}/pipeline",
        )
    )
    assert lead_id not in {r["lead"]["id"] for r in rows}  # the default listing is the open pipeline
    won = ok(api.get(f"{SALES}/pipeline?status=won"))
    assert lead_id in {r["lead"]["id"] for r in won}


def test_a_declined_quotation_is_shown_and_the_lead_can_be_lost_without_a_reason(team, api, factory):
    from tests.support.commercial import step

    t = team
    prop, est, q = t.issued()
    lead_id = prop["lead_id"]
    ok(step(t.c, q, "decision", t.c.sales, {"decision": "REJECTED", "method": "STAFF_RECORDED"}))
    t.as_(t.founder)
    p = progression(api, lead_id)
    assert (p["stage"]["code"], p["stage"]["basis"]) == ("QUOTATION_DECLINED", "QUOTATION_RECORD")
    assert "DECLINED_STILL_OPEN" in {a["code"] for a in p["attention"]}
    lead = ok(api.get(f"/api/v1/leads/{lead_id}"))
    r = api.post(f"/api/v1/leads/{lead_id}/status", {"to_status": "LOST", "lost_reason_code": "NOT_PROVIDED"},
                 if_match=lead["version"])  # fmt: skip
    assert r.status == 200, r
    p = progression(api, lead_id)
    assert p["stage"]["code"] == "LOST" and p["closed"]["lost_reason"] == {
        "code": "NOT_PROVIDED",
        "label": "Not provided",
    }


def test_quoted_amount_is_withheld_without_quotation_read(team, api, factory):
    t = team
    prop, est, q = t.issued()
    lead_id = prop["lead_id"]
    viewer = factory.user("SURVEYOR")  # pipeline access without quotation.read
    factory.grant(viewer, "sales.pipeline.view", scope="ALL")
    t.as_(viewer)
    p = progression(api, lead_id)
    assert p["quoted"] == {"withheld": True}
    assert "total_minor" not in keys(p)


def test_no_internal_or_customer_text_leaks_into_the_pipeline(team, api, factory):
    t = team
    prop, est, q = t.issued()
    t.as_(t.founder)
    rows = ok(api.get(f"{SALES}/pipeline?status=all"))
    found = keys(rows)
    assert not (found & set(INTERNAL_KEYS)), found & set(INTERNAL_KEYS)
    assert all("name" in r["lead"] and "phone" not in r["lead"] for r in rows)


def test_filters_and_meta(api, factory):
    manager = factory.user("SALES_MANAGER", mfa=True)
    sales = factory.user("SALES")
    a = _lead(api, factory, sales, source_code="INSTAGRAM")
    b = _lead(api, factory, sales, source_code="PHONE")
    r = api.post(f"/api/v1/leads/{b['id']}/status", {"to_status": "CONTACTED"}, if_match=b["version"])
    assert r.status == 200, r
    factory.login(api, manager)
    r = api.get(f"{SALES}/pipeline?stage=CONTACTED")
    assert [x["lead"]["id"] for x in r.data] == [b["id"]] and r.json["meta"]["total"] == 1
    r = api.get(f"{SALES}/pipeline?channel=SOCIAL")
    assert [x["lead"]["id"] for x in r.data] == [a["id"]]
    r = api.get(f"{SALES}/pipeline?attention=UNASSIGNED")
    assert {x["lead"]["id"] for x in r.data} == set()  # OWN creators are auto-assigned
    r = api.get(f"{SALES}/pipeline?q=anita+reddy")  # the CRM's tokenised search: every word must match
    assert {x["lead"]["id"] for x in r.data} == {a["id"], b["id"]}
    assert api.get(f"{SALES}/pipeline?q=%25").status == 422 and ok(api.get(f"{SALES}/pipeline?q=zzzz")) == []
    assert api.get(f"{SALES}/pipeline?stage=NOPE").status == 422
    assert api.get(f"{SALES}/pipeline?bogus=1").status == 422
    assert set(r.json["meta"]) >= {"page", "limit", "total", "scanned", "truncated", "stage_counts"}
