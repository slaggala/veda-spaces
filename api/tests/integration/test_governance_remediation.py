"""Founder-governance remediation (independent review IR-04, IR-05, IR-06, IR-08; RBAC-021, 06 §7).

P10 (STANDARD request surviving promotion to Founder), P11/P16 (Founder DELETE), P13 (custodian
break-glass in steady state and a self-asserted second custodian) are the review's reproducers.
"""

import json
import threading
from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.integration.test_founder_governance import K1, K2, assert_invariants, request
from tests.support.api import ApiClient
from tests.support.dbh import events, get, rows
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.errors import ApiError
from veda.platform import maintenance
from veda.platform.auth import security_events
from veda.platform.identity.models import User
from veda.platform.rbac import custodians, governance, guards
from veda.platform.rbac.models import AdminApprovalRequest

K3 = "arn:aws:iam::111111111111:role/custodian-c"
SESSION_K3 = "arn:aws:sts::111111111111:assumed-role/custodian-c/ssm-session-0a1b"


def _version(api, user_id):
    return api.get(f"/api/v1/users/{user_id}").data["version"]


def _grant_founder(api, factory, requester, approver, target):
    factory.login(api, requester)
    approval = request(api, "GRANT_FOUNDER", target.id).data["approval_id"]
    factory.login(api, approver)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "promotion"})
    assert r.data["status"] == "EXECUTED", r
    return approval


# --- IR-04: STANDARD request against a target later promoted to Founder --------------------------------


def test_IR04_P10_promotion_cancels_open_standard_requests(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    admin_a, a2 = factory.user("ADMIN"), factory.user("ADMIN")
    factory.login(api, admin_a)
    r = api.post(
        f"/api/v1/users/{a2.id}/email-change",
        {"new_email": "attacker@evil.test", "reason": "rename"},
        if_match=_version(api, a2.id),
    )
    assert r.data["status"] == "APPROVAL_REQUIRED"
    stale = r.data["approval_id"]

    _grant_founder(api, factory, f1, f2, a2)
    req = get(AdminApprovalRequest, stale)
    assert req.status == "CANCELLED" and req.status_reason == "TARGET_BECAME_FOUNDER"

    factory.login(api, f1)
    r = api.post(f"/api/v1/approvals/{stale}/approve", {"reason": "looks fine"})
    assert r.status == 409 and r.code == "INVALID_STATE"
    assert factory.get_user(a2.id).proposed_email is None
    assert_invariants()


def test_IR04_execution_time_G11_fails_a_stale_standard_request(api, factory):
    """Defence in depth: a STANDARD request whose target is a Founder at execution time fails even if it was
    not cancelled (e.g. a row left by the N-1 image)."""
    factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    factory.login(api, admin_a)
    stale = api.post(f"/api/v1/users/{a2.id}/mfa/reset", {"reason": "lost phone"}, if_match=_version(api, a2.id)).data[
        "approval_id"
    ]
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.get(User, a2.id).protection_level = "FOUNDER"  # simulate promotion without the cancellation step
    factory.login(api, admin_b)
    r = api.post(f"/api/v1/approvals/{stale}/approve", {"reason": "ok"})
    assert r.status == 200 and r.data["status"] == "FAILED" and r.data["status_reason"] == "FOUNDER_PROTECTED", r
    assert rows(sa.select(User).where(User.id == a2.id))[0].status == "ACTIVE"


def test_IR04_requester_G9_rechecked_at_execution(api, factory):
    factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    factory.login(api, admin_a)
    approval = api.post(
        f"/api/v1/users/{a2.id}/mfa/reset", {"reason": "lost phone"}, if_match=_version(api, a2.id)
    ).data["approval_id"]
    factory.grant(admin_a, "lead.delete", effect="DENY")  # a2 now holds a permission the requester does not
    factory.login(api, admin_b)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"})
    assert r.data["status"] == "FAILED" and r.data["status_reason"] == "ESCALATION_DENIED", r


def test_IR04_concurrent_promotion_and_standard_approval(app, api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    admin_a, admin_b, a2 = factory.user("ADMIN"), factory.user("ADMIN"), factory.user("ADMIN")
    factory.login(api, admin_a)
    standard = api.post(
        f"/api/v1/users/{a2.id}/email-change",
        {"new_email": "x@vedaspaces.test", "reason": "rename"},
        if_match=_version(api, a2.id),
    ).data["approval_id"]
    factory.login(api, f1)
    founder_req = request(api, "GRANT_FOUNDER", a2.id).data["approval_id"]
    t_f2, t_b = factory.login(api, f2, set_default=False), factory.login(api, admin_b, set_default=False)
    barrier = threading.Barrier(2)
    out = {}

    def approve(name, approval, token):
        c = ApiClient(app.test_client())
        barrier.wait()
        out[name] = c.post(f"/api/v1/approvals/{approval}/approve", {"reason": "go"}, token=token)

    threads = [
        threading.Thread(target=approve, args=("founder", founder_req, t_f2)),
        threading.Thread(target=approve, args=("standard", standard, t_b)),
    ]
    [t.start() for t in threads]
    [t.join() for t in threads]
    founder_row, standard_row = get(AdminApprovalRequest, founder_req), get(AdminApprovalRequest, standard)
    assert founder_row.status == "EXECUTED"
    # executed_on is each transaction's start time; the order in which the two committed is the order of their
    # chained security events (appended under the governance lock).
    promoted = next(e.chain_seq for e in events("FOUNDER_TRANSITION"))
    if standard_row.status == "EXECUTED":  # it won the lock and ran while a2 was still an ADMIN
        changed = next(e.chain_seq for e in events("EMAIL_CHANGE_REQUESTED"))
        assert changed < promoted, "the STANDARD action must never run after the promotion"
    else:
        assert standard_row.status in ("CANCELLED", "FAILED"), standard_row.status
        assert factory.get_user(a2.id).proposed_email is None
    assert_invariants()


# --- IR-08: FOUNDER_STATUS_CHANGE DELETE ----------------------------------------------------------------


def test_IR08_P16_founder_delete_executes_and_invariants_hold(api, factory):
    f1, f2, f3 = factory.user(founder=True), factory.user(founder=True), factory.user(founder=True)
    factory.login(api, f1)
    approval = request(api, "FOUNDER_STATUS_CHANGE", f3.id, status="DELETE").data["approval_id"]
    factory.login(api, f2)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "left the company"})
    assert r.data["status"] == "EXECUTED", r
    deleted = factory.get_user(f3.id)
    assert deleted.is_deleted and deleted.status == "DISABLED"
    with db.unit_of_work(write=False) as s:
        state = guards.evaluate(s)
    assert state.i1 and state.i3, state.problems
    nightly = maintenance.check_invariants()
    assert nightly["i1"] and nightly["i2"] and nightly["i3"], nightly["problems"]
    assert not events("GOVERNANCE_INVARIANT_FAILED")
    assert {u.id for u in _active_founders()} == {f1.id, f2.id}


def _active_founders():
    with db.unit_of_work(write=False) as s:
        found = guards.active_founders(s)
        s.expunge_all()
        return found


def test_IR08_last_founder_still_cannot_be_deleted(api, factory):
    f1 = factory.user(founder=True)
    factory.login(api, f1)
    r = request(api, "FOUNDER_STATUS_CHANGE", f1.id, status="DELETE")
    assert r.code in ("LAST_FOUNDER", "SELF_MODIFICATION_DENIED"), r


# --- IR-05: custodian break-glass only in its operating mode ----------------------------------------------


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1", K2: "external:Auditor-2"})
def test_IR05_P13_custodian_request_refused_while_founders_are_eligible(api, factory):
    factory.user(founder=True), factory.user(founder=True)
    victim = factory.user("SALES")
    with security_events.deferred_scope(), pytest.raises(ApiError) as exc:  # as the CLI runs it
        with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
            governance.break_glass_request(
                s,
                action="GRANT_FOUNDER",
                target=s.get(User, victim.id),
                reason="steady state",
                principal_arn=K1,
                payload={},
            )
    assert exc.value.code == "INVALID_STATE" and exc.value.extra["reason"] == "FOUNDER_AVAILABLE"
    assert not rows(sa.select(AdminApprovalRequest))
    failures = [e for e in events("BREAK_GLASS_REQUESTED") if e.outcome == "FAILURE"]
    assert failures and failures[0].detail["reason"] == "FOUNDER_AVAILABLE"


@pytest.mark.settings(break_glass_custodians={K1: "external:Auditor-1", K2: "external:Auditor-2"})
def test_IR05_custodian_path_available_when_no_founder_is_eligible_and_rechecked_at_execution(api, factory):
    founder = factory.user(founder=True, mfa=False)  # a Founder without a factor is not eligible (05 §11)
    target = factory.user("ADMIN")
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        req = governance.break_glass_request(
            s,
            action="GRANT_FOUNDER",
            target=s.get(User, target.id),
            reason="sole Founder lost access",
            principal_arn=K1,
            payload={},
        )
        rid = req.id
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        governance.break_glass_approve(s, s.get(AdminApprovalRequest, rid), principal_arn=K2)
    # Before execution an eligible Founder appears: the custodian action no longer applies.
    factory.user(founder=True)
    clock.advance(timedelta(hours=24, minutes=1))
    assert maintenance.execute_due_break_glass() == 1
    req = get(AdminApprovalRequest, rid)
    assert req.status == "FAILED" and req.status_reason == "INVALID_STATE"
    assert factory.get_user(target.id).protection_level == "STANDARD"
    del founder


# --- IR-06: the custodian identity comes from STS, not from the argument ---------------------------------


def _cli(args):
    from veda.cli.main import main

    return main(["break-glass", *args])


@pytest.mark.settings(
    break_glass_custodians={K1: "external:Auditor-1", K3: "external:Auditor-3"}, break_glass_identity="sts"
)
def test_IR06_P13_single_operator_cannot_assert_a_second_custodian(api, factory, monkeypatch, capsys):
    factory.user(founder=True, mfa=False)
    target = factory.user("ADMIN")
    monkeypatch.setattr(custodians, "caller_arn", lambda: K1)
    assert _cli(["request", "--target", target.id, "--founder-action", "GRANT_FOUNDER", "--reason", "lost access"]) == 0
    rid = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["approval_id"]
    # The same operator (still K1 per STS) claims to be K3.
    assert _cli(["approve", "--request", rid, "--principal-arn", K3]) == 3
    assert "APPROVER_NOT_ELIGIBLE" in capsys.readouterr().err
    assert get(AdminApprovalRequest, rid).status == "PENDING"
    assert any(
        e.outcome == "FAILURE" and (e.detail or {}).get("reason") == "PRINCIPAL_MISMATCH"
        for e in events("BREAK_GLASS_APPROVED")
    )
    # Without the argument the derived identity is K1 = the requester: refused as the same human.
    assert _cli(["approve", "--request", rid]) == 3
    assert get(AdminApprovalRequest, rid).status == "PENDING"
    # A second, genuinely different session (assumed role registered under its role ARN) may approve.
    monkeypatch.setattr(custodians, "caller_arn", lambda: SESSION_K3)
    assert _cli(["approve", "--request", rid]) == 0
    req = get(AdminApprovalRequest, rid)
    assert req.status == "APPROVED" and req.external_approver_ref == SESSION_K3
    assert req.external_approver_human == "external:Auditor-3"


def test_IR06_asserted_identity_refused_outside_local_and_test():
    from veda import config

    previous = config._current
    config.use_settings(
        config.Settings(
            env="staging", break_glass_identity="asserted", break_glass_custodians={K1: "external:Auditor-1"}
        )
    )
    try:
        with pytest.raises(ApiError):
            custodians.resolve(K1)
    finally:
        config._current = previous


# --- IR-A07: deny and cancel are sensitive actions too ----------------------------------------------------


def test_IRA07_deny_and_cancel_record_sensitive_actions(api, factory):
    f1, f2 = factory.user(founder=True), factory.user(founder=True)
    s1, s2 = factory.user("SALES"), factory.user("SALES")
    factory.login(api, f1)
    denied = request(api, "GRANT_FOUNDER", s1.id).data["approval_id"]
    cancelled = request(api, "GRANT_FOUNDER", s2.id).data["approval_id"]
    assert api.post(f"/api/v1/approvals/{cancelled}/cancel", {}).status == 200
    factory.login(api, f2)
    assert api.post(f"/api/v1/approvals/{denied}/deny", {"reason": "not now"}).status == 200
    actions = {(e.detail or {}).get("action") for e in events("SENSITIVE_ACTION")}
    assert {"deny:GRANT_FOUNDER", "cancel:GRANT_FOUNDER"} <= actions
