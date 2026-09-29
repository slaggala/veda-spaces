"""Test data factories. Users are created directly as SYSTEM (like the bootstrap
CLI or an accepted invitation would leave them); flows under test go through
the HTTP API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

import sqlalchemy as sa

from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.kernel.dto import normalize_email
from veda.kernel.ids import new_id
from veda.platform.auth import passwords, totp
from veda.platform.auth.crypto import encrypt_secret
from veda.platform.auth.models import UserMfaFactor
from veda.platform.identity.models import User, UserCredential
from veda.platform.rbac.models import Permission, Role, UserPermission, UserRole

DEFAULT_PASSWORD = "Terracotta-Lantern-2026!"


@dataclass
class TestUser:
    id: str
    email: str
    password: str
    secret: bytes | None
    roles: tuple[str, ...]
    full_name: str
    token: str | None = None
    extra: dict = field(default_factory=dict)

    def code(self) -> str:
        """A fresh TOTP code. Advances the clock one step so codes are never replays (MFA-009)."""
        clock.advance(timedelta(seconds=31))
        return totp.code_at(self.secret, clock.now())


class Factory:
    def __init__(self):
        self._n = 0

    def _next(self) -> int:
        self._n += 1
        return self._n

    def role_id(self, code: str) -> str:
        with db.unit_of_work(write=False) as s:
            return s.execute(sa.select(Role.id).where(Role.code == code)).scalar_one()

    def user(self, *roles: str, mfa: bool | None = None, founder: bool = False, password: str = DEFAULT_PASSWORD,
             email: str | None = None, status: str = "ACTIVE", full_name: str | None = None,
             mfa_required: bool = False) -> TestUser:
        n = self._next()
        roles = tuple(roles) or (("FOUNDER",) if founder else ("SALES",))
        if founder and "FOUNDER" not in roles:
            roles = ("FOUNDER", *roles)
        email = email or f"user{n}-{new_id()[-6:]}@vedaspaces.test"
        full_name = full_name or f"Test User {n}"
        if mfa is None:
            mfa = any(r in ("FOUNDER", "ADMIN") for r in roles)
        secret = totp.new_secret() if mfa else None
        with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
            now = db.tx_time(s)
            user = User(email=email, email_normalized=normalize_email(email), full_name=full_name,
                        display_name=full_name.split()[0], user_type="HUMAN", status=status, status_changed_on=now,
                        timezone="Asia/Kolkata", locale="en-IN", email_verified_on=now if status == "ACTIVE" else None,
                        protection_level="FOUNDER" if "FOUNDER" in roles else "STANDARD", mfa_required=mfa_required,
                        authz_version=1)
            s.add(user)
            s.flush()
            s.add(UserCredential(user_id=user.id, password_hash=passwords.hash_password(password),
                                 password_changed_on=now, must_change_password=False, failed_login_count=0))
            for code in roles:
                role_id = s.execute(sa.select(Role.id).where(Role.code == code)).scalar_one()
                s.add(UserRole(user_id=user.id, role_id=role_id, reason="test fixture"))
            if secret is not None:
                ciphertext, wrapped, arn = encrypt_secret(secret)
                s.add(UserMfaFactor(user_id=user.id, factor_type="TOTP", status="ACTIVE", secret_ciphertext=ciphertext,
                                    wrapped_data_key=wrapped, kms_key_arn=arn, confirmed_on=now, label="test phone"))
            uid = user.id
        return TestUser(uid, email, password, secret, roles, full_name)

    def grant(self, user: TestUser, code: str, *, effect: str = "GRANT", scope: str = "ALL") -> str:
        with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
            pid = s.execute(sa.select(Permission.id).where(Permission.code == code)).scalar_one()
            row = UserPermission(user_id=user.id, permission_id=pid, effect=effect, scope=scope, reason="test fixture")
            s.add(row)
            u = s.get(User, user.id)
            u.authz_version += 1
            s.flush()
            return row.id

    def login(self, api, user: TestUser, *, set_default: bool = True) -> str:
        r = api.post("/api/v1/auth/login", {"email": user.email, "password": user.password}, anonymous=True)
        assert r.status == 200, r
        if r.data["status"] == "MFA_REQUIRED":
            r = api.post("/api/v1/auth/mfa/verify", {"mfa_token": r.data["mfa_token"], "code": user.code()}, anonymous=True)
            assert r.status == 200, r
        assert r.data["status"] == "AUTHENTICATED", r
        user.token = r.data["access_token"]
        if set_default:
            api.token = user.token
        return user.token

    def get_user(self, user_id: str) -> User:
        with db.unit_of_work(write=False) as s:
            user = s.get(User, user_id, execution_options={"include_deleted": True})
            s.expunge_all()
            return user

    def lead(self, api, token: str, **fields) -> dict:
        body = {"name": "Anita Reddy", "phone": f"+9198{self._next():08d}", "source_code": "REFERRAL", **fields}
        r = api.post("/api/v1/leads", body, token=token)
        assert r.status == 201, r
        return r.data

    def public_lead(self, api, key: str | None = None, **fields) -> object:
        body = {"name": "Kiran Rao", "phone": f"98{self._next():08d}",
                "consent": {"acknowledged": True, "policy_version": "2026-09-v1"},
                "turnstile_token": "ok-token", "company_website_url": "", **fields}
        return api.post("/api/v1/public/leads", body, anonymous=True,
                        headers={"Idempotency-Key": key or f"key-{new_id()}", "Origin": "http://localhost:8000"})
