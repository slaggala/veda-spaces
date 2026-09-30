"""DEV-004 as corrected (IR-16): staff re-consent (04 §5.4, LEAD-012, LEAD-024, LEAD-027).

Privacy: staff cannot assert website provenance; a staff capture carries no web IP or source page.
Consent: accepted only after withdrawal, when never captured, or for a new notice version; a note is required.
History: the superseded evidence is kept append-only in a read-only timeline activity and in audit_log.
Authorization, duplicate detection, tamper evidence and erasure are covered below.
"""

import pytest
import sqlalchemy as sa

from tests.support.dbh import audits, rows
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.platform.audit.models import AuditLog

POLICY = "2026-09-v1"


@pytest.fixture
def founder(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    return user


def _web_lead(api, factory, **fields):
    assert factory.public_lead(api, **fields).status == 201
    return api.get("/api/v1/leads").data[0]


def _get(api, lead_id, token=None):
    return api.get(f"/api/v1/leads/{lead_id}", token=token).data


def _withdraw(api, lead):
    r = api.post(
        f"/api/v1/leads/{lead['id']}/consent/withdraw",
        {"channel": "PHONE_VERBAL", "note": "asked us to stop"},
        if_match=lead["version"],
    )
    assert r.status == 200, r
    return _get(api, lead["id"])


def _reconsent(api, lead, token=None, **consent):
    body = {"channel": "PHONE_VERBAL", "policy_version": POLICY, "note": "Customer called back on 29 Sep", **consent}
    return api.patch(f"/api/v1/leads/{lead['id']}", {"consent": body}, if_match=lead["version"], token=token)


def test_DEV004_reconsent_after_withdrawal_records_new_provenance_and_keeps_history(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    original = rows(sa.select(AuditLog).where(AuditLog.entity_id == lead["id"], AuditLog.action == "CREATE"))[0]
    r = _reconsent(api, lead)
    assert r.status == 200, r
    consent = r.data["consent"]
    assert consent["contact"] is True and consent["channel"] == "PHONE_VERBAL" and consent["withdrawn_on"] is None
    assert consent["source_page"] is None and consent["ip_address"] is None, "no website provenance on a staff capture"

    timeline = api.get(f"/api/v1/leads/{lead['id']}/activities").data
    evidence = [a for a in timeline if a["consent_evidence"]]
    assert len(evidence) == 1 and evidence[0]["is_system_generated"] and not evidence[0]["can_edit"]
    prev = evidence[0]["consent_evidence"]["previous"]
    assert (
        prev["channel"] == "WEBSITE_FORM" and prev["policy_version"] == POLICY and prev["ip_address_recorded"] is True
    )
    assert prev["withdrawn_on"] is not None and prev["withdrawal_channel"] == "PHONE_VERBAL"
    assert evidence[0]["description"] == "Customer called back on 29 Sep"
    # The full prior row values (including the web IP) stay in the immutable audit log.
    update = [a for a in audits(lead["id"], action="UPDATE") if "consent_channel" in (a.changed_fields or [])][-1]
    assert update.old_value["consent_channel"] == "WEBSITE_FORM" and update.old_value["consent_ip_address"]
    assert original.new_value["consent_channel"] == "WEBSITE_FORM"


def test_DEV004_reconsent_without_withdrawal_or_new_version_is_refused(api, founder, factory):
    lead = _web_lead(api, factory)
    r = _reconsent(api, lead)
    assert r.status == 409 and r.code == "INVALID_STATE"
    assert _get(api, lead["id"])["consent"]["channel"] == "WEBSITE_FORM", "original evidence untouched"


def test_DEV004_new_policy_version_may_be_recorded_without_withdrawal(api, founder, factory, app):
    from veda import config

    lead = _web_lead(api, factory)
    config.settings().published_policy_versions = [POLICY, "2027-01-v2"]
    r = _reconsent(api, lead, policy_version="2027-01-v2")
    assert r.status == 200 and r.data["consent"]["policy_version"] == "2027-01-v2"


@pytest.mark.parametrize(
    "consent,code",
    [
        ({"channel": "WEBSITE_FORM"}, "VALIDATION_FAILED"),
        ({"note": ""}, "VALIDATION_FAILED"),
        ({"policy_version": "1999"}, "UNKNOWN_POLICY_VERSION"),
    ],
)
def test_DEV004_invalid_reconsent_rejected(api, founder, factory, consent, code):
    lead = _withdraw(api, _web_lead(api, factory))
    r = _reconsent(api, lead, **consent)
    assert r.status == 422 and r.code == code, r
    assert _get(api, lead["id"])["consent"]["contact"] is False


def test_DEV004_note_is_required(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    r = api.patch(
        f"/api/v1/leads/{lead['id']}",
        {"consent": {"channel": "PHONE_VERBAL", "policy_version": POLICY}},
        if_match=lead["version"],
    )
    assert r.status == 422


def test_DEV004_raw_consent_fields_and_public_reconsent_rejected(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    assert (
        api.patch(f"/api/v1/leads/{lead['id']}", {"consent_contact": True}, if_match=lead["version"]).code
        == "FIELD_NOT_UPDATABLE"
    )
    pub = factory.public_lead(api, reconsent={"acknowledged": True})
    assert pub.status == 422 and pub.json["errors"][0]["code"] == "UNKNOWN_FIELD"


def test_DEV004_staff_create_cannot_claim_website_provenance(api, founder):
    body = {
        "name": "Walk-in",
        "phone": "+919812345678",
        "source_code": "REFERRAL",
        "consent": {"channel": "WEBSITE_FORM", "policy_version": POLICY},
    }
    assert api.post("/api/v1/leads", body).status == 422
    body["consent"]["channel"] = "IN_PERSON"
    r = api.post("/api/v1/leads", body)
    assert r.status == 201 and r.data["consent"]["channel"] == "IN_PERSON"


def test_DEV004_authorization_follows_lead_update_scope(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    sales = factory.user("SALES")
    token = factory.login(api, sales, set_default=False)
    assert _reconsent(api, lead, token=token).status == 404, "OWN scope: another user's lead is not visible"
    founder_token = factory.login(api, founder, set_default=False)
    r = api.post(
        f"/api/v1/leads/{lead['id']}/assign",
        {"assigned_to": sales.id},
        if_match=_get(api, lead["id"], founder_token)["version"],
        token=founder_token,
    )
    assert r.status == 200, r
    lead = _get(api, lead["id"], token)
    assert _reconsent(api, lead, token=token).status == 200
    # SALES cannot read /history, but the superseded evidence is in the timeline it can read.
    assert api.get(f"/api/v1/leads/{lead['id']}/history", token=token).status == 403
    assert any(a["consent_evidence"] for a in api.get(f"/api/v1/leads/{lead['id']}/activities", token=token).data)


def test_DEV004_duplicate_detection_still_runs_on_the_same_patch(api, founder, factory):
    first = _web_lead(api, factory, phone="9811111111")
    second = _withdraw(api, _web_lead(api, factory, phone="9822222222"))
    body = {"phone": "9811111111", "consent": {"channel": "PHONE_VERBAL", "policy_version": POLICY, "note": "call"}}
    r = api.patch(f"/api/v1/leads/{second['id']}", body, if_match=second["version"])
    assert r.status == 200 and r.data["duplicate_status"] == "SUSPECTED"
    del first


def test_DEV004_audit_evidence_is_tamper_resistant(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    assert _reconsent(api, lead).status == 200
    row = [a for a in audits(lead["id"], action="UPDATE") if "consent_channel" in (a.changed_fields or [])][-1]
    for statement in (
        f"UPDATE audit_log SET old_value = NULL WHERE id = '{row.id}'",
        f"DELETE FROM audit_log WHERE id = '{row.id}'",
    ):
        with pytest.raises(sa.exc.DBAPIError):  # the immutability guard rejects it (AUDIT-004)
            with actor(system_context()), db.engine().begin() as conn:
                conn.execute(sa.text(statement))
    assert rows(sa.select(AuditLog).where(AuditLog.id == row.id))[0].old_value["consent_channel"] == "WEBSITE_FORM"


def test_DEV004_erasure_removes_the_reconsent_note(api, founder, factory):
    lead = _withdraw(api, _web_lead(api, factory))
    lead = _reconsent(api, lead).data
    r = api.post(
        f"/api/v1/leads/{lead['id']}/erasure",
        {"request_ref": "DPR-2026-009", "legal_basis": "DPDP s.12 erasure", "reason": "customer asked"},
        if_match=lead["version"],
    )
    assert r.status in (200, 204), r
    notes = [a for a in api.get(f"/api/v1/leads/{lead['id']}/activities").data if a["consent_evidence"]]
    assert notes and notes[0]["description"] != "Customer called back on 29 Sep"
