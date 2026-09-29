"""Authorization and account control (12 §4.4)."""

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support.dbh import audits, events, rows
from veda.kernel import clock
from veda.platform.identity.models import User
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider
from veda.platform.rbac.models import UserPermission

MASS_FIELDS = [
    "email",
    "proposed_email",
    "password",
    "status",
    "roles",
    "permissions",
    "mfa_required",
    "protection_level",
    "is_founder",
]


# --- matrix (RBAC-008) ---------------------------------------------------------------------

ENDPOINTS = [
    ("GET", "/api/v1/users", "user.read"),
    ("GET", "/api/v1/roles", "role.read"),
    ("GET", "/api/v1/permissions", "permission.read"),
    ("GET", "/api/v1/audit-logs", "audit.read"),
    ("GET", "/api/v1/security-events", "security_event.read"),
    ("GET", "/api/v1/leads", "lead.read"),
    ("GET", "/api/v1/lookups", "lookup.read"),
    ("GET", "/api/v1/notifications", "notification.read"),
    ("GET", "/api/v1/users/assignable", "lead.assign"),
    ("GET", "/api/v1/auth/sessions", "session.read"),
]
ALLOWED = {
    "FOUNDER": {c for _, _, c in ENDPOINTS},
    "ADMIN": {c for _, _, c in ENDPOINTS},
    "SALES": {"lead.read", "lookup.read", "notification.read", "session.read"},
}


@pytest.mark.parametrize("role", ["FOUNDER", "ADMIN", "SALES"])
def test_RBAC_008_role_matrix_over_endpoints(api, factory, role):
    user = factory.user(role)
    factory.login(api, user)
    for method, path, code in ENDPOINTS:
        r = api.call(method, path)
        if code in ALLOWED[role]:
            assert r.status == 200, (role, path, r)
        else:
            assert r.status == 403 and r.code == "PERMISSION_DENIED", (role, path, r)


def test_SEVT_005_sales_has_no_security_event_access_even_for_self(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    me = api.get("/api/v1/auth/me").data
    assert "security_event.read" not in me["permissions"]
    assert api.get(f"/api/v1/security-events?subject_user_id={sales.id}").code == "PERMISSION_DENIED"
    own = events(subject_user_id=sales.id)[0]
    assert api.get(f"/api/v1/security-events/{own.id}").code == "PERMISSION_DENIED"


def test_admin_without_mfa_verified_session_has_security_read_suspended(api, factory):
    admin = factory.user("ADMIN")
    token = factory.login(api, admin)
    assert api.get("/api/v1/security-events", token=token).status == 200
    # Removing the factor (policy requires it, so do it directly) suspends sensitive permissions next request.
    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.platform.auth.models import UserMfaFactor

    with actor(system_context()), db.unit_of_work(write=True) as s:
        f = s.execute(sa.select(UserMfaFactor).where(UserMfaFactor.user_id == admin.id)).scalar_one()
        f.status, f.revoked_on, f.revoke_reason = "REVOKED", db.tx_time(s), "ADMIN_RESET"
        s.get(User, admin.id).authz_version += 1
    r = api.get("/api/v1/security-events", token=token)
    assert r.status == 403 and r.json["reason"] == "MFA_REQUIRED"


# --- mass assignment (F-03) --------------------------------------------------------------------


@pytest.mark.parametrize("field", MASS_FIELDS)
def test_RBAC_019_mass_assignment_rejected(api, factory, field):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin)
    version = api.get(f"/api/v1/users/{sales.id}").data["version"]
    r = api.patch(f"/api/v1/users/{sales.id}", {field: "x"}, if_match=version)
    assert r.status == 422 and r.code == "FIELD_NOT_UPDATABLE", r
    me_version = api.get("/api/v1/auth/me").data["version"]
    r = api.patch("/api/v1/auth/me", {field: "x"}, if_match=me_version)
    assert r.status == 422 and r.code == "FIELD_NOT_UPDATABLE", r


def test_unknown_field_rejected_and_profile_update_allowed(api, factory):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin)
    version = api.get(f"/api/v1/users/{sales.id}").data["version"]
    assert api.patch(f"/api/v1/users/{sales.id}", {"nickname": "x"}, if_match=version).code == "VALIDATION_FAILED"
    r = api.patch(
        f"/api/v1/users/{sales.id}",
        {"display_name": "Priya S", "timezone": "Asia/Kolkata", "phone": "98765 43210"},
        if_match=version,
    )
    assert r.status == 200 and r.data["display_name"] == "Priya S" and r.data["phone"] == "+919876543210"
    assert (
        api.patch(
            f"/api/v1/users/{admin.id}",
            {"display_name": "Me"},
            if_match=api.get(f"/api/v1/users/{admin.id}").data["version"],
        ).code
        == "SELF_MODIFICATION_DENIED"
    )


# --- guards --------------------------------------------------------------------------------------


def test_G3_no_self_deactivation(api, factory):
    admin = factory.user("ADMIN")
    factory.user(founder=True)
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{admin.id}").data["version"]
    assert (
        api.post(f"/api/v1/users/{admin.id}/status", {"status": "DISABLED", "reason": "x"}, if_match=v).code
        == "SELF_MODIFICATION_DENIED"
    )


def test_G11_admin_cannot_act_on_founder(api, factory):
    founder = factory.user(founder=True)
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{founder.id}").data["version"]
    for path, body in (
        (f"/api/v1/users/{founder.id}/status", {"status": "DISABLED", "reason": "x"}),
        (f"/api/v1/users/{founder.id}/mfa/reset", {"reason": "x"}),
        (f"/api/v1/users/{founder.id}/email-change", {"new_email": "f2@vedaspaces.test", "reason": "x"}),
        (f"/api/v1/users/{founder.id}/sessions/revoke", {"reason": "x"}),
    ):
        r = api.post(path, body, if_match=v)
        assert r.status == 403 and r.code in ("FOUNDER_PROTECTED", "ESCALATION_DENIED"), (path, r)
    r = api.delete(f"/api/v1/users/{founder.id}", {"reason": "x"}, if_match=v)
    assert r.status == 403
    r = api.put(f"/api/v1/users/{founder.id}/roles", {"roles": [], "reason": "demote"})
    assert r.status == 403 and r.code in ("FOUNDER_GOVERNANCE_REQUIRED", "ESCALATION_DENIED")


def test_G9_cannot_act_on_stronger_account(api, factory):
    admin = factory.user("ADMIN")
    other_admin = factory.user("ADMIN")
    factory.grant(other_admin, "user.delete")
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{other_admin.id}").data["version"]
    r = api.post(f"/api/v1/users/{other_admin.id}/status", {"status": "DISABLED", "reason": "x"}, if_match=v)
    assert r.code == "ESCALATION_DENIED"


def test_G1_G2_no_escalation(api, factory):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin)
    # Admin lacks user.permission.manage entirely.
    r = api.post(f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "reason": "cover"})
    assert r.code == "PERMISSION_DENIED"
    founder = factory.user(founder=True)
    factory.login(api, founder)
    r = api.post("/api/v1/roles", {"code": "INTAKE", "name": "Intake"})
    role_id = r.data["id"]
    api.put(
        f"/api/v1/roles/{role_id}/permissions",
        {"permissions": [{"permission_code": "lead.erase", "scope": "ALL"}], "reason": "test"},
    )
    factory.login(api, admin)
    r = api.put(
        f"/api/v1/users/{sales.id}/roles",
        {"roles": [{"role_id": factory.role_id("SALES")}, {"role_id": role_id}], "reason": "promote"},
    )
    assert r.status == 403 and r.code == "ESCALATION_DENIED", "G2: role contains lead.erase"
    r = api.post("/api/v1/roles", {"code": "COPY_OF_INTAKE", "name": "Copy", "copy_from_role_id": role_id})
    assert r.code == "ESCALATION_DENIED", "A-06 copy-from-role escalation"


def test_G8_team_scope_and_time_bound_grants_rejected(api, factory):
    founder = factory.user(founder=True)
    sales = factory.user("SALES")
    factory.login(api, founder)
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "scope": "TEAM", "reason": "x"}
    )
    assert r.code == "SCOPE_NOT_SUPPORTED"
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions",
        {"permission_code": "lead.read", "scope": "ALL", "reason": "x", "valid_until": "2026-12-31T00:00:00+05:30"},
    )
    assert r.code == "TIME_BOUND_GRANTS_NOT_ENABLED"
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "scope": "ALL", "reason": " "}
    )
    assert r.code == "REASON_REQUIRED"


def test_TD_A_deny_over_grant_and_next_request_propagation(api, factory):
    founder = factory.user(founder=True)
    sales = factory.user("SALES")
    other = factory.user("SALES")
    factory.login(api, founder)
    l2 = factory.lead(api, founder.token, assigned_to=other.id)
    sales_token = factory.login(api, sales, set_default=False)
    l1 = factory.lead(api, sales_token)
    api.token = founder.token
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "scope": "ALL", "reason": "cover"}
    )
    assert r.status == 201, r
    grant_id = r.data["id"]
    ids = {x["id"] for x in api.get("/api/v1/leads", token=sales_token).data}
    assert {l1["id"], l2["id"]} <= ids, "broadest scope wins"
    before = api.get("/api/v1/auth/me", token=sales_token).headers["X-Authz-Version"]
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "effect": "DENY", "reason": "policy"}
    )
    assert r.status == 409 and r.code == "DUPLICATE", "one direct row per permission"
    assert api.delete(f"/api/v1/users/{sales.id}/permissions/{grant_id}").status == 204
    r = api.post(
        f"/api/v1/users/{sales.id}/permissions", {"permission_code": "lead.read", "effect": "DENY", "reason": "policy"}
    )
    assert r.status == 201
    deny_id = r.data["id"]
    r1 = api.get("/api/v1/leads", token=sales_token)
    r2 = api.get(f"/api/v1/leads/{l1['id']}", token=sales_token)
    assert r1.code == "PERMISSION_DENIED" and r2.code == "PERMISSION_DENIED"
    assert r1.headers["X-Authz-Version"] != before
    eff = api.get(f"/api/v1/users/{sales.id}/effective-permissions").data["permissions"]
    assert next(p for p in eff if p["code"] == "lead.read")["status"] == "DENIED"
    assert api.delete(f"/api/v1/users/{sales.id}/permissions/{deny_id}").status == 204
    assert api.get(f"/api/v1/leads/{l1['id']}", token=sales_token).status == 200
    assert events("SENSITIVE_ACTION", permission_code="user.permission.manage")
    assert audits(entity_type="user_permission")


def test_RBAC_020_last_recovery_administrator(api, factory):
    founder = factory.user(founder=True)
    factory.login(api, founder)
    # The Founder is the only I2 holder; a DENY of user.role.manage would break I2.
    other = factory.user(founder=True)
    r = api.post(
        f"/api/v1/users/{other.id}/permissions",
        {"permission_code": "user.role.manage", "effect": "DENY", "reason": "x"},
    )
    assert r.status == 403 and r.code == "FOUNDER_PROTECTED"
    admin = factory.user("ADMIN")
    admin2 = factory.user("ADMIN")
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{admin2.id}").data["version"]
    assert (
        api.post(f"/api/v1/users/{admin2.id}/status", {"status": "DISABLED", "reason": "leaving"}, if_match=v).status
        == 200
    )


def test_disable_revokes_sessions_and_enable_restores(api, factory):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    sales_token = factory.login(api, sales, set_default=False)
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{sales.id}").data["version"]
    r = api.post(f"/api/v1/users/{sales.id}/status", {"status": "DISABLED", "reason": "left"}, if_match=v)
    assert r.status == 200 and r.data["status"] == "DISABLED"
    assert api.get("/api/v1/auth/me", token=sales_token).code == "SESSION_INVALID"
    r = api.post(f"/api/v1/users/{sales.id}/status", {"status": "ACTIVE", "reason": "back"}, if_match=r.data["version"])
    assert r.status == 200 and r.data["status"] == "ACTIVE"
    assert events("SESSION_REVOKED", subject_user_id=sales.id)


def test_USER_001_delete_and_restore(api, factory):
    founder = factory.user(founder=True)
    sales = factory.user("SALES")
    factory.login(api, founder)
    v = api.get(f"/api/v1/users/{sales.id}").data["version"]
    assert api.delete(f"/api/v1/users/{sales.id}", {"reason": "left"}, if_match=v).status == 204
    assert api.get(f"/api/v1/users/{sales.id}").status == 404
    assert api.get(f"/api/v1/users/{sales.id}?include_deleted=true").data["is_deleted"] is True
    r = api.post(f"/api/v1/users/{sales.id}/restore", {})
    assert r.status == 200 and r.data["status"] == "DISABLED" and r.data["is_deleted"] is False
    actions = [a.action for a in audits(sales.id, entity_type="app_user")]
    assert "DELETE" in actions and "RESTORE" in actions
    assert api.delete("/api/v1/users/00000000000070008000000000000001", {"reason": "x"}, if_match=1).status == 404


def test_G12_dual_control_mfa_reset_of_privileged_user(api, factory):
    admin_a = factory.user("ADMIN")
    admin_b = factory.user("ADMIN")
    target = factory.user("ADMIN")
    factory.login(api, admin_a)
    v = api.get(f"/api/v1/users/{target.id}").data["version"]
    r = api.post(f"/api/v1/users/{target.id}/mfa/reset", {"reason": "Lost phone; verified by video call"}, if_match=v)
    assert r.status == 202 and r.data["status"] == "APPROVAL_REQUIRED"
    approval = r.data["approval_id"]
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"}).code == "APPROVER_NOT_ELIGIBLE"
    target_token = factory.login(api, target, set_default=False)
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "ok"}, token=target_token).status in (403, 404)
    factory.login(api, admin_b)
    listing = api.get("/api/v1/approvals?status=PENDING").data
    assert any(a["id"] == approval and a["can_decide"] for a in listing)
    r = api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "Verified with the user"})
    assert r.status == 200 and r.data["status"] == "EXECUTED", r
    assert api.get("/api/v1/auth/me", token=target_token).code == "SESSION_INVALID"
    assert api.post(f"/api/v1/approvals/{approval}/approve", {"reason": "again"}).code == "INVALID_STATE"
    worker.drain_all()
    assert any(target.email in m.to and "two-step" in m.text for m in CaptureEmailProvider.sent)
    assert not any(admin_a.email in m.to and "#token=" in m.text for m in CaptureEmailProvider.sent), (
        "the admin never receives an enrollment token"
    )
    kinds = {e.event_type for e in events(subject_user_id=target.id)}
    assert {
        "APPROVAL_REQUESTED",
        "ADMIN_MFA_RESET_REQUESTED",
        "ADMIN_MFA_RESET_APPROVED",
        "ADMIN_MFA_RESET_COMPLETED",
    } <= kinds


def test_G12_non_privileged_mfa_reset_executes_directly(api, factory):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES", mfa=True)
    factory.login(api, admin)
    v = api.get(f"/api/v1/users/{sales.id}").data["version"]
    assert api.post(f"/api/v1/users/{sales.id}/mfa/reset", {"reason": "Lost phone"}, if_match=v).status == 204
    assert (
        api.post(
            f"/api/v1/users/{admin.id}/mfa/reset",
            {"reason": "self"},
            if_match=api.get(f"/api/v1/users/{admin.id}").data["version"],
        ).code
        == "SELF_MODIFICATION_DENIED"
    )


def test_approval_expiry(api, factory):
    from veda.platform import maintenance

    admin_a = factory.user("ADMIN")
    target = factory.user("ADMIN")
    factory.login(api, admin_a)
    v = api.get(f"/api/v1/users/{target.id}").data["version"]
    approval = api.post(f"/api/v1/users/{target.id}/mfa/reset", {"reason": "x"}, if_match=v).data["approval_id"]
    clock.advance(timedelta(hours=25))
    assert maintenance.expire_approvals() == 1
    factory.login(api, factory.user("ADMIN"))
    assert api.get(f"/api/v1/approvals/{approval}").data["status"] == "EXPIRED"


def test_USER_007_admin_email_change_privileged_needs_approval(api, factory):
    admin_a, admin_b = factory.user("ADMIN"), factory.user("ADMIN")
    target_admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    factory.login(api, admin_a)
    v = api.get(f"/api/v1/users/{sales.id}").data["version"]
    r = api.post(
        f"/api/v1/users/{sales.id}/email-change",
        {"new_email": "sales.new@vedaspaces.test", "reason": "rename"},
        if_match=v,
    )
    assert r.status == 202 and r.data["status"] == "VERIFICATION_SENT"
    v = api.get(f"/api/v1/users/{target_admin.id}").data["version"]
    r = api.post(
        f"/api/v1/users/{target_admin.id}/email-change",
        {"new_email": "adm.new@vedaspaces.test", "reason": "rename"},
        if_match=v,
    )
    assert r.status == 202 and r.data["status"] == "APPROVAL_REQUIRED"
    factory.login(api, admin_b)
    r = api.post(f"/api/v1/approvals/{r.data['approval_id']}/approve", {"reason": "confirmed"})
    assert r.data["status"] == "EXECUTED" and r.data["request_payload"]["new_email"].startswith("a***@")
    assert factory.get_user(target_admin.id).proposed_email == "adm.new@vedaspaces.test"
    assert factory.get_user(target_admin.id).email == target_admin.email, "the verified email never changes directly"


def test_USER_007_self_email_change_workflow(api, factory):
    sales = factory.user("SALES")
    token = factory.login(api, sales)
    r = api.put("/api/v1/auth/me/email", {"new_email": "fresh@vedaspaces.test"})
    assert r.code == "STEP_UP_REQUIRED" and r.json["kind"] == "password"
    api.post("/api/v1/auth/reauth", {"password": sales.password})
    assert api.put("/api/v1/auth/me/email", {"new_email": sales.email}).code == "SAME_AS_CURRENT"
    r = api.put("/api/v1/auth/me/email", {"new_email": "fresh@vedaspaces.test"})
    assert (
        r.status == 202
        and r.data["status"] == "VERIFICATION_SENT"
        and r.data["proposed_email"] == "f***@vedaspaces.test"
    )
    assert api.get("/api/v1/auth/me").data["email_change"]["proposed_email"] == "f***@vedaspaces.test"
    # Login and reset still use the current address.
    r = api.post("/api/v1/auth/login", {"email": "fresh@vedaspaces.test", "password": sales.password}, anonymous=True)
    assert r.status == 401
    worker.drain_all()
    to_new = [m for m in CaptureEmailProvider.sent if "fresh@vedaspaces.test" in m.to]
    to_old = [m for m in CaptureEmailProvider.sent if sales.email in m.to]
    assert len(to_new) == 1 and "confirm" in to_new[0].subject.lower()
    assert any("cancel" in m.text.lower() for m in to_old)
    verify_token = to_new[0].text.split("#token=")[1].split()[0]
    assert api.post("/api/v1/auth/email/verify", {"token": verify_token}, anonymous=True).status == 204
    assert api.get("/api/v1/auth/me", token=token).code == "SESSION_INVALID"
    assert api.post("/api/v1/auth/email/verify", {"token": verify_token}, anonymous=True).code == "EMAIL_TOKEN_INVALID"
    sales.email = "fresh@vedaspaces.test"
    factory.login(api, sales)
    worker.drain_all()
    completed = [m for m in CaptureEmailProvider.sent if "changed" in m.subject.lower()]
    assert {tuple(m.to) for m in completed} >= {("fresh@vedaspaces.test",)}
    kinds = {e.event_type for e in events(subject_user_id=sales.id)}
    assert {"EMAIL_CHANGE_REQUESTED", "EMAIL_CHANGE_VERIFIED", "EMAIL_CHANGE_COMPLETED"} <= kinds


def test_USER_007_cancel_link(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    api.post("/api/v1/auth/reauth", {"password": sales.password})
    api.put("/api/v1/auth/me/email", {"new_email": "maybe@vedaspaces.test"})
    worker.drain_all()
    alert = next(m for m in CaptureEmailProvider.sent if sales.email in m.to and "cancel" in m.text.lower())
    token = alert.text.split("#token=")[1].split()[0]
    assert api.post("/api/v1/auth/email/cancel", {"token": token}, anonymous=True).status == 204
    assert factory.get_user(sales.id).proposed_email is None
    assert events("EMAIL_CHANGE_CANCELLED", subject_user_id=sales.id)


def test_roles_crud_and_permission_catalog(api, factory):
    founder = factory.user(founder=True)
    factory.login(api, founder)
    r = api.post(
        "/api/v1/roles",
        {"code": "SALES_MANAGER", "name": "Sales Manager", "copy_from_role_id": factory.role_id("SALES")},
    )
    assert r.status == 201 and r.data["permission_count"] > 0
    role = r.data
    assert api.post("/api/v1/roles", {"code": "OTHER", "name": "sales manager"}).code == "DUPLICATE", (
        "case-insensitive name (A-04)"
    )
    r = api.patch(f"/api/v1/roles/{role['id']}", {"code": "RENAMED"}, if_match=role["version"])
    assert r.code == "IMMUTABLE_FIELD"
    r = api.put(
        f"/api/v1/roles/{role['id']}/permissions",
        {
            "permissions": [
                {"permission_code": "lead.read", "scope": "ALL"},
                {"permission_code": "lead.assign", "scope": "ALL"},
            ],
            "reason": "Create sales manager role",
        },
    )
    assert r.status == 200 and r.json["meta"]["diff"]["added"] >= 1
    sales = factory.user("SALES")
    assert (
        api.put(f"/api/v1/users/{sales.id}/roles", {"roles": [{"role_id": role["id"]}], "reason": "promote"}).status
        == 200
    )
    assert (
        api.delete(f"/api/v1/roles/{role['id']}", if_match=api.get(f"/api/v1/roles/{role['id']}").data["version"]).code
        == "ROLE_IN_USE"
    )
    assert (
        api.delete(
            f"/api/v1/roles/{factory.role_id('SALES')}",
            if_match=api.get(f"/api/v1/roles/{factory.role_id('SALES')}").data["version"],
        ).code
        == "SYSTEM_OBJECT"
    )
    perms = api.get("/api/v1/permissions?module=crm&q=status").data
    assert perms and perms[0]["code"] == "lead.status.change" and perms[0]["granted_to_roles"]
    p = api.get("/api/v1/permissions?q=lead.read").data[0]
    r = api.patch(f"/api/v1/permissions/{p['id']}", {"sensitivity_class": "BULK_DATA"}, if_match=p["version"])
    assert r.code == "IMMUTABLE_FIELD"
    r = api.patch(f"/api/v1/permissions/{p['id']}", {"description": "See leads"}, if_match=p["version"])
    assert r.status == 200 and r.data["description"] == "See leads"
    holders = api.get(f"/api/v1/permissions/{p['id']}/holders").data
    assert any(h["user"]["id"] == sales.id for h in holders)


def test_RBAC_013_role_change_applies_on_next_request(api, factory):
    admin = factory.user("ADMIN")
    sales = factory.user("SALES")
    sales_token = factory.login(api, sales, set_default=False)
    factory.login(api, admin)
    assert api.get("/api/v1/users", token=sales_token).code == "PERMISSION_DENIED"
    r = api.put(
        f"/api/v1/users/{sales.id}/roles",
        {"roles": [{"role_id": factory.role_id("SALES")}, {"role_id": factory.role_id("ADMIN")}], "reason": "promote"},
    )
    assert r.status == 200 and any(i["pending_mfa"] for i in r.data)
    me = api.get("/api/v1/auth/me", token=sales_token).data
    assert me["permissions"]["user.read"] == "ALL" and any(
        s["code"] == "user.role.manage" for s in me["suspended_permissions"]
    )
    assert events("PERMISSION_SUSPENDED", subject_user_id=sales.id)


def test_users_list_filters(api, factory):
    admin = factory.user("ADMIN", full_name="Anand Nair")
    factory.user("SALES", full_name="Priya Sharma")
    factory.login(api, admin)
    r = api.get("/api/v1/users?q=priya")
    assert [u["full_name"] for u in r.data] == ["Priya Sharma"] and r.json["meta"]["total"] == 1
    assert api.get("/api/v1/users?sort=bogus").code == "INVALID_QUERY_PARAM"
    assert api.get("/api/v1/users?unknown=1").code == "INVALID_QUERY_PARAM"
    rows_ = rows(sa.select(UserPermission))
    assert rows_ == []
