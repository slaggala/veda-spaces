"""Audit capture (12 §4.2) and the security event log (12 §4.3)."""

import re
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import audits, events, rows
from veda import config
from veda.kernel import clock, db
from veda.kernel.context import AuditContextMissing, actor, system_context
from veda.platform.auth import security_events
from veda.platform.identity.models import User
from veda.platform.lookups.models import LookupValue
from veda.platform.notifications.models import OutboxEvent

# --- audit capture (AUDIT-*, DATA-015) ------------------------------------------------------------


def test_AUDIT_001_full_lifecycle_rows_with_actor_and_transaction(api, factory):
    founder = factory.user(founder=True)
    factory.login(api, founder)
    lead = factory.lead(api, founder.token)
    rows_ = audits(lead["id"])
    create = rows_[0]
    assert create.action == "CREATE" and create.performed_by == founder.id and create.performed_via == "API"
    assert (
        create.request_id and create.session_id and create.transaction_id and create.new_value["name"] == "Anita Reddy"
    )
    same_tx = audits(transaction_id=create.transaction_id)
    assert {r.entity_type for r in same_tx} >= {"lead", "lead_activity"}, "one transaction id per unit of work"
    api.patch(f"/api/v1/leads/{lead['id']}", {"priority": "HIGH"}, if_match=lead["version"])
    upd = audits(lead["id"], action="UPDATE")[-1]
    assert upd.old_value == {"priority": "MEDIUM"} and upd.new_value == {"priority": "HIGH"}
    assert upd.changed_fields == ["priority"]


def test_AUDIT_005_redaction(api, factory):
    sales = factory.user("SALES")
    cred_rows = audits(entity_type="user_credential", parent_entity_id=sales.id)
    assert cred_rows and cred_rows[0].new_value["password_hash"] == "[REDACTED]"
    factor_rows = audits(entity_type="user_mfa_factor")
    for r in audits(entity_type="user_mfa_factor"):
        for key in ("secret_ciphertext", "wrapped_data_key"):
            assert (r.new_value or {}).get(key) in (None, "[REDACTED]")
    del factor_rows
    for r in audits():
        blob = str(r.old_value) + str(r.new_value)
        assert "$argon2id$" not in blob


def test_AUDIT_010_write_without_actor_context_is_refused(app):
    with pytest.raises(AuditContextMissing):
        with db.unit_of_work(write=True) as s:
            s.add(
                LookupValue(
                    category_id=s.execute(sa.select(LookupValue.category_id)).scalars().first(), code="X", label="X"
                )
            )


def test_DATA_015_atomicity_forced_error_leaves_nothing(app):
    before_leads = len(rows(sa.select(User)))
    before_audit = len(audits())
    before_outbox = len(rows(sa.select(OutboxEvent)))
    with pytest.raises(RuntimeError):
        with actor(system_context()), db.unit_of_work(write=True) as s:
            u = User(
                email="x@vedaspaces.test",
                email_normalized="x@vedaspaces.test",
                full_name="X",
                user_type="HUMAN",
                status="INVITED",
                status_changed_on=db.tx_time(s),
                protection_level="STANDARD",
                authz_version=1,
            )
            s.add(u)
            s.flush()
            from veda.kernel import outbox

            outbox.enqueue(s, "user.invited", "app_user", u.id, user_id=u.id)
            s.flush()
            raise RuntimeError("forced after flush")
    assert len(rows(sa.select(User))) == before_leads
    assert len(audits()) == before_audit and len(rows(sa.select(OutboxEvent))) == before_outbox


def test_AUDIT_parent_linkage_and_excluded_only_updates(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)  # updates last_login_on (excluded) only
    user_updates = [r for r in audits(sales.id, action="UPDATE")]
    assert user_updates == [], "an UPDATE of only excluded fields writes no audit row"
    cred = audits(entity_type="user_credential", parent_entity_id=sales.id)
    assert cred[0].parent_entity_type == "app_user"


def test_A12_audit_viewer_masks_out_of_scope_lead_pii(api, factory):
    founder = factory.user(founder=True)
    admin = factory.user("ADMIN")
    factory.login(api, founder)
    lead = factory.lead(api, founder.token, name="Private Person")
    # Admin has lead.read ALL → sees PII; a custom auditor with audit.read but OWN lead scope sees masks.
    auditor = factory.user("SALES", mfa=True)
    factory.grant(auditor, "audit.read")
    factory.login(api, auditor)
    r = api.get(f"/api/v1/audit-logs?entity_type=lead&entity_id={lead['id']}")
    assert r.status == 200 and r.data
    create = next(x for x in r.data if x["action"] == "CREATE")
    assert create["new_value"]["name"] == "[MASKED]" and create["entity_label"] is None
    factory.login(api, admin)
    create = next(x for x in api.get(f"/api/v1/audit-logs?entity_id={lead['id']}").data if x["action"] == "CREATE")
    assert create["new_value"]["name"] == "Private Person" and "Private Person" in create["entity_label"]
    assert create["new_value"]["source_id"]["code"] == "REFERRAL", "lookup ids resolved to labels at read time"
    detail = api.get(f"/api/v1/audit-logs/{create['id']}").data
    assert "user_agent" in detail and "session_id" in detail


def test_audit_viewer_cursor_pagination(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    first = api.get("/api/v1/audit-logs?limit=5")
    assert len(first.data) == 5 and first.json["meta"]["has_more"]
    second = api.get(f"/api/v1/audit-logs?limit=5&cursor={first.json['meta']['next_cursor']}")
    assert {x["id"] for x in first.data}.isdisjoint({x["id"] for x in second.data})
    assert api.get("/api/v1/audit-logs?cursor=garbage").code == "INVALID_QUERY_PARAM"


# --- security events (SEVT-*) ---------------------------------------------------------------------


def test_SEVT_006_keyed_chain_verifies_and_detects_tampering(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/login", {"email": sales.email, "password": "bad-password-1"}, anonymous=True)
    with db.unit_of_work(write=False) as s:
        report = security_events.verify_chain(s)
    assert report.ok and report.checked >= 2
    seqs = [e.chain_seq for e in events()]
    assert seqs == list(range(1, len(seqs) + 1)), "gap-free"
    # Recomputing with a wrong key fails.
    cfg = config.settings()
    original = dict(cfg.chain_keys)
    cfg.chain_keys = {k: b"wrong-key" * 4 for k in original}
    with db.unit_of_work(write=False) as s:
        assert not security_events.verify_chain(s).ok
    cfg.chain_keys = original
    # Tamper with a row behind the application's back (guards lifted as an attacker with DB access would).
    from veda.kernel import migration_support

    with db.engine().begin() as conn:
        migration_support.drop_immutability_guards(conn, "security_event_log")
        conn.execute(sa.text("UPDATE security_event_log SET ip_address = '6.6.6.6' WHERE chain_seq = 2"))
        migration_support.restore_immutability_guards(conn, "security_event_log")
    with db.unit_of_work(write=False) as s:
        report = security_events.verify_chain(s)
    assert not report.ok and report.at_seq == 2 and report.problem == "row_hash mismatch"
    from veda.platform import maintenance

    assert not maintenance.verify_chain().ok
    assert events("SECURITY_LOG_CHAIN_BROKEN")


def test_SEVT_007_anchor_and_verify_from_anchor(api, factory):
    from veda.platform import maintenance

    factory.login(api, factory.user("SALES"))
    anchor = maintenance.anchor_chain()
    assert anchor and maintenance.latest_anchor()["row_hash"] == anchor["row_hash"]
    factory.login(api, factory.user("SALES"))
    assert maintenance.verify_chain().ok
    assert events("SECURITY_LOG_CHAIN_ANCHORED")


def test_SEVT_JCS_is_engine_independent(api, factory):
    factory.login(api, factory.user("SALES"))
    row = events("LOGIN")[0]
    rep = security_events.row_representation(row)
    assert re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$", rep["created_on"])
    assert re.match(r"^[0-9a-f]{32}$", rep["id"]) and isinstance(rep["is_deleted"], bool)
    assert "row_hash" not in rep and "prev_hash" not in rep


def test_SEVT_003_detail_allow_list_and_prohibited_content(app):
    with actor(system_context()), db.unit_of_work(write=True) as s:
        with pytest.raises(security_events.SecurityEventError):
            security_events.record(s, "LOGIN", "SUCCESS", detail={"password": "x"})
        with pytest.raises(security_events.SecurityEventError):
            security_events.record(s, "LOGIN", "SUCCESS", detail={"favourite": "x"})
        with pytest.raises(security_events.SecurityEventError):
            security_events.record(s, "LOGIN", "SUCCESS", detail={"method": "x" * 201})
        with pytest.raises(security_events.SecurityEventError):
            security_events.record(s, "NOT_AN_EVENT", "SUCCESS")


def test_SEVT_003_no_secret_shaped_values_in_any_event(api, factory):
    admin = factory.user("ADMIN")
    token = factory.login(api, admin)
    api.post("/api/v1/auth/password/forgot", {"email": admin.email}, anonymous=True)
    api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)
    for e in events():
        blob = " ".join(str(v) for v in (e.detail, e.failure_reason, e.permission_code, e.user_agent))
        assert token not in blob and "$argon2" not in blob
        assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}", blob), "no JWT-shaped values"
        if e.detail:
            assert not set(e.detail) & security_events.PROHIBITED_DETAIL_KEYS


def test_SEVT_011_failure_events_survive_rollback(api, factory):
    api.post("/api/v1/auth/login", {"email": "ghost@vedaspaces.test", "password": "nope-nope-nope"}, anonymous=True)
    assert events("LOGIN", outcome="FAILURE")


def test_F06_sensitive_reads_recorded_and_deduplicated(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    for _ in range(3):
        api.get("/api/v1/security-events")
        api.get("/api/v1/audit-logs")
    reads = events("SENSITIVE_READ", subject_user_id=admin.id)
    assert sorted(e.permission_code for e in reads) == ["audit.read", "security_event.read"]
    clock.advance(timedelta(minutes=16))
    factory.login(api, admin)
    api.get("/api/v1/audit-logs")
    assert len(events("SENSITIVE_READ", subject_user_id=admin.id)) == 3


def test_SEVT_005_listing_never_returns_chain_columns(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    r = api.get("/api/v1/security-events?event_type=LOGIN")
    assert r.status == 200 and r.data
    for item in r.data:
        assert not {"chain_seq", "prev_hash", "row_hash", "chain_key_label", "email_attempted_hash"} & set(item)
    assert api.get("/api/v1/security-events?from=2026-01-01T00:00:00Z").code == "INVALID_QUERY_PARAM"


def test_SEVT_004_archival_refuses_without_retention(app):
    from veda.platform import maintenance

    with pytest.raises(RuntimeError, match="OWNER-INPUT-002"):
        maintenance.archive_security_events()


def test_SEVT_004_archival_exports_anchors_and_deletes(api, factory, tmp_path):
    from veda.platform import maintenance

    factory.login(api, factory.user("SALES"))
    config.settings().security_event_online_retention_days = 1
    clock.advance(timedelta(days=2))
    result = maintenance.archive_security_events(str(tmp_path))
    assert result["archived"] >= 1
    remaining = events()
    assert remaining and remaining[-1].event_type == "SECURITY_LOG_ARCHIVED"
    assert maintenance.verify_chain().ok, "verification starts from the archival anchor"
