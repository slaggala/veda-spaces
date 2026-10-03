"""RR-12: staff re-consent residuals of DEV-004 (AM-4 rules a to d; LEAD-012, LEAD-027).

(a) A re-consent without withdrawal needs a LATER published notice version (VEDA_PUBLISHED_POLICY_VERSIONS order);
    the same or an earlier version is 409 INVALID_STATE, so evidence cannot alternate between versions.
(b) Staff consent at lead creation requires a note and writes the same consent-history activity as PATCH.
(c) The superseded snapshot records the withdrawal note.
(d) Consent-history activities are protected in the database (0010_consent_evidence_guard); the erasure rewrite of
    an anonymized lead is the one admitted change.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
import sqlalchemy as sa

from tests.integration.test_consent_dev004 import POLICY, _get, _reconsent, _web_lead, _withdraw
from tests.support.dbh import audits, rows
from veda import config
from veda.kernel import db, migration_support
from veda.modules.crm.leads.models import LeadActivity
from veda.platform import maintenance
from veda.platform.audit.models import AuditLog

V2, V3 = "2027-01-v2", "2027-06-v3"
WITHDRAWAL_NOTE = "Asked us to stop calling his office line"
RECONSENT_NOTE = "Customer called back on 29 Sep"


@pytest.fixture
def founder(api, factory):
    user = factory.user(founder=True)
    factory.login(api, user)
    return user


def _publish(*versions: str) -> None:
    config.settings().published_policy_versions = list(versions)


def _evidence(api, lead_id: str) -> list[dict]:
    """Consent-history activities, oldest first."""
    acts = [a for a in api.get(f"/api/v1/leads/{lead_id}/activities").data if a["consent_evidence"]]
    return sorted(acts, key=lambda a: a["consent_evidence"]["recorded"]["captured_on"])


def _staff_lead(api, **consent):
    body = {
        "name": "Walk-in",
        "phone": "+919812345678",
        "source_code": "REFERRAL",
        "consent": {"channel": "IN_PERSON", "policy_version": POLICY, "note": "Signed at the studio", **consent},
    }
    return api.post("/api/v1/leads", body)


def _sql(statement: str, **params) -> None:
    with db.engine().begin() as conn:
        conn.execute(sa.text(statement), params)


def _refused(statement: str, **params) -> None:
    with pytest.raises(sa.exc.DBAPIError) as exc:
        _sql(statement, **params)
    assert "immutable" in str(exc.value).lower()


def _metadata(activity_id: str) -> dict:
    act = rows(sa.select(LeadActivity).where(LeadActivity.id == activity_id))[0]
    return act.metadata_


# --- (a) later-version rule ------------------------------------------------------------------------------------


def test_RR12_a_later_version_is_accepted_without_withdrawal(api, founder, factory):
    _publish(POLICY, V2)
    lead = _web_lead(api, factory)
    r = _reconsent(api, lead, policy_version=V2)
    assert r.status == 200 and r.data["consent"]["policy_version"] == V2
    (entry,) = _evidence(api, lead["id"])
    assert entry["consent_evidence"]["consent_event"] == "RECAPTURED"
    assert entry["consent_evidence"]["previous"]["policy_version"] == POLICY


def test_RR12_a_alternating_back_to_an_earlier_version_is_refused(api, founder, factory):
    """The reported defect: v1 → v2 → v1 → v2 … each overwrote the live evidence. Now only forward moves."""
    _publish(POLICY, V2)
    lead = _web_lead(api, factory)
    lead = _reconsent(api, lead, policy_version=V2).data
    r = _reconsent(api, lead, policy_version=POLICY)
    assert r.status == 409 and r.code == "INVALID_STATE", r
    assert _get(api, lead["id"])["consent"]["policy_version"] == V2, "live evidence untouched"
    assert len(_evidence(api, lead["id"])) == 1, "no history entry for a refused capture"


def test_RR12_a_same_version_is_refused_and_a_third_later_one_accepted(api, founder, factory):
    _publish(POLICY, V2, V3)
    lead = _web_lead(api, factory)
    lead = _reconsent(api, lead, policy_version=V2).data
    assert _reconsent(api, lead, policy_version=V2).code == "INVALID_STATE"
    lead = _get(api, lead["id"])
    assert _reconsent(api, lead, policy_version=V3).status == 200
    assert [e["consent_evidence"]["recorded"]["policy_version"] for e in _evidence(api, lead["id"])] == [V2, V3]


def test_RR12_a_withdrawal_allows_the_same_version_but_never_an_earlier_one(api, founder, factory):
    _publish(POLICY, V2)
    lead = _withdraw(api, _reconsent(api, _web_lead(api, factory), policy_version=V2).data)
    r = _reconsent(api, lead, policy_version=POLICY)
    assert r.status == 409 and r.code == "INVALID_STATE", "a withdrawal is no way back to an older notice"
    assert _reconsent(api, _get(api, lead["id"]), policy_version=V2).status == 200


def test_RR12_a_a_recorded_version_no_longer_published_counts_as_earliest(api, founder, factory):
    lead = _web_lead(api, factory)  # recorded under POLICY
    _publish(V2)  # POLICY retired
    r = _reconsent(api, lead, policy_version=V2)
    assert r.status == 200 and r.data["consent"]["policy_version"] == V2


def test_RR12_a_unknown_version_is_still_422_before_the_ordering_check(api, founder, factory):
    lead = _web_lead(api, factory)
    r = _reconsent(api, lead, policy_version="2099-01-v9")
    assert r.status == 422 and r.code == "UNKNOWN_POLICY_VERSION"


@pytest.mark.parametrize("versions", [[], [POLICY, V2, POLICY]], ids=["empty", "duplicate"])
def test_RR12_a_published_versions_must_be_an_ordered_set(app, versions):
    def problems(published: list[str]) -> list[str]:
        settings = replace(config.settings(), published_policy_versions=published)
        return [p for p in config.validate_environment(settings) if "VEDA_PUBLISHED_POLICY_VERSIONS" in p]

    assert problems(versions)
    assert not problems([POLICY, V2])


# --- (b) create-time staff consent ------------------------------------------------------------------------------


def test_RR12_b_create_time_consent_requires_a_note(api, founder):
    r = api.post(
        "/api/v1/leads",
        {
            "name": "Walk-in",
            "phone": "+919812345678",
            "source_code": "REFERRAL",
            "consent": {"channel": "IN_PERSON", "policy_version": POLICY},
        },
    )
    assert r.status == 422 and r.json["errors"][0]["field"] == "consent.note", r
    assert _staff_lead(api, note="").status == 422
    assert api.get("/api/v1/leads").data == [], "nothing created"


def test_RR12_b_create_time_consent_writes_the_consent_history_activity(api, founder):
    r = _staff_lead(api)
    assert r.status == 201 and r.data["consent"]["contact"] is True
    (entry,) = _evidence(api, r.data["id"])
    evidence = entry["consent_evidence"]
    assert evidence["consent_event"] == "CAPTURED" and evidence["previous"] is None
    assert evidence["recorded"] == {
        "policy_version": POLICY,
        "channel": "IN_PERSON",
        "captured_on": r.data["consent"]["captured_on"],
    }
    assert entry["description"] == "Signed at the studio" and entry["can_edit"] is False
    assert entry["subject"] == "Consent to contact recorded"


def test_RR12_b_create_without_consent_writes_no_consent_activity(api, founder):
    r = _staff_lead(api)
    assert r.status == 201
    plain = api.post("/api/v1/leads", {"name": "Walk-in", "phone": "+919812345679", "source_code": "REFERRAL"})
    assert plain.status == 201 and plain.data["consent"]["contact"] is False
    assert _evidence(api, plain.data["id"]) == []


def test_RR12_b_unknown_version_at_create_creates_nothing(api, founder):
    r = _staff_lead(api, policy_version="2099-01-v9")
    assert r.status == 422 and r.code == "UNKNOWN_POLICY_VERSION"
    assert api.get("/api/v1/leads").data == []


def test_RR12_b_create_time_capture_then_later_version(api, founder):
    _publish(POLICY, V2)
    lead = _staff_lead(api).data
    assert _reconsent(api, lead, policy_version=POLICY).code == "INVALID_STATE"
    assert _reconsent(api, _get(api, lead["id"]), policy_version=V2).status == 200
    first, second = _evidence(api, lead["id"])
    assert second["consent_evidence"]["previous"]["channel"] == "IN_PERSON"
    assert second["consent_evidence"]["previous"]["captured_on"] == first["consent_evidence"]["recorded"]["captured_on"]


# --- (c) withdrawal note in the snapshot ---------------------------------------------------------------------


def test_RR12_c_superseded_snapshot_keeps_the_withdrawal_note(api, founder, factory):
    lead = _web_lead(api, factory)
    r = api.post(
        f"/api/v1/leads/{lead['id']}/consent/withdraw",
        {"channel": "EMAIL", "note": WITHDRAWAL_NOTE},
        if_match=lead["version"],
    )
    assert r.status == 200
    assert _reconsent(api, _get(api, lead["id"])).status == 200
    previous = _evidence(api, lead["id"])[0]["consent_evidence"]["previous"]
    assert previous["withdrawal_note"] == WITHDRAWAL_NOTE and previous["withdrawal_channel"] == "EMAIL"
    assert _get(api, lead["id"])["consent"]["withdrawn_on"] is None, "the live row starts afresh"


def test_RR12_c_snapshot_without_a_withdrawal_has_a_null_note(api, founder, factory):
    _publish(POLICY, V2)
    lead = _web_lead(api, factory)
    assert _reconsent(api, lead, policy_version=V2).status == 200
    previous = _evidence(api, lead["id"])[0]["consent_evidence"]["previous"]
    assert "withdrawal_note" in previous and previous["withdrawal_note"] is None


# --- (d) database protection --------------------------------------------------------------------------------


def _consent_activity(api, factory) -> tuple[dict, str]:
    lead = _withdraw(api, _web_lead(api, factory))
    lead = _reconsent(api, lead).data
    return lead, _evidence(api, lead["id"])[0]["id"]


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE lead_activity SET description = 'rewritten' WHERE id = :id",
        "UPDATE lead_activity SET subject = 'Nothing happened' WHERE id = :id",
        "UPDATE lead_activity SET metadata = NULL WHERE id = :id",
        "UPDATE lead_activity SET completed_on = created_on WHERE id = :id",
        "UPDATE lead_activity SET is_deleted = true, deleted_on = created_on, deleted_by = created_by WHERE id = :id",
        "UPDATE lead_activity SET description = '[anonymized]' WHERE id = :id",  # not an anonymized lead
        "DELETE FROM lead_activity WHERE id = :id",
    ],
    ids=["note", "subject", "metadata", "time", "soft-delete", "fake-erasure", "delete"],
)
def test_RR12_d_consent_history_is_immutable_in_the_database(api, founder, factory, statement):
    lead, act_id = _consent_activity(api, factory)
    before = _metadata(act_id)
    _refused(statement, id=act_id)
    assert _metadata(act_id) == before
    assert _evidence(api, lead["id"])[0]["description"] == RECONSENT_NOTE


def test_RR12_d_snapshot_tampering_is_refused(api, founder, factory, engine):
    _, act_id = _consent_activity(api, factory)
    if engine == "sqlite":
        forged = "json_set(metadata, '$.previous.channel', 'IN_PERSON')"
    else:
        forged = "jsonb_set(metadata, '{previous,channel}', '\"IN_PERSON\"')"
    _refused(f"UPDATE lead_activity SET metadata = {forged} WHERE id = :id", id=act_id)


def test_RR12_d_ordinary_activities_stay_editable_and_cannot_be_forged_into_evidence(api, founder, factory):
    lead = _web_lead(api, factory)
    r = api.post(
        f"/api/v1/leads/{lead['id']}/activities",
        {"activity_type": "CALL", "subject": "Intro call", "activity_status": "COMPLETED", "direction": "OUTBOUND"},
    )
    assert r.status == 201, r
    act_id = r.data["id"]
    _sql("UPDATE lead_activity SET subject = 'Intro call (edited)' WHERE id = :id", id=act_id)
    forged = json.dumps({"consent_event": "CAPTURED", "previous": None, "recorded": {"policy_version": POLICY}})
    _refused("UPDATE lead_activity SET metadata = :m WHERE id = :id", id=act_id, m=forged)


def test_RR12_d_the_api_still_refuses_to_edit_or_delete_consent_history(api, founder, factory):
    lead, act_id = _consent_activity(api, factory)
    act = next(a for a in api.get(f"/api/v1/leads/{lead['id']}/activities").data if a["id"] == act_id)
    url = f"/api/v1/leads/{lead['id']}/activities/{act_id}"
    assert api.patch(url, {"subject": "x"}, if_match=act["version"]).code == "SYSTEM_ACTIVITY_READ_ONLY"
    assert api.delete(url, if_match=act["version"]).code == "SYSTEM_ACTIVITY_READ_ONLY"


def test_RR12_d_readiness_requires_the_consent_guard(app, client):
    assert client.get("/health/ready").status_code == 200
    with db.engine().begin() as conn:
        migration_support.drop_consent_evidence_guard(conn)
    try:
        r = client.get("/health/ready")
        assert r.status_code == 503 and r.get_json()["checks"]["immutability_guards"] == "missing"
    finally:
        with db.engine().begin() as conn:
            migration_support.create_consent_evidence_guard(conn)
    assert client.get("/health/ready").status_code == 200


# --- erasure stays possible (07 §8.2, AM-4 exemption) ------------------------------------------------------------


def _erase(api, lead_id: str):
    lead = _get(api, lead_id)
    r = api.post(
        f"/api/v1/leads/{lead_id}/erasure",
        {"request_ref": "DPR-2026-012", "legal_basis": "DPDP s.12 erasure", "reason": "customer asked"},
        if_match=lead["version"],
    )
    assert r.status in (200, 204), r


def test_RR12_erasure_anonymizes_the_snapshot_and_keeps_the_evidence(api, founder, factory):
    lead = _web_lead(api, factory)
    api.post(
        f"/api/v1/leads/{lead['id']}/consent/withdraw",
        {"channel": "EMAIL", "note": WITHDRAWAL_NOTE},
        if_match=lead["version"],
    )
    assert _reconsent(api, _get(api, lead["id"])).status == 200
    act_id = _evidence(api, lead["id"])[0]["id"]
    _erase(api, lead["id"])
    meta = _metadata(act_id)
    assert meta["previous"]["withdrawal_note"] == "[anonymized]" and meta["previous"]["source_page"] is None
    assert meta["previous"]["policy_version"] == POLICY and meta["previous"]["channel"] == "WEBSITE_FORM"
    assert meta["recorded"]["channel"] == "PHONE_VERBAL" and meta["consent_event"] == "RECAPTURED"
    assert rows(sa.select(LeadActivity).where(LeadActivity.id == act_id))[0].description == "[anonymized]"
    # After erasure the evidence is frozen again: no second rewrite, no deletion.
    _refused("UPDATE lead_activity SET description = 'back' WHERE id = :id", id=act_id)
    _refused("DELETE FROM lead_activity WHERE id = :id", id=act_id)
    # The historical audit payloads lose the personal text too (07 §8.2 steps 2 to 7, with its verification).
    assert maintenance.run_erasure_audit() >= 1
    history = json.dumps([[a.old_value, a.new_value] for a in audits(lead["id"])], default=str)
    history += json.dumps(
        [[a.old_value, a.new_value] for a in rows(sa.select(AuditLog).where(AuditLog.parent_entity_id == lead["id"]))],
        default=str,
    )
    assert WITHDRAWAL_NOTE not in history and RECONSENT_NOTE not in history


def test_RR12_erasure_of_a_withdrawn_lead_removes_the_withdrawal_note(api, founder, factory):
    lead = _web_lead(api, factory)
    api.post(
        f"/api/v1/leads/{lead['id']}/consent/withdraw",
        {"channel": "EMAIL", "note": WITHDRAWAL_NOTE},
        if_match=lead["version"],
    )
    _erase(api, lead["id"])
    assert maintenance.run_erasure_audit() >= 1
    history = json.dumps([[a.old_value, a.new_value] for a in audits(lead["id"])], default=str)
    assert WITHDRAWAL_NOTE not in history
    with db.engine().connect() as conn:
        note = conn.execute(sa.text("SELECT consent_withdrawal_note FROM lead WHERE id = :id"), {"id": lead["id"]})
        assert note.scalar() is None


# --- backward compatibility -----------------------------------------------------------------------------------


def _legacy_evidence(api, factory) -> tuple[dict, str]:
    """A consent activity in the pre-RR-12 shape: no withdrawal_note key, written before the guard existed."""
    lead, act_id = _consent_activity(api, factory)
    with db.engine().begin() as conn:
        migration_support.drop_consent_evidence_guard(conn)
    try:
        meta = _metadata(act_id)
        meta["previous"].pop("withdrawal_note")
        meta["previous"]["source_page"] = "/contact?utm=mail"
        _sql("UPDATE lead_activity SET metadata = :m WHERE id = :id", id=act_id, m=json.dumps(meta))
    finally:
        with db.engine().begin() as conn:
            migration_support.create_consent_evidence_guard(conn)  # what 0010 does to existing rows
    return lead, act_id


def test_RR12_compat_legacy_evidence_is_readable_and_protected(api, founder, factory):
    lead, act_id = _legacy_evidence(api, factory)
    previous = _evidence(api, lead["id"])[0]["consent_evidence"]["previous"]
    assert "withdrawal_note" not in previous and previous["policy_version"] == POLICY
    _refused("UPDATE lead_activity SET description = 'x' WHERE id = :id", id=act_id)
    _refused("DELETE FROM lead_activity WHERE id = :id", id=act_id)


def test_RR12_compat_legacy_evidence_can_still_be_erased(api, founder, factory):
    lead, act_id = _legacy_evidence(api, factory)
    _erase(api, lead["id"])
    meta = _metadata(act_id)
    assert meta["previous"]["source_page"] is None and "withdrawal_note" not in meta["previous"]


def test_RR12_compat_n_minus_1_erasure_rewrite_is_admitted(api, founder, factory):
    """The previous image anonymizes the note only and leaves the metadata alone; on 0010 that still works."""
    lead, act_id = _consent_activity(api, factory)
    _refused("UPDATE lead_activity SET description = '[anonymized]' WHERE id = :id", id=act_id)
    _sql("UPDATE lead SET anonymized_on = updated_on WHERE id = :id", id=lead["id"])
    _sql(
        "UPDATE lead_activity SET description = '[anonymized]', version = version + 1, updated_on = updated_on"
        " WHERE id = :id",
        id=act_id,
    )
    assert rows(sa.select(LeadActivity).where(LeadActivity.id == act_id))[0].description == "[anonymized]"


def test_RR12_compat_migration_round_trip(tmp_path, engine):
    """0010 adds only triggers to a 0009 schema; the result is conformant, and like every revision it has no
    down-migration (02 §12.4)."""
    from alembic import command
    from alembic.config import Config

    from tests.conftest import ROOT
    from tests.support import pg
    from veda.kernel import conformance
    from veda.kernel.ids import new_id

    if engine == "sqlite":
        url = f"sqlite:///{tmp_path / 'rr12.db'}"
    else:
        name = f"veda_rr12_{new_id()[-10:]}"
        pg.admin(f"CREATE DATABASE {name}")
        url = pg.url(name)
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["url"] = url
    cfg.attributes["skip_logging"] = True

    def triggers() -> set[str]:
        eng = db.create_engine(url)
        try:
            with eng.connect() as conn:
                if engine == "sqlite":
                    sql = "SELECT name FROM sqlite_master WHERE type = 'trigger'"
                else:
                    sql = "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"
                return {r[0] for r in conn.exec_driver_sql(sql)}
        finally:
            eng.dispose()

    try:
        command.upgrade(cfg, "0009_mfa_challenge_binding")
        assert not set(migration_support.CONSENT_GUARD) & triggers()
        command.upgrade(cfg, "head")
        assert set(migration_support.CONSENT_GUARD) <= triggers()
        with pytest.raises(NotImplementedError):
            command.downgrade(cfg, "0009_mfa_challenge_binding")
        assert set(migration_support.CONSENT_GUARD) <= triggers()
        eng = db.create_engine(url)
        with eng.begin() as conn:
            assert migration_support.guards_present(conn) and conformance.check(conn).ok
        eng.dispose()
    finally:
        if engine != "sqlite":
            pg.admin(f"DROP DATABASE IF EXISTS {name} WITH (FORCE)")
