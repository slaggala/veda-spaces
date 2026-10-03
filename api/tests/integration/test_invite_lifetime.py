"""FC-09: an invitation that would grant a sensitive permission lives 24 h (05 §8.4, AUTH-011), including when the
privilege is added after the link was sent."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

from tests.integration.test_auth import link_token
from tests.support.dbh import events
from veda.kernel import clock
from veda.platform.rbac.registry import SENSITIVE_CODES

PASSWORD = "Monsoon-Garden-Window-88"


def _invite(api, factory, email: str, role: str) -> str:
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    r = api.post("/api/v1/users", {"email": email, "full_name": "Invitee", "role_ids": [factory.role_id(role)]})
    assert r.status == 201 and r.data["status"] == "INVITED"
    return r.data["id"]


def _accept(api, token: str):
    return api.post("/api/v1/auth/invite/accept", {"token": token, "new_password": PASSWORD}, anonymous=True)


def test_FC09_privilege_added_after_sending_shortens_the_invitation_to_24h(api, factory):
    user_id = _invite(api, factory, "late-admin@vedaspaces.test", "SALES")
    token = link_token("invited to Veda Workspace", "late-admin@vedaspaces.test")
    # Any escalation path counts: here a direct sensitive permission, as a role change or a role grant would add.
    factory.grant(SimpleNamespace(id=user_id), sorted(SENSITIVE_CODES)[0])
    clock.advance(timedelta(hours=30))
    r = _accept(api, token)
    assert r.status == 400 and r.code == "INVITE_TOKEN_INVALID"
    failed = events("INVITE_ACCEPTED", outcome="FAILURE", subject_user_id=user_id)
    assert failed and failed[-1].failure_reason == "TOKEN_EXPIRED"
    assert failed[-1].detail["reason"] == "PRIVILEGED_INVITE_LIFETIME"


def test_FC09_escalated_invitation_is_still_honoured_inside_24h(api, factory):
    user_id = _invite(api, factory, "early-admin@vedaspaces.test", "SALES")
    token = link_token("invited to Veda Workspace", "early-admin@vedaspaces.test")
    factory.grant(SimpleNamespace(id=user_id), sorted(SENSITIVE_CODES)[0])
    clock.advance(timedelta(hours=23))
    r = _accept(api, token)
    # Privileged invitees enrol MFA inside the invitation flow (05 §11.3 path B).
    assert r.status == 200 and r.data["status"] == "MFA_ENROLLMENT_REQUIRED"


def test_FC09_unprivileged_invitation_keeps_72h(api, factory):
    _invite(api, factory, "sales-late@vedaspaces.test", "SALES")
    token = link_token("invited to Veda Workspace", "sales-late@vedaspaces.test")
    clock.advance(timedelta(hours=30))
    assert _accept(api, token).status == 204


def test_FC09_invitation_privileged_at_issue_expires_after_24h(api, factory):
    _invite(api, factory, "admin-invite@vedaspaces.test", "ADMIN")
    token = link_token("invited to Veda Workspace", "admin-invite@vedaspaces.test")
    clock.advance(timedelta(hours=25))
    assert _accept(api, token).code == "INVITE_TOKEN_INVALID"
