"""E2/E3: Budgetary Estimate persistence, public endpoints, enquiry linking, staff actions, rate cards, retention.

Runs on the SYNTHETIC rate card only (no commercial rates). The estimator is disabled by default; tests enable it
with @pytest.mark.settings(estimator_enabled=True).
"""

import copy
import json
from datetime import timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa

from tests.support.dbh import rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.ids import new_id
from veda.modules.crm.leads.models import Lead, LeadActivity
from veda.modules.estimator import engine, ratecard, service
from veda.modules.estimator.models import (
    BudgetEstimate,
    BudgetEstimateAssumption,
    BudgetEstimateLeadLink,
    BudgetEstimateLine,
    BudgetEstimateProjectItem,
    EstimateEvent,
    EstimatorRateCard,
)

CARD_DOC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
APPROVAL = "Owner approval 2026-10-08 (synthetic test card)"
ON = pytest.mark.settings(estimator_enabled=True)
SITE = "http://localhost:8000"


def load_card(doc=None, *, version=None, activate=True):
    d = copy.deepcopy(doc or CARD_DOC)
    if version:
        d["version"] = version
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_card(s, d)
        if activate:
            service.activate_card(s, d["version"], APPROVAL)
    return d["version"]


def body(**overrides):
    b = {
        "property_type": "APARTMENT",
        "home_size": "2BHK",
        "project_kind": "NEW_HOME",
        "city": "Hyderabad",
        "package": "ESSENTIAL",
        "selections": [
            {
                "room": "MASTER_BEDROOM",
                "product": "WARDROBE",
                "measurements": {"WIDTH": {"value": 6, "unit": "ft"}},
                "options": {"DOOR": "SLIDING"},
            },
            {"room": "KITCHEN", "product": "KITCHEN"},
        ],
        "turnstile_token": "ok-token",
    }
    b.update(overrides)
    return b


def estimate(api, **overrides):
    return api.post("/api/v1/public/estimates", body(**overrides), anonymous=True, headers={"Origin": SITE})


def enquiry(api, reference, *, key=None, **fields):
    b = {
        "name": "Meera Iyer",
        "phone": f"98{new_id()[-8:].translate(str.maketrans('abcdef', '123456'))}",
        "consent": {"acknowledged": True, "policy_version": "2026-09-v1"},
        "turnstile_token": "ok-token",
        "company_website_url": "",
        "estimate_reference": reference,
        "preferred_contact": "WHATSAPP",
        "city": "Hyderabad",
        **fields,
    }
    return api.post(
        "/api/v1/public/enquiries",
        b,
        anonymous=True,
        headers={"Idempotency-Key": key or f"enq-{new_id()}", "Origin": SITE},
    )


def keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from keys(v)


# --- feature flag, privacy -----------------------------------------------------------------------------------------------


def test_public_endpoints_are_disabled_by_default(api):
    load_card()
    assert estimate(api).status == 404
    assert enquiry(api, "AAAA-BBBB").status == 404
    assert not rows(sa.select(BudgetEstimate)) and not rows(sa.select(Lead))


@ON
def test_no_active_card_means_unavailable(api):
    r = estimate(api)
    assert r.status == 503 and r.code == "ESTIMATOR_UNAVAILABLE"


@ON
def test_public_estimate_is_customer_safe(api):
    load_card()
    r = estimate(api)
    assert r.status == 201, r
    data = r.data
    assert data["title"] == "VEDA SPACES PRELIMINARY BUDGETARY ESTIMATE"
    assert service.REFERENCE_RE.match(data["reference"]) and data["rate_card_version"] == "SYNTHETIC-2"
    leaked = set(keys(data)) & {"id", "rate_minor", "lines", "quantity", "components", "base_minor", "uom", "lead"}
    assert not leaked, leaked
    assert data["project_preparation"]["label"] == "Project Preparation & Protection Package"
    assert data["range"]["low_minor"] < data["range"]["high_minor"] and data["gst"]["pct"] == 18
    allowance = data["custom_features_allowance"]
    assert set(allowance) == {"label", "description", "low_minor", "high_minor"}, "no percentage or basis"
    assert allowance["label"] == "Custom Features Allowance" and 0 < allowance["low_minor"] < allowance["high_minor"]
    assert r.headers["Cache-Control"] == "no-store"
    assert r.headers["Access-Control-Allow-Origin"] == SITE


@ON
def test_estimate_takes_no_personal_data(api):
    load_card()
    for extra in ({"name": "Meera"}, {"phone": "9876543210"}, {"email": "m@example.com"}):
        r = estimate(api, **extra)
        assert r.status == 422 and r.code in ("UNKNOWN_FIELD", "VALIDATION_FAILED"), (extra, r)
    estimate(api)
    stored = rows(sa.select(BudgetEstimate))[0]
    assert set(stored.inputs) == {"property_type", "home_size", "project_kind", "city", "package", "selections"}


@ON
@pytest.mark.parametrize("token", [None, "", "fail-bad-token"])
def test_turnstile_is_required(api, token):
    load_card()
    r = estimate(api, turnstile_token=token)
    assert r.status == 422 and r.code == "CAPTCHA_FAILED"
    assert not rows(sa.select(BudgetEstimate))


@ON
@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"package": "LUXURY"}, "PACKAGE_UNAVAILABLE"),
        ({"selections": [{"room": "KITCHEN", "product": "SAUNA"}]}, "UNKNOWN_PRODUCT"),
        (
            {
                "selections": [
                    {
                        "room": "BEDROOM_2",
                        "product": "WARDROBE",
                        "measurements": {"WIDTH": {"value": 900, "unit": "ft"}},
                    }
                ]
            },
            "OUT_OF_BOUNDS",
        ),
        ({"selections": []}, "INVALID"),
        ({"home_size": "9BHK"}, "INVALID"),
    ],
)
def test_invalid_inputs_are_refused_with_field_errors(api, overrides, code):
    load_card()
    r = estimate(api, **overrides)
    assert r.status == 422 and r.code == "VALIDATION_FAILED"
    assert code in {e["code"] for e in r.json["errors"]}, r.json
    assert not rows(sa.select(BudgetEstimate))


# --- persistence, reproducibility, expiry -------------------------------------------------------------------------------


@ON
def test_snapshot_is_complete_and_reproducible(api):
    load_card()
    reference = estimate(api).data["reference"]
    row = rows(sa.select(BudgetEstimate).where(BudgetEstimate.public_reference == reference))[0]
    lines = rows(sa.select(BudgetEstimateLine).where(BudgetEstimateLine.estimate_id == row.id))
    prep = rows(sa.select(BudgetEstimateProjectItem).where(BudgetEstimateProjectItem.estimate_id == row.id))
    assumptions = rows(sa.select(BudgetEstimateAssumption).where(BudgetEstimateAssumption.estimate_id == row.id))
    work = sum(ln.amount_minor for ln in lines)
    assert work + row.allowance_minor + sum(p.amount_minor for p in prep) == row.base_minor
    assert row.allowance_low_minor == round(work * 0.05) and row.allowance_high_minor == round(work * 0.15)
    assert len(assumptions) > 0 and all(a.text for a in assumptions), "the kitchen used typical sizes"
    assert row.calculation_version == engine.CALCULATION_VERSION and row.rate_card_version == "SYNTHETIC-2"
    card = rows(sa.select(EstimatorRateCard).where(EstimatorRateCard.id == row.rate_card_id))[0]
    again = engine.calculate(ratecard.parse(card.document), engine.EstimateRequest.model_validate(row.inputs))
    assert json.loads(json.dumps(again.staff_view(), default=str)) == row.result
    assert (row.expires_on - row.created_on).days == 30, "D7: 30-day validity"
    assert [e.event_type for e in rows(sa.select(EstimateEvent).where(EstimateEvent.estimate_id == row.id))] == [
        "ESTIMATE_CREATED"
    ]


# --- enquiry: atomic link, retries, unusable references -----------------------------------------------------------------


@ON
def test_enquiry_links_the_estimate_and_fills_the_lead(api):
    load_card()
    reference = estimate(api).data["reference"]
    r = enquiry(api, reference)
    assert r.status == 201, r
    assert set(r.data) == {"reference", "message"}, "a customer reference only: no id, duplicate or workflow state"
    lead = rows(sa.select(Lead))[0]
    link = rows(sa.select(BudgetEstimateLeadLink))[0]
    est = rows(sa.select(BudgetEstimate))[0]
    assert link.lead_id == lead.id and link.estimate_id == est.id
    assert link.preferred_contact == "WHATSAPP" and link.consent_policy_version == "2026-09-v1"
    assert lead.project_type_id is not None and lead.budget_range_id is not None, "defaulted from the estimate"
    assert not lead.intake_unmapped


@ON
def test_enquiry_retry_with_the_same_key_replays(api):
    load_card()
    reference = estimate(api).data["reference"]
    first = enquiry(api, reference, key="enquiry-retry-0001", phone="9812345678")
    second = enquiry(api, reference, key="enquiry-retry-0001", phone="9812345678")
    assert first.status == second.status == 201 and first.data == second.data
    assert len(rows(sa.select(Lead))) == 1 and len(rows(sa.select(BudgetEstimateLeadLink))) == 1


@ON
@pytest.mark.parametrize("problem", ["UNKNOWN", "EXPIRED", "ALREADY_LINKED", "INVALID"])
def test_unusable_estimate_never_rejects_the_enquiry(api, problem):
    load_card()
    reference = estimate(api).data["reference"]
    if problem == "UNKNOWN":
        reference = "ZZZZ-ZZZZ"
    elif problem == "INVALID":
        reference = "not a reference"
    elif problem == "EXPIRED":
        clock.advance(timedelta(days=31))
    else:
        assert enquiry(api, reference).status == 201
    r = enquiry(api, reference)
    assert r.status == 201
    lead = rows(sa.select(Lead).order_by(Lead.created_on.desc()))[0]
    assert lead.intake_unmapped["estimate_reference"].startswith(problem)
    assert len(rows(sa.select(BudgetEstimateLeadLink))) == (1 if problem == "ALREADY_LINKED" else 0)


@ON
def test_lead_and_link_commit_together(api, monkeypatch):
    load_card()
    reference = estimate(api).data["reference"]

    def broken(*a, **k):
        raise RuntimeError("link failed")

    monkeypatch.setattr(service, "link", broken)
    r = enquiry(api, reference)
    assert r.status == 500
    assert not rows(sa.select(Lead)) and not rows(sa.select(BudgetEstimateLeadLink)), "no lead without its link"


@ON
def test_enquiry_still_needs_consent_and_turnstile(api):
    load_card()
    reference = estimate(api).data["reference"]
    assert enquiry(api, reference, consent=None).code == "CONSENT_REQUIRED"
    assert enquiry(api, reference, turnstile_token="fail-x").code == "CAPTCHA_FAILED"
    assert not rows(sa.select(BudgetEstimateLeadLink))


@ON
def test_lead_notification_carries_the_estimate_summary(api, factory):
    from veda.platform.notifications import worker
    from veda.platform.notifications.email import CaptureEmailProvider

    factory.user(founder=True)
    load_card()
    reference = estimate(api).data["reference"]
    assert enquiry(api, reference).status == 201
    worker.drain_once()
    texts = [m.text for m in CaptureEmailProvider.sent]
    assert any("Budgetary Estimate ₹" in t and "Essential" in t for t in texts), texts


@ON
def test_luxury_enquiry_requests_a_design_consultation(api, factory):
    """D2: Luxury has no public price; the enquiry is marked on the lead and in the notification."""
    from veda.platform.notifications import worker
    from veda.platform.notifications.email import CaptureEmailProvider

    factory.user(founder=True)
    load_card()
    assert enquiry(api, None, consultation="LUXURY_DESIGN", preferred_contact="PHONE").status == 201
    lead = rows(sa.select(Lead))[0]
    subjects = [a.subject for a in rows(sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id))]
    assert any(t.startswith(service.LUXURY_CONSULTATION) and t.endswith("prefers phone") for t in subjects), subjects
    assert not rows(sa.select(BudgetEstimateLeadLink)) and not lead.intake_unmapped
    worker.drain_once()
    assert any("Luxury design consultation requested" in m.text for m in CaptureEmailProvider.sent)
    assert enquiry(api, None, consultation="SOMETHING_ELSE").status == 201, "an unknown value is ignored"
    assert sum(a.subject.startswith(service.LUXURY_CONSULTATION) for a in rows(sa.select(LeadActivity))) == 1


@ON
def test_a_concurrently_linked_estimate_never_rejects_the_enquiry(api, monkeypatch):
    """Review finding: two enquiries racing on one reference both pass the check; the second must still be taken."""
    load_card()
    reference = estimate(api).data["reference"]
    assert enquiry(api, reference).status == 201
    row = rows(sa.select(BudgetEstimate))[0]
    monkeypatch.setattr(service, "usable_for_enquiry", lambda s, ref: (s.get(BudgetEstimate, row.id), None))
    r = enquiry(api, reference)
    assert r.status == 201, r
    second = [lead for lead in rows(sa.select(Lead)) if lead.intake_unmapped][0]
    assert second.intake_unmapped["estimate_reference"] == f"ALREADY_LINKED:{reference}"
    assert len(rows(sa.select(BudgetEstimateLeadLink))) == 1


@ON
def test_luxury_is_never_priced_publicly(api):
    doc = copy.deepcopy(CARD_DOC)
    doc["packages"]["LUXURY"] = True
    load_card(doc)
    r = estimate(api, package="LUXURY")
    assert r.status == 422 and r.json["errors"][0]["code"] == "PACKAGE_UNAVAILABLE", r


# --- staff ----------------------------------------------------------------------------------------------------------------


@ON
def test_staff_view_scope_and_actions(api, factory):
    load_card()
    reference = estimate(api).data["reference"]
    assert enquiry(api, reference).status == 201
    lead = rows(sa.select(Lead))[0]
    admin = factory.user("ADMIN")
    token = factory.login(api, admin, set_default=False)
    listed = api.get(f"/api/v1/leads/{lead.id}/estimates", token=token)
    assert listed.status == 200 and [e["reference"] for e in listed.data] == [reference]
    est_id = listed.data[0]["id"]
    view = api.get(f"/api/v1/estimates/{est_id}", token=token).data
    assert view["estimate"]["lines"] and view["estimate"]["project_preparation"]["components"], "staff see details"
    assert view["lead"]["lead_number"] == lead.lead_number and view["preferred_contact"] == "WHATSAPP"

    revised = api.post(f"/api/v1/estimates/{est_id}/revisions", {"package": "PREMIUM"}, token=token)
    assert (
        revised.status == 201 and revised.data["package"] == "PREMIUM" and revised.data["source_reference"] == reference
    )
    dup = api.post(f"/api/v1/estimates/{est_id}/duplicate", token=token)
    assert dup.status == 201 and dup.data["lead"]["id"] == lead.id
    assert len(api.get(f"/api/v1/leads/{lead.id}/estimates", token=token).data) == 3

    copy_ = api.post(f"/api/v1/estimates/{est_id}/consultation-copy", token=token)
    assert copy_.status == 200 and copy_.data["heading"] == "Consultation copy" and "lines" not in copy_.data
    assert api.post(f"/api/v1/estimates/{est_id}/site-measurement", token=token).data["site_measurement_required"]
    q = api.post(f"/api/v1/estimates/{est_id}/quotation-process", token=token)
    assert q.status == 200 and q.data["started"]
    lead_after = rows(sa.select(Lead).where(Lead.id == lead.id))[0]
    assert lead_after.status == "NEW", "never converted into a quotation automatically"
    subjects = [a.subject for a in rows(sa.select(LeadActivity).where(LeadActivity.lead_id == lead.id))]
    assert any("Site measurement required" in s for s in subjects)
    assert any("Official quotation process started" in s for s in subjects)
    types = {e.event_type for e in rows(sa.select(EstimateEvent))}
    assert {"ESTIMATE_REVISED", "ESTIMATE_DUPLICATED", "CONSULTATION_COPY", "SITE_MEASUREMENT_REQUIRED"} <= types
    assert "QUOTATION_PROCESS_STARTED" in types


@ON
def test_staff_access_follows_the_lead_scope(api, factory):
    load_card()
    reference = estimate(api).data["reference"]
    assert enquiry(api, reference).status == 201
    lead = rows(sa.select(Lead))[0]
    est_id = rows(sa.select(BudgetEstimate))[0].id
    sales = factory.user("SALES")
    token = factory.login(api, sales, set_default=False)
    assert api.get(f"/api/v1/estimates/{est_id}", token=token).status == 404, "not their lead"
    assert api.get(f"/api/v1/leads/{lead.id}/estimates", token=token).status == 404
    assert api.get(f"/api/v1/estimates/{est_id}", anonymous=True).status == 401


@ON
def test_unlinked_estimates_need_full_lead_visibility(api, factory):
    load_card()
    estimate(api)
    est_id = rows(sa.select(BudgetEstimate))[0].id
    sales_token = factory.login(api, factory.user("SALES"), set_default=False)
    admin_token = factory.login(api, factory.user("ADMIN"), set_default=False)
    assert api.get(f"/api/v1/estimates/{est_id}", token=sales_token).status == 404
    assert api.get(f"/api/v1/estimates/{est_id}", token=admin_token).status == 200


def test_no_route_exposes_a_rate_card(app):
    paths = [r.rule for r in app.url_map.iter_rules()]
    assert not [p for p in paths if "rate" in p.lower() or "card" in p.lower()]
    public = sorted(p for p in paths if p.startswith("/api/v1/public/"))
    assert public == ["/api/v1/public/enquiries", "/api/v1/public/estimates", "/api/v1/public/leads"]


# --- rate cards ------------------------------------------------------------------------------------------------------------


def test_rate_card_lifecycle_and_rollback(app):
    v1 = load_card(version="SYN-A")
    v2 = load_card(version="SYN-B")
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        states = {c["version"]: c["status"] for c in service.list_cards(s)}
        assert states == {v1: "RETIRED", v2: "ACTIVE"}
        assert "rates" not in json.dumps(service.list_cards(s))
        service.rollback_card(s, APPROVAL)
    with db.unit_of_work(write=False) as s:
        assert service.active_card(s)[0].card_version == v1
    events = [e.event_type for e in rows(sa.select(EstimateEvent).order_by(EstimateEvent.created_on))]
    assert events.count("CARD_LOADED") == 2 and "CARD_ROLLED_BACK" in events and events.count("CARD_RETIRED") == 2


def test_rate_card_refusals(app):
    load_card(version="SYN-A", activate=False)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        with pytest.raises(service.CardError, match="already loaded"):
            service.load_card(s, dict(copy.deepcopy(CARD_DOC), version="SYN-A"))
        with pytest.raises(service.CardError, match="approval"):
            service.activate_card(s, "SYN-A", "ok")
        with pytest.raises(service.CardError, match="customer data"):
            service.validate_document(dict(copy.deepcopy(CARD_DOC), description="call 9876543210 for rates"))
        with pytest.raises(service.CardError, match="invalid rate card"):
            service.validate_document(dict(copy.deepcopy(CARD_DOC), gst_pct=-1))
        row = s.execute(sa.select(EstimatorRateCard)).scalar_one()
        row.document = dict(row.document, gst_pct=0)  # tampering after load
        s.flush()
        with pytest.raises(service.CardError, match="SHA-256"):
            service.activate_card(s, "SYN-A", APPROVAL)


def test_cli_dry_run_validates_without_storing(app, tmp_path, capsys):
    from veda.cli.main import main

    path = tmp_path / "card.json"
    path.write_text(json.dumps(CARD_DOC))
    assert main(["estimator", "validate-card", str(path)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["valid"] and out["version"] == "SYNTHETIC-2" and "rates" not in json.dumps(out)
    assert not rows(sa.select(EstimatorRateCard))
    assert main(["estimator", "load-card", str(path)]) == 0
    assert main(["estimator", "activate-card", "--version", "SYNTHETIC-2", "--approval", APPROVAL]) == 0
    assert main(["estimator", "activate-card", "--version", "SYNTHETIC-2", "--approval", APPROVAL]) == 2


# --- retention, rate limits ---------------------------------------------------------------------------------------------------


@ON
def test_retention_removes_only_expired_unlinked_estimates(api):
    load_card()
    kept = estimate(api).data["reference"]
    assert enquiry(api, kept).status == 201
    estimate(api)
    from veda.platform import maintenance

    clock.advance(timedelta(days=89))
    assert maintenance.estimate_retention()["removed"] == 0, "D7: kept for 90 days from creation"
    clock.advance(timedelta(days=2))
    assert maintenance.estimate_retention()["removed"] == 1
    live = rows(sa.select(BudgetEstimate), include_deleted=False)
    assert [e.public_reference for e in live] == [kept]
    assert not rows(
        sa.select(BudgetEstimateLine).where(BudgetEstimateLine.estimate_id != live[0].id), include_deleted=False
    )


@pytest.mark.settings(estimator_enabled=True, rate_limits_enabled=True)
def test_estimate_rate_limits(api):
    load_card()
    codes = [estimate(api).status for _ in range(12)]
    assert codes[:6].count(201) == 6 and 429 in codes, codes


@pytest.mark.settings(estimator_enabled=True, rate_limits_enabled=True)
def test_unverified_traffic_cannot_exhaust_the_aggregate_limit(api):
    """Review S4 / staging stop condition: requests that fail Turnstile count against their own source limits, never
    against the aggregate, so 102 networks sending 612 unverified requests (over the 600/h aggregate) lock out only
    themselves."""
    load_card()

    def post(ip, token):
        return api.post(
            "/api/v1/public/estimates",
            body(turnstile_token=token),
            anonymous=True,
            headers={"Origin": SITE, "CF-Connecting-IP": ip, "X-Veda-Client": f"c{ip.replace('.', '')}"},
        )

    refused = [post(f"10.{n // 250}.{n % 250}.7", "fail-x").status for n in range(102) for _ in range(6)]
    assert set(refused) == {422}, "each source stays inside its own limits"
    assert post("10.9.9.9", "ok-token").status == 201, "a verified customer is still served"
