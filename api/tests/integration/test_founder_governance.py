"""TD-G: Founder-governance negative suite (RBAC-021, MFA-015, RBAC-020, N-01)."""

import json
import threading
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import events, get, rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.platform.auth.models import UserMfaFactor
from veda.platform.identity.models import User
from veda.platform.rbac import governance, guards
from veda.platform.rbac.models import AdminApprovalRequest, Role, UserRole

K1, K2 = "arn:aws:iam::111111111111:user/custodian-a", "arn:aws:iam::111111111111:user/custodian-b"


def assert_invariants():
    with db.unit_of_work(write=False) as s:
        state = guards.evaluate(s)
    assert state.i3, state.problems


def request(api, action, target_id, **extra):
    return api.post("/api/v1/founder-actions", {"action": action, "target_user_id": target_id, "reason": "governance test",
                                                **extra})


def test_G1_self_approval_refused(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    r = request(api, "GRANT_FOUNDER", s.id)
    assert r.status == 202 and r.data["channel"] == "IN_APP"
    approval = r.data["approval_id"]
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "self"})
    assert r.status == 403 and r.code == "APPROVER_NOT_ELIGIBLE"
    assert get(AdminApprovalRequest, approval).status == "PENDING"
    assert not events("FOUNDER_ACTION_DENIED")
    del f2
    assert_invariants()


@pytest.mark.settings(break_glass_custodians={K1: "F1-HUMAN", K2: "external:Auditor"})
def test_G2_G12_single_founder_mode_break_glass(api, factory, app):
    from veda import config

    f1 = factory.user(founder=True)
    config.settings().break_glass_custodians = {K1: f1.id, K2: "external:Auditor"}
    s = factory.user("SALES")
    factory.login(api, f1)
    r = request(api, "GRANT_FOUNDER", s.id)
    assert r.status == 202 and r.data["channel"] == "BREAK_GLASS" and r.data["not_before"]
    approval = r.data["approval_id"]
    with actor(system_context("CLI")), db.unit_of_work(write=True) as sess:
        req = sess.get(AdminApprovalRequest, approval)
        with pytest.raises(Exception) as exc:
            governance.break_glass_approve(sess, req, principal_arn=K1)  # same human as the requester (G2)
        assert "APPROVER_NOT_ELIGIBLE" in str(exc.value)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as sess:
        req = sess.get(AdminApprovalRequest, approval)
        governance.break_glass_approve(sess, req, principal_arn=K2)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as sess:
        req = sess.get(AdminApprovalRequest, approval)
        with pytest.raises(Exception) as exc:
            governance.break_glass_execute(sess, req)  # before not_before
        assert "INVALID_STATE" in str(exc.value)
    clock.advance(timedelta(hours=24, minutes=1))
    from veda.platform import maintenance

    assert maintenance.execute_due_break_glass() == 1
    assert get(AdminApprovalRequest, approval).status == "EXECUTED"
    target = get(User, s.id)
    assert target.protection_level == "FOUNDER"
    assert {e.event_type for e in events()} >= {"BREAK_GLASS_REQUESTED", "BREAK_GLASS_APPROVED", "BREAK_GLASS_EXECUTED",
                                                 "FOUNDER_ACTION_EXECUTED", "FOUNDER_TRANSITION"}
    assert_invariants()


@pytest.mark.settings(break_glass_custodians={K2: "external:Auditor"})
def test_G12_cancel_link_by_notified_party(api, factory):
    from veda.platform.notifications import worker
    from veda.platform.notifications.email import CaptureEmailProvider

    f1 = factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    worker.drain_all()
    msg = next(m for m in CaptureEmailProvider.sent if f1.email in m.to and "break-glass" in m.text.lower())
    token = msg.text.split("#token=")[1].split()[0]
    assert api.post("/api/v1/approvals/cancel-link", {"token": token}, anonymous=True).status == 204
    req = get(AdminApprovalRequest, approval)
    assert req.status == "CANCELLED" and req.status_reason == "CANCELLED_BY_NOTIFIED_PARTY"
    assert events("BREAK_GLASS_CANCELLED")


def test_G3_duplicate_approvers(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    factory.login(api, f2)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"})
    assert r.status == 200 and r.data["status"] == "EXECUTED"
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "again"}).code == "INVALID_STATE"
    factory.login(api, f3)
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "third"}).code == "INVALID_STATE"
    assert get(AdminApprovalRequest, approval).approver_user_id == f2.id
    assert_invariants()


def test_G4_direct_founder_role_grant_blocked(api, factory):
    f1 = factory.user(founder=True)
    admin = factory.user("ADMIN")
    s = factory.user("SALES")
    founder_role = factory.role_id("FOUNDER")
    for who in (f1, admin):
        factory.login(api, who)
        r = api.put(f"/api/v1/users/{s.id}/roles", {"roles": [{"role_id": factory.role_id("SALES")},
                                                               {"role_id": founder_role}], "reason": "bypass"})
        assert r.status == 403 and r.code in ("FOUNDER_GOVERNANCE_REQUIRED",), r
    assert len(events("FOUNDER_GOVERNANCE_BYPASS_BLOCKED")) >= 2
    r = api.post("/api/v1/users", {"email": "new@vedaspaces.test", "full_name": "New", "role_ids": [founder_role]})
    assert r.code == "FOUNDER_GOVERNANCE_REQUIRED"
    assert_invariants()


def test_G5_direct_founder_manage_grant_or_deny_blocked(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    r = api.post(f"/api/v1/users/{s.id}/permissions", {"permission_code": "user.founder.manage", "reason": "bypass"})
    assert r.code == "FOUNDER_GOVERNANCE_REQUIRED"
    r = api.post(f"/api/v1/users/{f2.id}/permissions", {"permission_code": "user.founder.manage", "effect": "DENY",
                                                        "reason": "bypass"})
    assert r.code == "FOUNDER_GOVERNANCE_REQUIRED"
    assert_invariants()


def test_G6_role_definition_bypass_blocked(api, factory):
    f1 = factory.user(founder=True)
    factory.login(api, f1)
    sales_role, founder_role = factory.role_id("SALES"), factory.role_id("FOUNDER")
    r = api.put(f"/api/v1/roles/{sales_role}/permissions", {"permissions": [{"permission_code": "user.founder.manage"}],
                                                            "reason": "bypass"})
    assert r.code == "FOUNDER_GOVERNANCE_REQUIRED"
    assert api.post("/api/v1/roles", {"code": "FOUNDER_COPY", "name": "Copy", "copy_from_role_id": founder_role}).code == \
        "FOUNDER_GOVERNANCE_REQUIRED"
    v = api.get(f"/api/v1/roles/{founder_role}").data["version"]
    assert api.patch(f"/api/v1/roles/{founder_role}", {"name": "Owner"}, if_match=v).code == "FOUNDER_GOVERNANCE_REQUIRED"
    assert api.delete(f"/api/v1/roles/{founder_role}", if_match=v).code == "FOUNDER_GOVERNANCE_REQUIRED"
    assert_invariants()


def test_G7_approval_after_eligibility_revoked(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    f2_token = factory.login(api, f2)
    with actor(system_context()), db.unit_of_work(write=True) as sess:
        f = sess.execute(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == f2.id)).scalar_one()
        f.status, f.revoked_on, f.revoke_reason = "REVOKED", db.tx_time(sess), "ADMIN_RESET"
        sess.get(User, f2.id).authz_version += 1
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"}, token=f2_token)
    assert r.status == 403 and r.code in ("APPROVER_NOT_ELIGIBLE", "PERMISSION_DENIED")
    assert get(AdminApprovalRequest, approval).status == "PENDING"


def test_G8_requester_loses_eligibility(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    with actor(system_context()), db.unit_of_work(write=True) as sess:
        sess.get(User, f1.id).security_cooling_off_until = db.tx_time(sess) + timedelta(hours=24)
    factory.login(api, f2)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"})
    assert r.status == 200 and r.data["status"] == "CANCELLED" and r.data["status_reason"] == "REQUESTER_INELIGIBLE"
    assert get(User, s.id).protection_level == "STANDARD"
    assert events("FOUNDER_ACTION_CANCELLED")


def test_G9_non_founder_approver(api, factory):
    f1, _f2 = factory.user(founder=True), factory.user(founder=True)
    admin = factory.user("ADMIN")
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    factory.login(api, admin)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"})
    assert r.status == 403 and r.code == "APPROVER_NOT_ELIGIBLE"
    assert all(a["id"] != approval for a in api.get("/api/v1/approvals").data), "never shown to non-eligible users"


def test_G10_concurrent_founder_requests_and_execution(api, factory, engine):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    assert request(api, "GRANT_FOUNDER", s.id).status == 202
    r = request(api, "GRANT_FOUNDER", s.id)
    assert r.status == 409 and r.code == "REQUEST_ALREADY_OPEN"
    # Two approved self step-downs executed concurrently: exactly one EXECUTED, one FAILED (LAST_FOUNDER).
    ids = []
    with actor(system_context()), db.unit_of_work(write=True) as sess:
        for requester, target in ((f1, f1), (f2, f2)):
            req = AdminApprovalRequest(action_class="FOUNDER", action_type="REVOKE_FOUNDER", channel="IN_APP",
                                       target_user_id=target.id, requested_by=requester.id, request_payload={},
                                       reason="step down", status="APPROVED", expires_on=db.tx_time(sess) + timedelta(hours=1))
            sess.add(req)
            sess.flush()
            ids.append(req.id)
    # (The GRANT request for S stays open for S; these target f1 and f2.)
    barrier = threading.Barrier(2)
    results = {}

    def run(rid):
        barrier.wait()
        with actor(system_context()), db.unit_of_work(write=True) as sess:
            req = sess.get(AdminApprovalRequest, rid)
            governance.execute(sess, req)
            results[rid] = (req.status, req.status_reason)

    threads = [threading.Thread(target=run, args=(rid,)) for rid in ids]
    [t.start() for t in threads]
    [t.join() for t in threads]
    statuses = sorted(v[0] for v in results.values())
    assert statuses == ["EXECUTED", "FAILED"], results
    assert any(v == ("FAILED", "LAST_FOUNDER") for v in results.values()), results
    assert_invariants()
    with db.unit_of_work(write=False) as sess:
        assert guards.evaluate(sess).i1


def test_G11_last_founder_cannot_be_removed(api, factory):
    f1 = factory.user(founder=True)
    factory.login(api, f1)
    assert request(api, "REVOKE_FOUNDER", f1.id).code == "LAST_FOUNDER"
    assert request(api, "FOUNDER_STATUS_CHANGE", f1.id, status="DISABLED").code == "LAST_FOUNDER"


def test_G13_bootstrap_misuse_refused(api, factory, capsys):
    from veda.cli.main import main

    f1 = factory.user(founder=True)
    assert main(["bootstrap-founder", "--email", "second@vedaspaces.test", "--name", "Second"]) == 2
    with actor(system_context()), db.unit_of_work(write=True) as sess:
        sess.get(User, f1.id).is_deleted = True
    assert main(["bootstrap-founder", "--email", "second@vedaspaces.test", "--name", "Second"]) == 2


def test_AUTH_014_bootstrap_creates_one_invited_founder(api, capsys):
    from veda.cli.main import main

    assert main(["bootstrap-founder", "--email", "founder@vedaspaces.test", "--name", "Founder One"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["invite_link"].startswith("http://localhost:5173/accept-invite#token=")
    user = get(User, out["user_id"])
    assert user.status == "INVITED" and user.protection_level == "FOUNDER"
    assert events("BOOTSTRAP_FOUNDER")[0].severity == "CRITICAL"
    token = out["invite_link"].split("#token=")[1]
    r = api.post("/api/v1/auth/invite/accept", {"token": token, "new_password": "Studio-Evening-Lantern-5"}, anonymous=True)
    assert r.data["status"] == "MFA_ENROLLMENT_REQUIRED", "invite acceptance forces MFA enrollment"
    assert main(["bootstrap-founder", "--email", "x@vedaspaces.test", "--name", "X"]) == 2
    assert_invariants()


def test_G14_i3_drift_detected_by_nightly_job(api, factory):
    from veda.platform import maintenance

    factory.user(founder=True)
    s = factory.user("SALES")
    with actor(system_context()), db.unit_of_work(write=True) as sess:
        role_id = sess.execute(sa.select(Role.id).where(Role.code == "FOUNDER")).scalar_one()
        sess.add(UserRole(user_id=s.id, role_id=role_id, reason="out-of-band edit"))
    result = maintenance.check_invariants()
    assert result["i3"] is False
    assert events("GOVERNANCE_INVARIANT_FAILED")[0].severity == "CRITICAL"
    with db.unit_of_work(write=False) as sess:
        assert not governance.structurally_eligible(sess, sess.get(User, s.id), "user.founder.manage")


def test_grant_founder_in_steady_state_executes(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s = factory.user("SALES")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", s.id).data["approval_id"]
    factory.login(api, f2)
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "welcome"}).data["status"] == "EXECUTED"
    user = get(User, s.id)
    assert user.protection_level == "FOUNDER"
    assert rows(sa.select(UserRole).where(UserRole.user_id == s.id, UserRole.role_id == factory.role_id("FOUNDER")))
    assert_invariants()
