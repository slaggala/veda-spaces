"""Final merge-blocker remediation (targeted re-review RR-02, RR-03, RR-08; owner decisions OD-2, OD-3).

* RR-02 / OD-2: a deleted Founder is restored only through FOUNDER_STATUS_CHANGE status=RESTORE, requested by one
  eligible Founder and approved by a second; generic user endpoints and break-glass cannot restore one.
* RR-03 / OD-3: work authorised under a weaker governance class than the target now holds fails closed; the
  reviewer's N17 reproducer (an executed STANDARD email change verified after promotion to Founder) is refused.
* RR-08: every refresh-token rotation links the successor, so the grace window applies after path-A enrollment
  and after a password change.
"""

import threading
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_founder_governance import K1, K2, assert_invariants, request
from tests.integration.test_mfa import code_for, link_from, secret_from_uri
from tests.support.api import ApiClient
from tests.support.dbh import audits, events, get, rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.errors import ApiError
from veda.platform import maintenance
from veda.platform.auth import security_events
from veda.platform.auth.models import RefreshToken, UserMfaFactor, UserSession
from veda.platform.identity.models import User
from veda.platform.rbac import governance
from veda.platform.rbac.models import AdminApprovalRequest

APPROVE = "/api/v1/approvals/{}/approve"


def _version(api, user_id):
    return api.get(f"/api/v1/users/{user_id}", token=api.token).data["version"]


def _delete_founder(api, factory, requester, approver, target):
    factory.login(api, requester)
    approval = request(api, "FOUNDER_STATUS_CHANGE", target.id, status="DELETE").data["approval_id"]
    factory.login(api, approver)
    assert api.post(APPROVE.format(approval), {"reason": "left"}).data["status"] == "EXECUTED"
    assert factory.get_user(target.id).is_deleted


def _request_restore(api, target_id):
    return request(api, "FOUNDER_STATUS_CHANGE", target_id, status="RESTORE")


# --- RR-02 / OD-2: restoring a deleted Founder ------------------------------------------------------------


def test_RR02_P11_single_founder_cannot_restore_a_deleted_founder(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, f3)
    factory.login(api, f1)
    r = api.post(f"/api/v1/users/{f3.id}/restore", {})
    assert r.status == 403 and r.code == "FOUNDER_PROTECTED", r
    assert factory.get_user(f3.id).is_deleted, "the dual-control deletion stands"
    blocked = events("FOUNDER_GOVERNANCE_BYPASS_BLOCKED", subject_user_id=f3.id)
    assert blocked and blocked[-1].created_by == f1.id and blocked[-1].detail["action"] == "restore"
    assert_invariants()


def test_RR02_generic_endpoints_cannot_restore_a_founder(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, f3)
    factory.login(api, f1)
    assert api.post(f"/api/v1/users/{f3.id}/status", {"status": "ACTIVE", "reason": "back"}, if_match=1).status == 404
    assert api.post(f"/api/v1/users/{f3.id}/unlock", {}).status == 404
    assert api.put(f"/api/v1/users/{f3.id}/roles", {"roles": [], "reason": "x"}).status == 404
    assert api.post(f"/api/v1/users/{f3.id}/permissions", {"permission_code": "lead.read", "reason": "x"}).status == 404
    for status in ("ACTIVE", "UNLOCK", "DISABLED"):
        assert request(api, "FOUNDER_STATUS_CHANGE", f3.id, status=status).status == 404
    assert request(api, "GRANT_FOUNDER", f3.id).status == 404
    assert factory.get_user(f3.id).is_deleted
    # RESTORE only addresses a deleted account.
    r = _request_restore(api, f2.id)
    assert r.status == 409 and r.code == "INVALID_STATE", r


def test_RR02_two_distinct_founders_restore_through_the_workflow(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, f3)
    factory.login(api, f1)
    r = _request_restore(api, f3.id)
    assert r.status == 202 and r.data["channel"] == "IN_APP", r
    approval = r.data["approval_id"]
    # The requester cannot approve; the target (deleted, not signed in) is never eligible.
    r = api.post(APPROVE.format(approval), {"reason": "self"})
    assert r.status == 403 and r.code == "APPROVER_NOT_ELIGIBLE"
    factory.login(api, f2)
    r = api.post(APPROVE.format(approval), {"reason": "rehired"})
    assert r.status == 200 and r.data["status"] == "EXECUTED", r
    restored = factory.get_user(f3.id)
    assert not restored.is_deleted and restored.status == "DISABLED" and restored.protection_level == "FOUNDER"
    # One human cannot supply a second decision.
    assert api.post(APPROVE.format(approval), {"reason": "again"}).code == "INVALID_STATE"
    # Audit actor is the approving Founder in the executing transaction; security events are complete.
    change = [a for a in audits(f3.id) if "is_deleted" in (a.changed_fields or [])][-1]
    assert change.performed_by == f2.id and change.new_value["is_deleted"] is False
    kinds = [(e.event_type, (e.detail or {}).get("action")) for e in events(subject_user_id=f3.id)]
    assert ("FOUNDER_ACTION_REQUESTED", "FOUNDER_STATUS_CHANGE") in kinds
    assert ("FOUNDER_ACTION_APPROVED", None) in kinds
    assert ("FOUNDER_TRANSITION", "RESTORE") in kinds
    assert ("FOUNDER_ACTION_EXECUTED", "FOUNDER_STATUS_CHANGE") in kinds
    req = get(AdminApprovalRequest, approval)
    assert req.requested_by == f1.id and req.approver_user_id == f2.id and req.request_payload["status"] == "RESTORE"
    # Restored as DISABLED: reactivation is its own Founder-governed request.
    r = api.post(f"/api/v1/users/{f3.id}/status", {"status": "ACTIVE", "reason": "x"}, if_match=_version(api, f3.id))
    assert r.status == 403 and r.code == "FOUNDER_PROTECTED", r
    assert_invariants()


def test_RR02_single_eligible_founder_cannot_use_break_glass_to_restore(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, factory.user(founder=True))  # warm-up: deletion path works
    deleted = [u for u in rows(sa.select(User).where(User.is_deleted.is_(True)))][0]
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, f2.id).status = "DISABLED"  # f1 is now the only eligible Founder
    factory.login(api, f1)
    r = _request_restore(api, deleted.id)
    assert r.status == 409 and r.code == "SECOND_FOUNDER_REQUIRED", r
    assert not rows(
        sa.select(AdminApprovalRequest).where(
            AdminApprovalRequest.target_user_id == deleted.id, AdminApprovalRequest.status == "PENDING"
        )
    )


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1", K2: "external:Auditor-2"})
def test_RR02_custodian_break_glass_cannot_restore_a_founder(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, f3)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        for uid in (f1.id, f2.id):
            s.execute(sa.delete(UserMfaFactor).where(UserMfaFactor.user_id == uid))  # no eligible Founder remains
    with security_events.deferred_scope(), pytest.raises(ApiError) as exc:
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            governance.break_glass_request(
                s,
                action="FOUNDER_STATUS_CHANGE",
                target=s.get(User, f3.id, execution_options={"include_deleted": True}),
                reason="restore",
                principal_arn=K1,
                payload={"status": "RESTORE"},
            )
    assert exc.value.code == "SECOND_FOUNDER_REQUIRED"
    assert factory.get_user(f3.id).is_deleted


def test_RR02_revoked_approver_or_requester_eligibility_blocks_execution(api, factory):
    f1, f2, f3, f4 = (factory.user(founder=True) for _ in range(4))
    _delete_founder(api, factory, f1, f2, f3)
    factory.login(api, f1)
    approval = _request_restore(api, f3.id).data["approval_id"]
    t2 = factory.login(api, f2, set_default=False)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.execute(sa.delete(UserMfaFactor).where(UserMfaFactor.user_id == f2.id))  # approver loses eligibility
    r = api.post(APPROVE.format(approval), {"reason": "go"}, token=t2)
    assert r.status in (401, 403), r
    assert get(AdminApprovalRequest, approval).status == "PENDING" and factory.get_user(f3.id).is_deleted
    # The requester loses eligibility before a valid approval: the request is cancelled, nothing applied.
    t4 = factory.login(api, f4, set_default=False)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, f1.id).status = "DISABLED"
    r = api.post(APPROVE.format(approval), {"reason": "go"}, token=t4)
    assert r.data["status"] == "CANCELLED" and r.data["status_reason"] == "REQUESTER_INELIGIBLE", r
    assert factory.get_user(f3.id).is_deleted


def test_RR02_stale_restore_fails_closed(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    _delete_founder(api, factory, f1, f2, f3)
    factory.login(api, f1)
    approval = _request_restore(api, f3.id).data["approval_id"]
    reissued = factory.user("SALES", email=f3.email)  # the address was reissued meanwhile
    factory.login(api, f2)
    r = api.post(APPROVE.format(approval), {"reason": "go"})
    assert r.data["status"] == "FAILED" and r.data["status_reason"] == "DUPLICATE", r
    assert factory.get_user(f3.id).is_deleted
    assert events("FOUNDER_ACTION_FAILED", subject_user_id=f3.id)
    # An expired request can no longer be decided.
    factory.login(api, f1)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, reissued.id).is_deleted = True  # the address is free again
    approval = _request_restore(api, f3.id).data["approval_id"]
    clock.advance(timedelta(days=8))
    factory.login(api, f1)
    factory.login(api, f2)
    assert api.post(APPROVE.format(approval), {"reason": "late"}).code == "INVALID_STATE"
    assert factory.get_user(f3.id).is_deleted


def test_RR02_concurrent_restore_requests_and_approvals(app, api, factory):
    f1, f2, f4, f3 = (factory.user(founder=True) for _ in range(4))
    _delete_founder(api, factory, f1, f2, f3)
    t1, t2, t4 = (factory.login(api, u, set_default=False) for u in (f1, f2, f4))
    barrier = threading.Barrier(2)
    out = {}

    def call(name, fn):
        c = ApiClient(app.test_client())
        barrier.wait()
        out[name] = fn(c)

    body = {"action": "FOUNDER_STATUS_CHANGE", "target_user_id": f3.id, "reason": "restore", "status": "RESTORE"}
    threads = [
        threading.Thread(target=call, args=(n, lambda c, t=t: c.post("/api/v1/founder-actions", body, token=t)))
        for n, t in (("a", t1), ("b", t2))
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    statuses = sorted(r.status for r in out.values())
    assert statuses == [202, 409], out
    winner = next(r for r in out.values() if r.status == 202)
    loser = next(r for r in out.values() if r.status == 409)
    assert loser.code == "REQUEST_ALREADY_OPEN"
    approval = winner.data["approval_id"]
    requester = get(AdminApprovalRequest, approval).requested_by
    approvers = [t for u, t in ((f1, t1), (f2, t2), (f4, t4)) if u.id != requester]
    barrier = threading.Barrier(2)
    out.clear()
    threads = [
        threading.Thread(
            target=call, args=(n, lambda c, t=t: c.post(APPROVE.format(approval), {"reason": "go"}, token=t))
        )
        for n, t in zip(("x", "y"), approvers, strict=True)
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    executed = [r for r in out.values() if r.status == 200 and r.data["status"] == "EXECUTED"]
    assert len(executed) == 1, out
    assert all(r.status in (200, 409) for r in out.values()), out
    assert len(events("FOUNDER_TRANSITION", subject_user_id=f3.id)) == 1
    assert not factory.get_user(f3.id).is_deleted
    assert_invariants()


def test_RR02_standard_restore_unchanged_and_audited(api, factory):
    f1 = factory.user(founder=True)
    sales = factory.user("SALES")
    factory.login(api, f1)
    assert api.delete(f"/api/v1/users/{sales.id}", {"reason": "left"}, if_match=_version(api, sales.id)).status == 204
    r = api.post(f"/api/v1/users/{sales.id}/restore", {})
    assert r.status == 200 and r.data["status"] == "DISABLED"
    change = [a for a in audits(sales.id) if "is_deleted" in (a.changed_fields or [])][-1]
    assert change.performed_by == f1.id and change.new_value["is_deleted"] is False


# --- RR-03 / OD-3: revalidation when the target's governance class rises -----------------------------------


def _staged_admin_email_change(api, factory, admin_a, admin_b, target, new_email):
    factory.login(api, admin_a)
    r = api.post(
        f"/api/v1/users/{target.id}/email-change",
        {"new_email": new_email, "reason": "rename"},
        if_match=_version(api, target.id),
    )
    assert r.data["status"] == "APPROVAL_REQUIRED", r
    factory.login(api, admin_b)
    r = api.post(APPROVE.format(r.data["approval_id"]), {"reason": "ok"})
    assert r.data["status"] == "EXECUTED", r
    assert factory.get_user(target.id).proposed_email == new_email
    return link_from(new_email, "#token=")


def _promote(api, factory, f1, f2, target):
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", target.id).data["approval_id"]
    factory.login(api, f2)
    assert api.post(APPROVE.format(approval), {"reason": "promotion"}).data["status"] == "EXECUTED"


def test_RR03_N17_executed_standard_email_change_cannot_complete_after_promotion(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    link = _staged_admin_email_change(api, factory, admin_a, admin_b, a2, "attacker@evil.test")
    _promote(api, factory, f1, f2, a2)
    after = factory.get_user(a2.id)
    assert after.proposed_email is None, "promotion withdraws the weaker-class proposal"
    cancelled = events("EMAIL_CHANGE_CANCELLED", subject_user_id=a2.id)[-1]
    assert cancelled.detail["reason"] == "TARGET_BECAME_FOUNDER"
    assert cancelled.detail["status"] == "DUAL_CONTROL->FOUNDER_GOVERNANCE"
    assert "attacker@evil.test" not in str(cancelled.detail), "masked address only"
    r = api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True)
    assert r.status == 400 and r.code == "EMAIL_TOKEN_INVALID"
    assert factory.get_user(a2.id).email == a2.email


def test_RR03_verify_fails_closed_even_without_the_cleanup(api, factory):
    """Defence in depth: a proposal left behind (N-1 image, direct data change) never completes on a Founder."""
    factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    link = _staged_admin_email_change(api, factory, admin_a, admin_b, a2, "late@evil.test")
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, a2.id).protection_level = "FOUNDER"
    r = api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True)
    assert r.status == 400 and r.code == "EMAIL_TOKEN_INVALID"
    user = factory.get_user(a2.id)
    assert user.email == a2.email
    refused = [e for e in events("EMAIL_CHANGE_VERIFIED", subject_user_id=a2.id) if e.outcome == "FAILURE"]
    assert refused and refused[-1].detail["reason"] == "GOVERNANCE_CLASS_CHANGED"
    assert events("FOUNDER_GOVERNANCE_BYPASS_BLOCKED", subject_user_id=a2.id)


def test_RR03_standard_change_withdrawn_when_target_becomes_privileged(api, factory):
    f1 = factory.user(founder=True)
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin)
    r = api.post(
        f"/api/v1/users/{sales.id}/email-change",
        {"new_email": "sales.next@vedaspaces.test", "reason": "rename"},
        if_match=_version(api, sales.id),
    )
    assert r.data["status"] == "VERIFICATION_SENT"
    link = link_from("sales.next@vedaspaces.test", "#token=")
    factory.login(api, f1)
    r = api.put(
        f"/api/v1/users/{sales.id}/roles", {"roles": [{"role_id": factory.role_id("ADMIN")}], "reason": "promotion"}
    )
    assert r.status == 200, r
    assert factory.get_user(sales.id).proposed_email is None
    cancelled = events("EMAIL_CHANGE_CANCELLED", subject_user_id=sales.id)[-1]
    assert cancelled.detail["reason"] == "TARGET_BECAME_PRIVILEGED"
    assert api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True).code == "EMAIL_TOKEN_INVALID"


def test_RR03_privilege_via_role_definition_is_caught_at_verification(api, factory):
    """A role gaining a sensitive permission raises every holder's class without touching the user: the
    verification-time check still refuses (OD-3: eligibility recalculated after the request)."""
    factory.user(founder=True)
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin)
    api.post(
        f"/api/v1/users/{sales.id}/email-change",
        {"new_email": "sales.role@vedaspaces.test", "reason": "rename"},
        if_match=_version(api, sales.id),
    )
    link = link_from("sales.role@vedaspaces.test", "#token=")
    factory.grant(sales, "user.delete")  # now privileged (sensitive permission)
    r = api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True)
    assert r.code == "EMAIL_TOKEN_INVALID"
    assert factory.get_user(sales.id).email == sales.email


def test_RR03_self_and_founder_workflow_changes_still_complete(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    f3 = factory.user(founder=True)
    factory.login(api, f1)
    approval = request(api, "FOUNDER_EMAIL_CHANGE", f3.id, new_email="f3.new@vedaspaces.test").data["approval_id"]
    factory.login(api, f2)
    assert api.post(APPROVE.format(approval), {"reason": "ok"}).data["status"] == "EXECUTED"
    link = link_from("f3.new@vedaspaces.test", "#token=")
    assert api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True).status == 204
    assert factory.get_user(f3.id).email == "f3.new@vedaspaces.test"
    # Self-requested: promotion afterwards does not withdraw the owner's own change.
    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/reauth", {"password": sales.password})
    assert api.put("/api/v1/auth/me/email", {"new_email": "own@vedaspaces.test"}).status == 202
    link = link_from("own@vedaspaces.test", "#token=")
    factory.login(api, f1)
    api.put(f"/api/v1/users/{sales.id}/roles", {"roles": [{"role_id": factory.role_id("ADMIN")}], "reason": "p"})
    assert factory.get_user(sales.id).proposed_email == "own@vedaspaces.test"
    assert api.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True).status == 204


def test_RR03_mfa_reset_request_before_promotion_fails_closed(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    factory.login(api, admin_a)
    approval = api.post(
        f"/api/v1/users/{a2.id}/mfa/reset", {"reason": "lost phone"}, if_match=_version(api, a2.id)
    ).data["approval_id"]
    _promote(api, factory, f1, f2, a2)
    factory.login(api, admin_b)
    r = api.post(APPROVE.format(approval), {"reason": "ok"})
    assert r.status == 409 and r.code == "INVALID_STATE"
    req = get(AdminApprovalRequest, approval)
    assert req.status == "CANCELLED" and req.status_reason == "TARGET_BECAME_FOUNDER"
    assert rows(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == a2.id, UserMfaFactor.status == "ACTIVE"))
    cancelled = [e for e in events("APPROVAL_CANCELLED") if e.target_entity_id == approval]
    assert cancelled and cancelled[-1].detail["reason"] == "TARGET_BECAME_FOUNDER"


def test_RR03_founder_status_request_recalculated_when_target_changes(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    factory.login(api, f1)
    approval = request(api, "FOUNDER_STATUS_CHANGE", f3.id, status="DISABLED").data["approval_id"]
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, f3.id).protection_level = "STANDARD"  # target left the Founder class after the request
    factory.login(api, f2)
    r = api.post(APPROVE.format(approval), {"reason": "ok"})
    assert r.data["status"] == "FAILED" and r.data["status_reason"] == "INVALID_STATE", r
    assert factory.get_user(f3.id).status == "ACTIVE"


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1", K2: "external:Auditor-2"})
def test_RR03_approved_break_glass_recalculated_at_execution(api, factory):
    factory.user(founder=True, mfa=False)
    target = factory.user("ADMIN")
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        rid = governance.break_glass_request(
            s, action="GRANT_FOUNDER", target=s.get(User, target.id), reason="x", principal_arn=K1, payload={}
        ).id
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        governance.break_glass_approve(s, s.get(AdminApprovalRequest, rid), principal_arn=K2)
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, target.id).status = "DISABLED"  # target changed after approval
    clock.advance(timedelta(hours=24, minutes=1))
    maintenance.execute_due_break_glass()
    req = get(AdminApprovalRequest, rid)
    assert req.status == "FAILED" and req.status_reason == "INVALID_STATE"
    assert factory.get_user(target.id).protection_level == "STANDARD"


def test_RR03_concurrent_promotion_and_verification(app, api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    link = _staged_admin_email_change(api, factory, admin_a, admin_b, a2, "race@evil.test")
    factory.login(api, f1)
    approval = request(api, "GRANT_FOUNDER", a2.id).data["approval_id"]
    t2 = factory.login(api, f2, set_default=False)
    barrier = threading.Barrier(2)
    out = {}

    def run(name, fn):
        c = ApiClient(app.test_client())
        barrier.wait()
        out[name] = fn(c)

    threads = [
        threading.Thread(
            target=run, args=("promote", lambda c: c.post(APPROVE.format(approval), {"reason": "p"}, token=t2))
        ),
        threading.Thread(
            target=run,
            args=("verify", lambda c: c.post("/api/v1/auth/email/verify", {"token": link}, anonymous=True)),
        ),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert out["promote"].data["status"] == "EXECUTED"
    promoted = next(e.chain_seq for e in events("FOUNDER_TRANSITION", subject_user_id=a2.id))
    final = factory.get_user(a2.id)
    if out["verify"].status == 204:  # verification committed first, while a2 was still an ADMIN
        completed = next(e.chain_seq for e in events("EMAIL_CHANGE_COMPLETED", subject_user_id=a2.id))
        assert completed < promoted and final.email == "race@evil.test"
    else:
        assert out["verify"].code == "EMAIL_TOKEN_INVALID" and final.email == a2.email
        assert final.proposed_email is None


# --- RR-08: refresh successor links on every rotation --------------------------------------------------------


def _cookie(client):
    return client.get_cookie("vs_rt", path="/api/v1/auth").value


def _refresh(api):
    return api.post("/api/v1/auth/refresh", headers=api.csrf_headers(), anonymous=True)


def test_RR08_path_a_enrollment_keeps_the_grace_window(api, factory, client):
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    old = _cookie(client)
    assert api.post("/api/v1/auth/reauth", {"password": user.password}, token=token).status == 204
    r = api.post("/api/v1/auth/mfa/enroll/start", {"reauth": True}, token=token)
    challenge, secret = r.data["challenge_token"], secret_from_uri(r.data["otpauth_uri"])
    r = api.post(
        "/api/v1/auth/mfa/enroll/confirm", {"challenge_token": challenge, "code": code_for(secret)}, token=token
    )
    assert r.status == 200 and r.data["status"] == "AUTHENTICATED"
    new = _cookie(client)
    assert new != old
    # The reviewer's reproducer: a second tab presents the old cookie within 20 s → access token only.
    client.set_cookie("vs_rt", old, path="/api/v1/auth")
    r = _refresh(api)
    assert r.status == 200 and r.data["access_token"] and "Set-Cookie" not in r.headers, r
    assert not events("REFRESH_REUSE_DETECTED")
    client.set_cookie("vs_rt", new, path="/api/v1/auth")
    assert _refresh(api).status == 200, "the successor still works; the session was not revoked"
    retired = rows(sa.select(RefreshToken).where(RefreshToken.token_hash.isnot(None)))
    assert all(t.replaced_by_id is not None for t in retired if t.used_on is not None)


def test_RR08_reuse_after_the_window_is_still_theft(api, factory, client):
    user = factory.user("SALES")
    token = factory.login(api, user, set_default=False)
    old = _cookie(client)
    assert (
        api.post(
            "/api/v1/auth/password/change",
            {"current_password": user.password, "new_password": "Brand-New-Lantern-2027!"},
            token=token,
        ).status
        == 204
    )
    client.set_cookie("vs_rt", old, path="/api/v1/auth")
    r = _refresh(api)
    assert r.status == 200 and "Set-Cookie" not in r.headers, "grace applies after a password change too"
    clock.advance(timedelta(seconds=21))
    client.set_cookie("vs_rt", old, path="/api/v1/auth")
    r = _refresh(api)
    assert r.status == 401 and r.code == "SESSION_INVALID"
    detected = events("REFRESH_REUSE_DETECTED")
    assert detected and "vs_rt" not in str(detected[-1].detail or {}) and old not in str(detected[-1].detail or {})


def test_RR08_rotation_only_touches_the_rotating_session(api, factory, client):
    user = factory.user("SALES")
    factory.login(api, user, set_default=False)
    other_cookie = _cookie(client)
    token = factory.login(api, user, set_default=False)
    sessions = rows(sa.select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.id))
    assert len(sessions) == 2
    stranger = factory.user("SALES")
    factory.login(api, stranger, set_default=False)
    assert (
        api.post(
            "/api/v1/auth/password/change",
            {"current_password": user.password, "new_password": "Brand-New-Lantern-2027!"},
            token=token,
        ).status
        == 204
    )
    stranger_sessions = {s.id for s in rows(sa.select(UserSession).where(UserSession.user_id == stranger.id))}
    for t in rows(sa.select(RefreshToken)):
        if t.replaced_by_id:
            successor = get(RefreshToken, t.replaced_by_id)
            assert successor.session_id == t.session_id, "never a cross-session link"
        if t.session_id in stranger_sessions:
            assert t.used_on is None and t.replaced_by_id is None
    # The other session of the same user was revoked by the password change (05 §8.5), not linked.
    client.set_cookie("vs_rt", other_cookie, path="/api/v1/auth")
    assert _refresh(api).status == 401


def test_RR08_concurrent_refresh_yields_a_single_successor(app, api, factory, client):
    user = factory.user("SALES")
    factory.login(api, user, set_default=False)
    cookie = _cookie(client)
    barrier = threading.Barrier(3)
    results = []

    def go():
        c = app.test_client()
        c.set_cookie("vs_rt", cookie, path="/api/v1/auth")
        barrier.wait()
        r = c.post("/api/v1/auth/refresh", headers=api.csrf_headers())
        results.append((r.status_code, "vs_rt=" in (r.headers.get("Set-Cookie") or "")))

    threads = [threading.Thread(target=go) for _ in range(3)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    rotated = [ok for status, ok in results if status == 200 and ok]
    assert len(rotated) == 1, results
    session_ids = {s.id for s in rows(sa.select(UserSession).where(UserSession.user_id == user.id))}
    live = [t for t in rows(sa.select(RefreshToken)) if t.session_id in session_ids and t.used_on is None]
    assert len(live) <= 1, "one successor at most"
