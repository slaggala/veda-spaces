"""Acquisition funnel, beacons and demo (SCA-007/008/009): NOT_TRACKED against zero, beacon de-duplication, channel
derivation, closed schema and body limit on the public route, cohort counts, ratios with no denominator, and a demo
that holds no customer data. SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.sales import FLAGS, SALES, beacon, keys

pytestmark = pytest.mark.settings(**FLAGS)


@pytest.fixture
def manager(api, factory):
    user = factory.user("SALES_MANAGER", mfa=True)
    factory.login(api, user)
    return user


def _funnel(api, **params):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return ok(api.get(f"{SALES}/funnel{'?' + q if q else ''}"))


def test_untracked_beacons_are_reported_as_not_tracked_never_as_zero(api, manager):
    f = _funnel(api)
    for event in ("site_visit", "estimator_started", "enquiry_started", "journey_viewed"):
        assert f["site"][event] == {
            "count": None,
            "basis": "CLIENT_EVENT",
            "tracking": "NOT_TRACKED",
            "by_channel": None,
        }
    assert f["ratios"]["site_visit_to_enquiry"] == {"value": None, "reason": "NOT_TRACKED"}
    assert f["ratios"]["enquiry_to_quotation"] == {"value": None, "reason": "NO_DENOMINATOR"}
    assert f["estimates_completed"] == {"count": 0, "basis": "AUTHORITATIVE", "tracking": "TRACKED"}
    assert f["cohort"]["size"] == 0 and f["lost_reasons"] == []


def test_a_beacon_counts_once_per_session_event_and_day(api, manager):
    token = api.token
    assert beacon(api, "site_visit", "session-aaaaaaaaaaaaaaaa").status == 204
    assert beacon(api, "site_visit", "session-aaaaaaaaaaaaaaaa").status == 204  # a retry or reload
    assert beacon(api, "site_visit", "session-bbbbbbbbbbbbbbbb", utm_medium="cpc", utm_source="google").status == 204
    assert beacon(api, "estimator_started", "session-aaaaaaaaaaaaaaaa").status == 204
    api.token = token
    f = _funnel(api)
    visits = f["site"]["site_visit"]
    assert visits["count"] == 2 and visits["tracking"] == "TRACKED"
    assert visits["by_channel"]["UNKNOWN"] == 1 and visits["by_channel"]["PAID"] == 1
    assert f["site"]["estimator_started"]["count"] == 1
    assert f["site"]["enquiry_started"]["tracking"] == "NOT_TRACKED"  # a tracked zero and an untracked event differ
    assert f["ratios"]["site_visit_to_enquiry"] == {"value": 0.0, "reason": None}


def test_the_public_beacon_is_closed_bounded_and_anonymous(api, app):
    assert beacon(api, "page_scrolled").status == 422
    assert beacon(api, "site_visit", "short").status == 422
    assert beacon(api, "site_visit", "session-cccccccccccccccc", referrer_host="not a host!").status == 422
    r = api.post("/api/v1/public/acquisition/events", {"event": "site_visit", "client": "c" * 20, "page": "/x"},
                 anonymous=True)  # fmt: skip
    assert r.status == 422 and r.json["errors"][0]["code"] == "UNKNOWN_FIELD"
    r = api.post("/api/v1/public/acquisition/events", {"event": "site_visit", "client": "c" * 20, "utm_source": "x" * 2000},
                 anonymous=True)  # fmt: skip
    assert r.status == 413
    assert beacon(api, "journey_viewed", "session-dddddddddddddddd", referrer_host="www.google.co.in").status == 204
    from veda.kernel import db
    from veda.modules.sales.models import AcquisitionEventDaily

    with db.unit_of_work(write=False) as s:
        rows = {(r.event, r.channel, r.count) for r in s.query(AcquisitionEventDaily)}
    assert rows == {("journey_viewed", "ORGANIC_SEARCH", 1)}
    assert {c.name for c in AcquisitionEventDaily.__table__.columns} <= {
        "id",
        "created_on",
        "updated_on",
        "created_by",
        "updated_by",
        "is_deleted",
        "deleted_on",
        "deleted_by",
        "version",
        "day",
        "event",
        "channel",
        "count",
    }  # nothing about a person, a page or a device


def test_the_lead_cohort_counts_facts_by_channel_and_lost_reason(api, factory, manager):
    sales = factory.user("SALES")
    factory.login(api, sales)
    a = factory.lead(api, sales.token, source_code="INSTAGRAM")
    b = factory.lead(api, sales.token, source_code="PHONE")
    c = factory.lead(api, sales.token, source_code="REFERRAL")
    r = api.post(f"/api/v1/leads/{b['id']}/status", {"to_status": "CONTACTED"}, if_match=b["version"])
    assert r.status == 200, r
    r = api.post(f"/api/v1/leads/{c['id']}/status", {"to_status": "LOST", "lost_reason_code": "PROJECT_POSTPONED"},
                 if_match=c["version"])  # fmt: skip
    assert r.status == 200, r
    r = factory.public_lead(
        api, attribution={"utm_source": "google", "utm_medium": "cpc", "landing_page": "/", "referrer_url": None}
    )
    assert r.status == 201, r
    factory.login(api, manager)
    f = _funnel(api)
    steps = {s["code"]: s["count"] for s in f["leads"]}
    assert steps["leads_created"] == 4 and steps["contacted"] == 1 and steps["lost"] == 1 and steps["won"] == 0
    assert f["cohort"]["size"] == 4 and f["cohort"]["claimed_stages_without_record"] == 1  # b: CONTACTED by status only
    by = {x["code"]: x for x in f["by_channel"]}
    assert (
        by["SOCIAL"]["leads"] == 1
        and by["DIRECT"]["leads"] == 1
        and by["REFERRAL"]["lost"] == 1
        and by["PAID"]["leads"] == 1
    )
    assert f["lost_reasons"] == [{"code": "PROJECT_POSTPONED", "label": "Project postponed", "count": 1}]
    assert f["ratios"]["enquiry_to_won"] == {"value": 0.0, "reason": None}
    assert f["ratios"]["decided_to_won"] == {"value": 0.0, "reason": None}
    assert {s["code"]: s["count"] for s in f["current_stages"]}["LOST"] == 1
    assert "name" not in keys(f) and a["name"] not in str(f)
    # the period bounds the cohort; a bad range is refused
    assert _funnel(api, **{"from": "2020-01-01", "to": "2020-01-31"})["cohort"]["size"] == 0
    assert api.get(f"{SALES}/funnel?from=2026-02-01&to=2026-01-01").status == 422
    assert api.get(f"{SALES}/funnel?from=2024-01-01&to=2026-01-01").status == 422


def test_the_demo_is_synthetic_read_only_and_holds_no_customer_data(api, factory, manager):
    sales = factory.user("SALES")
    factory.login(api, sales)
    lead = factory.lead(api, sales.token, name="Only Realname", phone="+919000011111")
    before = ok(api.get(f"{SALES}/demo"))
    text = str(before)
    assert before["demo"] is True and before["label"].startswith("DEMO")
    assert "Only Realname" not in text and lead["lead_number"] not in text and "9000011111" not in text
    assert before["portal"]["demo"] is True and before["proposal"]["demo"] is True
    assert before["portal"]["contact"]["phone"].startswith("+00") and before["portal"]["contact"]["email"].endswith(
        "@example.com"
    )
    assert before["proposal"]["capabilities"] == {"interaction": False, "acceptance": False}
    assert [s["key"] for s in before["journey"]] == ["consultation", "site_measurement", "design_scope", "quotation",
                                                     "approval", "execution", "quality", "handover"]  # fmt: skip
    assert ok(api.get(f"{SALES}/demo")) == before  # deterministic: the same model on every call
    from veda.kernel import db
    from veda.modules.crm.leads.models import Lead
    from veda.platform.audit.models import AuditLog

    with db.unit_of_work(write=False) as s:
        leads = s.query(Lead).count()
        demo_audit = s.query(AuditLog).filter(AuditLog.entity_type.like("%demo%")).count()
    assert leads == 1 and demo_audit == 0  # nothing created, nothing audited
