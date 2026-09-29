"""Sensitivity registry rules (06 §3.1, RBAC-018) and the resolution table (TD-A, RBAC-006)."""

import itertools

import pytest

from veda.platform.rbac import registry
from veda.platform.rbac.resolver import PermissionMeta, Resolution, apply_gate, broader


def test_RBAC_018_registry_rules_hold():
    assert registry.validate_registry() == []


def test_RBAC_018_sales_holds_no_sensitive_permission():
    for code, grants in registry.MATRIX.items():
        if "SALES" in grants:
            assert code not in registry.SENSITIVE_CODES, code


def test_founder_workflow_only_permission_only_in_founder_role():
    assert registry.FOUNDER_WORKFLOW_ONLY_CODES == {"user.founder.manage"}
    assert set(registry.MATRIX["user.founder.manage"]) == {"FOUNDER"}


def test_security_event_read_is_all_only():
    assert registry.BY_CODE["security_event.read"].definition.supports_scope is False


def test_step_up_classes():
    assert registry.requires_step_up("user.role.manage")
    assert registry.requires_step_up("lead.erase")
    assert not registry.requires_step_up("lead.delete")
    assert not registry.requires_step_up("audit.read")


class _User:
    def __init__(self, cooling=None):
        self.status, self.is_deleted, self.user_type = "ACTIVE", False, "HUMAN"
        self.security_cooling_off_until = cooling


def _resolve(role_scope, direct_scope, deny):
    """The 06 §5 steps 3–7 with synthetic rows, then the MFA gate."""
    meta = PermissionMeta("lead.read", True, None, "STANDARD")
    grants = {}
    if role_scope:
        grants["lead.read"] = broader(grants.get("lead.read"), role_scope)
    if direct_scope:
        grants["lead.read"] = broader(grants.get("lead.read"), direct_scope)
    base = Resolution(user_id="u", authz_version=1, meta={"lead.read": meta})
    if not deny and grants:
        base.granted = dict(grants)
    return apply_gate(base, user=_User(), session_type="FULL", mfa_verified=False, now=None)


@pytest.mark.parametrize(
    "role_scope, direct_scope, deny", list(itertools.product([None, "OWN", "ALL"], [None, "OWN", "ALL"], [False, True]))
)
def test_RBAC_006_deny_over_grant_resolution_table(role_scope, direct_scope, deny):
    res = _resolve(role_scope, direct_scope, deny)
    if deny or not (role_scope or direct_scope):
        assert "lead.read" not in res.effective
    else:
        expected = "ALL" if "ALL" in (role_scope, direct_scope) else "OWN"
        assert res.effective["lead.read"] == expected


def test_MFA_012_sensitive_permission_suspended_without_mfa_or_in_cooling_off():
    from datetime import UTC, datetime, timedelta

    now = datetime(2026, 9, 29, tzinfo=UTC)
    meta = {
        "user.role.manage": PermissionMeta("user.role.manage", False, "ACCESS_CONTROL", "STANDARD"),
        "lead.read": PermissionMeta("lead.read", True, None, "STANDARD"),
    }
    base = Resolution(
        user_id="u",
        authz_version=1,
        meta=meta,
        granted={"user.role.manage": "ALL", "lead.read": "ALL"},
        has_active_factor=True,
    )
    r = apply_gate(base, user=_User(), session_type="FULL", mfa_verified=False, now=now)
    assert r.suspended == {"user.role.manage": "MFA_REQUIRED"} and "lead.read" in r.effective
    r = apply_gate(base, user=_User(), session_type="FULL", mfa_verified=True, now=now)
    assert "user.role.manage" in r.effective
    r = apply_gate(base, user=_User(now + timedelta(hours=1)), session_type="FULL", mfa_verified=True, now=now)
    assert r.suspended == {"user.role.manage": "COOLING_OFF"}
    r = apply_gate(base, user=_User(), session_type="RECOVERY", mfa_verified=False, now=now)
    assert r.effective == {}
