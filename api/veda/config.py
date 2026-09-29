"""Environment-driven settings (02 §3.2, OPS-003).

Secrets are injected from SSM/Secrets Manager as environment variables in
production (SEC-005). Local and test environments get generated development
keys; production refuses to start without real ones.
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass, field
from datetime import timedelta


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int | None) -> int | None:
    value = _env(name)
    return int(value) if value is not None else default


def _list(name: str, default: list[str]) -> list[str]:
    value = _env(name)
    if value is None:
        return default
    return [v.strip() for v in value.split(",") if v.strip()]


def _dev_key(label: str, secret: str) -> bytes:
    return hashlib.sha256(f"veda-dev::{label}::{secret}".encode()).digest()


@dataclass
class Settings:
    env: str = "local"  # local | test | staging | production
    database_url: str = "sqlite:///var/veda.db"
    app_origin: str = "http://localhost:5173"
    public_site_origins: list[str] = field(default_factory=lambda: ["http://localhost:8000"])
    api_base_url: str = "http://localhost:5000"
    app_base_url: str = "http://localhost:5173"
    # JWT (05 §5): ES256 keys as PEM; previous key accepted for rotation overlap.
    jwt_private_key_pem: str | None = None
    jwt_kid: str = "dev-1"
    jwt_previous_public_key_pem: str | None = None
    jwt_previous_kid: str | None = None
    jwt_issuer: str = "https://api.vedaspaces.com"
    jwt_audience: str = "veda-workspace"
    access_token_ttl: timedelta = timedelta(minutes=15)
    refresh_idle_ttl: timedelta = timedelta(days=7)
    refresh_absolute_ttl: timedelta = timedelta(days=30)
    refresh_grace: timedelta = timedelta(seconds=20)
    recovery_session_ttl: timedelta = timedelta(minutes=15)
    cookie_secure: bool = True
    cookie_name: str = "vs_rt"
    # Argon2id (05 §2.1). Final values are set by host benchmark (ASM-010).
    argon2_memory_kib: int = 65536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 1
    argon2_concurrency: int = 4
    # Keys (SEC-005). 32-byte keys, base64 in env.
    recovery_code_hmac_key: bytes = b""
    email_hash_hmac_key: bytes = b""
    action_token_key: bytes = b""
    chain_keys: dict[str, bytes] = field(default_factory=dict)
    chain_key_label: str = "dev-2026"
    # MFA secret envelope encryption (03 §5.5, F-13)
    kms_key_arn: str = "arn:aws:kms:ap-south-1:000000000000:key/local-dev"
    kms_provider: str = "local"  # local | aws
    local_kms_master_key: bytes = b""
    aws_region: str = "ap-south-1"
    # Email (NOTIF-009)
    email_provider: str = "capture"  # capture | log | ses
    email_sender: str = "Veda Spaces <no-reply@vedaspaces.com>"
    email_capture_dir: str | None = None
    ses_configuration_set: str | None = None
    # Turnstile (LEAD-018)
    turnstile_secret: str | None = None
    turnstile_mode: str = "dev"  # dev | cloudflare
    # Public intake (ADR-005)
    published_policy_versions: list[str] = field(default_factory=lambda: ["2026-09-v1"])
    whatsapp_number: str = "919515125153"
    # Rate limits (08 §12)
    rate_limits_enabled: bool = True
    # Workflow timings
    approval_expiry: timedelta = timedelta(hours=24)
    break_glass_delay: timedelta = timedelta(hours=24)
    mfa_recovery_cooling_off: timedelta = timedelta(hours=24)
    step_up_window: timedelta = timedelta(minutes=10)
    reauth_window: timedelta = timedelta(minutes=5)
    email_verification_ttl: timedelta = timedelta(minutes=60)
    # Break-glass custodian register (OWNER-INPUT-004): "arn=human,arn=human"
    break_glass_custodians: dict[str, str] = field(default_factory=dict)
    # Retention (OWNER-INPUT-002). None = not approved → nothing is purged.
    user_session_retention_days: int | None = None
    token_retention_days: int | None = None
    outbox_retention_days: int | None = None
    notification_read_retention_days: int | None = None
    notification_unread_retention_days: int | None = None
    security_event_online_retention_days: int | None = None
    audit_online_retention_days: int | None = None
    lead_retention_days: int | None = None
    lead_retention_enabled: bool = False
    spam_review_age_hours: int = 24
    anchor_dir: str | None = None
    anchor_bucket: str | None = None
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    worker_poll_seconds: float = 2.0
    testing: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def allowed_origins(self) -> list[str]:
        return [self.app_origin, *self.public_site_origins]


def load_settings(**overrides) -> Settings:
    env = _env("VEDA_ENV", "local")
    dev_secret = _env("VEDA_DEV_SECRET", "local-development-only")

    def key(name: str, label: str) -> bytes:
        raw = _env(name)
        if raw:
            return base64.b64decode(raw)
        return _dev_key(label, dev_secret)

    chain_label = _env("VEDA_CHAIN_KEY_LABEL", "dev-2026")
    chain_keys = {chain_label: key("VEDA_CHAIN_KEY", "chain")}
    for item in _list("VEDA_CHAIN_KEYS_RETIRED", []):  # "label:base64,label:base64"
        label, _, b64 = item.partition(":")
        chain_keys[label] = base64.b64decode(b64)

    custodians = {}
    for item in _list("VEDA_BREAK_GLASS_CUSTODIANS", []):
        arn, _, human = item.partition("=")
        custodians[arn] = human

    settings = Settings(
        env=env,
        database_url=_env("VEDA_DATABASE_URL", "sqlite:///var/veda.db"),
        app_origin=_env("VEDA_APP_ORIGIN", "http://localhost:5173"),
        public_site_origins=_list("VEDA_PUBLIC_SITE_ORIGINS", ["http://localhost:8000"]),
        api_base_url=_env("VEDA_API_BASE_URL", "http://localhost:5000"),
        app_base_url=_env("VEDA_APP_BASE_URL", "http://localhost:5173"),
        jwt_private_key_pem=_env("VEDA_JWT_PRIVATE_KEY_PEM"),
        jwt_kid=_env("VEDA_JWT_KID", "dev-1"),
        jwt_previous_public_key_pem=_env("VEDA_JWT_PREVIOUS_PUBLIC_KEY_PEM"),
        jwt_previous_kid=_env("VEDA_JWT_PREVIOUS_KID"),
        jwt_issuer=_env("VEDA_JWT_ISSUER", "https://api.vedaspaces.com"),
        jwt_audience=_env("VEDA_JWT_AUDIENCE", "veda-workspace"),
        cookie_secure=_bool("VEDA_COOKIE_SECURE", True),
        argon2_memory_kib=_int("VEDA_ARGON2_MEMORY_KIB", 65536),
        argon2_time_cost=_int("VEDA_ARGON2_TIME_COST", 3),
        argon2_parallelism=_int("VEDA_ARGON2_PARALLELISM", 1),
        recovery_code_hmac_key=key("VEDA_RECOVERY_CODE_HMAC_KEY", "recovery"),
        email_hash_hmac_key=key("VEDA_EMAIL_HASH_HMAC_KEY", "email-hash"),
        action_token_key=key("VEDA_ACTION_TOKEN_KEY", "action-token"),
        chain_keys=chain_keys,
        chain_key_label=chain_label,
        kms_key_arn=_env("VEDA_KMS_KEY_ARN", "arn:aws:kms:ap-south-1:000000000000:key/local-dev"),
        kms_provider=_env("VEDA_KMS_PROVIDER", "local"),
        local_kms_master_key=key("VEDA_LOCAL_KMS_MASTER_KEY", "local-kms"),
        aws_region=_env("VEDA_AWS_REGION", "ap-south-1"),
        email_provider=_env("VEDA_EMAIL_PROVIDER", "capture"),
        email_sender=_env("VEDA_EMAIL_SENDER", "Veda Spaces <no-reply@vedaspaces.com>"),
        email_capture_dir=_env("VEDA_EMAIL_CAPTURE_DIR"),
        ses_configuration_set=_env("VEDA_SES_CONFIGURATION_SET"),
        turnstile_secret=_env("VEDA_TURNSTILE_SECRET"),
        turnstile_mode=_env("VEDA_TURNSTILE_MODE", "dev"),
        published_policy_versions=_list("VEDA_PUBLISHED_POLICY_VERSIONS", ["2026-09-v1"]),
        rate_limits_enabled=_bool("VEDA_RATE_LIMITS_ENABLED", True),
        break_glass_custodians=custodians,
        user_session_retention_days=_int("VEDA_USER_SESSION_RETENTION_DAYS", None),
        token_retention_days=_int("VEDA_TOKEN_RETENTION_DAYS", None),
        outbox_retention_days=_int("VEDA_OUTBOX_RETENTION_DAYS", None),
        notification_read_retention_days=_int("VEDA_NOTIFICATION_READ_RETENTION_DAYS", None),
        notification_unread_retention_days=_int("VEDA_NOTIFICATION_UNREAD_RETENTION_DAYS", None),
        security_event_online_retention_days=_int("VEDA_SECURITY_EVENT_ONLINE_RETENTION_DAYS", None),
        audit_online_retention_days=_int("VEDA_AUDIT_ONLINE_RETENTION_DAYS", None),
        lead_retention_days=_int("VEDA_LEAD_RETENTION_DAYS", None),
        lead_retention_enabled=_bool("VEDA_LEAD_RETENTION_ENABLED", False),
        anchor_dir=_env("VEDA_ANCHOR_DIR"),
        anchor_bucket=_env("VEDA_ANCHOR_BUCKET"),
        sentry_dsn=_env("VEDA_SENTRY_DSN"),
        log_level=_env("VEDA_LOG_LEVEL", "INFO"),
    )
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def validate_production(settings: Settings) -> list[str]:
    """Production refuses development secrets and unsafe settings (SEC-005)."""
    problems: list[str] = []
    if not settings.is_production:
        return problems
    required = {
        "VEDA_JWT_PRIVATE_KEY_PEM": settings.jwt_private_key_pem,
        "VEDA_RECOVERY_CODE_HMAC_KEY": _env("VEDA_RECOVERY_CODE_HMAC_KEY"),
        "VEDA_EMAIL_HASH_HMAC_KEY": _env("VEDA_EMAIL_HASH_HMAC_KEY"),
        "VEDA_ACTION_TOKEN_KEY": _env("VEDA_ACTION_TOKEN_KEY"),
        "VEDA_CHAIN_KEY": _env("VEDA_CHAIN_KEY"),
        "VEDA_TURNSTILE_SECRET": settings.turnstile_secret,
    }
    problems += [f"{k} is required in production" for k, v in required.items() if not v]
    if settings.kms_provider != "aws":
        problems.append("VEDA_KMS_PROVIDER must be aws in production")
    if settings.email_provider != "ses":
        problems.append("VEDA_EMAIL_PROVIDER must be ses in production")
    if settings.turnstile_mode != "cloudflare":
        problems.append("VEDA_TURNSTILE_MODE must be cloudflare in production")
    if not settings.cookie_secure:
        problems.append("VEDA_COOKIE_SECURE must be true in production")
    if settings.argon2_memory_kib < 19456 or settings.argon2_time_cost < 2:
        problems.append("Argon2id parameters below the OWASP minimum (05 §2.1)")
    if settings.lead_retention_enabled and not settings.lead_retention_days:
        problems.append("LEAD_RETENTION_ENABLED requires an approved LEAD_RETENTION_DAYS (OWNER-INPUT-002)")
    return problems


_current: Settings | None = None


def settings() -> Settings:
    global _current
    if _current is None:
        _current = load_settings()
    return _current


def use_settings(value: Settings) -> Settings:
    global _current
    _current = value
    return value
