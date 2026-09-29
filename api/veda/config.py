"""Environment-driven settings (02 §3.2, OPS-003).

Secrets are injected from SSM/Secrets Manager as environment variables in
staging and production (SEC-005). ``VEDA_ENV`` must name one of the four
environments explicitly; anything else refuses to load (IR-09). Only ``local``
and ``test`` derive development keys; ``staging`` and ``production`` refuse to
start without real ones and without the deployed-environment checks.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os
import re
from dataclasses import dataclass, field
from datetime import timedelta
from urllib.parse import urlparse

ENVIRONMENTS = ("local", "test", "staging", "production")
DEPLOYED_ENVIRONMENTS = ("staging", "production")
MIN_KEY_BYTES = 32
_KMS_ARN = re.compile(r"^arn:aws[a-z-]*:kms:[a-z0-9-]+:\d{12}:(key|alias)/[A-Za-z0-9/_-]+$")


class ConfigError(RuntimeError):
    """The environment is not one of ENVIRONMENTS or a value cannot be parsed."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else default


def _str(name: str, default: str) -> str:
    value = _env(name)
    return value if value is not None else default


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int | None) -> int | None:
    value = _env(name)
    return int(value) if value is not None else default


def _intd(name: str, default: int) -> int:
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
    # Nightly snapshots (OPS-002, IR-11): local directory, optional Object Lock bucket, local copies kept.
    snapshot_dir: str | None = None
    snapshot_bucket: str | None = None
    snapshot_keep: int = 7
    snapshot_lock_days: int = 35
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    worker_poll_seconds: float = 2.0
    # Break-glass custodian identity (06 §7.5): "sts" derives the caller from AWS STS; "asserted" trusts the
    # --principal-arn argument and is refused outside local/test (IR-06).
    break_glass_identity: str = "sts"
    # Peers whose CF-Connecting-IP header is believed (02 §11, IR-35): the local tunnel by default.
    trusted_proxy_cidrs: list[str] = field(default_factory=lambda: ["127.0.0.1/32", "::1/128"])
    # Schema revisions newer than this image that the operator declared expand-only compatible (IR-10, AM-6).
    schema_ahead_accepted: list[str] = field(default_factory=list)
    testing: bool = False

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_deployed(self) -> bool:
        return self.env in DEPLOYED_ENVIRONMENTS

    @property
    def dev_keys_allowed(self) -> bool:
        return self.env in ("local", "test")

    @property
    def allowed_origins(self) -> list[str]:
        return [self.app_origin, *self.public_site_origins]


def load_settings(**overrides) -> Settings:
    env = overrides.get("env") or _env("VEDA_ENV")
    if env not in ENVIRONMENTS:
        raise ConfigError(f"VEDA_ENV must be one of {', '.join(ENVIRONMENTS)} (got {env!r})")
    dev_secret = _str("VEDA_DEV_SECRET", "local-development-only")

    def key(name: str, label: str) -> bytes:
        raw = _env(name)
        if raw:
            try:
                return base64.b64decode(raw, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ConfigError(f"{name} is not valid base64") from exc
        # Development keys are derived from a public constant: never outside local and test.
        return _dev_key(label, dev_secret) if env in ("local", "test") else b""

    chain_label = _str("VEDA_CHAIN_KEY_LABEL", "dev-2026")
    chain_keys = {chain_label: key("VEDA_CHAIN_KEY", "chain")}
    for item in _list("VEDA_CHAIN_KEYS_RETIRED", []):  # "label:base64,label:base64"
        label, _, b64 = item.partition(":")
        try:
            chain_keys[label] = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ConfigError(f"VEDA_CHAIN_KEYS_RETIRED entry {label!r} is not valid base64") from exc

    custodians = {}
    for item in _list("VEDA_BREAK_GLASS_CUSTODIANS", []):
        arn, _, human = item.partition("=")
        custodians[arn] = human

    settings = Settings(
        env=env,
        database_url=_str("VEDA_DATABASE_URL", "sqlite:///var/veda.db"),
        app_origin=_str("VEDA_APP_ORIGIN", "http://localhost:5173"),
        public_site_origins=_list("VEDA_PUBLIC_SITE_ORIGINS", ["http://localhost:8000"]),
        api_base_url=_str("VEDA_API_BASE_URL", "http://localhost:5000"),
        app_base_url=_str("VEDA_APP_BASE_URL", "http://localhost:5173"),
        jwt_private_key_pem=_env("VEDA_JWT_PRIVATE_KEY_PEM"),
        jwt_kid=_str("VEDA_JWT_KID", "dev-1"),
        jwt_previous_public_key_pem=_env("VEDA_JWT_PREVIOUS_PUBLIC_KEY_PEM"),
        jwt_previous_kid=_env("VEDA_JWT_PREVIOUS_KID"),
        jwt_issuer=_str("VEDA_JWT_ISSUER", "https://api.vedaspaces.com"),
        jwt_audience=_str("VEDA_JWT_AUDIENCE", "veda-workspace"),
        cookie_secure=_bool("VEDA_COOKIE_SECURE", True),
        argon2_memory_kib=_intd("VEDA_ARGON2_MEMORY_KIB", 65536),
        argon2_time_cost=_intd("VEDA_ARGON2_TIME_COST", 3),
        argon2_parallelism=_intd("VEDA_ARGON2_PARALLELISM", 1),
        recovery_code_hmac_key=key("VEDA_RECOVERY_CODE_HMAC_KEY", "recovery"),
        email_hash_hmac_key=key("VEDA_EMAIL_HASH_HMAC_KEY", "email-hash"),
        action_token_key=key("VEDA_ACTION_TOKEN_KEY", "action-token"),
        chain_keys=chain_keys,
        chain_key_label=chain_label,
        kms_key_arn=_str("VEDA_KMS_KEY_ARN", "arn:aws:kms:ap-south-1:000000000000:key/local-dev"),
        kms_provider=_str("VEDA_KMS_PROVIDER", "local"),
        local_kms_master_key=key("VEDA_LOCAL_KMS_MASTER_KEY", "local-kms"),
        aws_region=_str("VEDA_AWS_REGION", "ap-south-1"),
        email_provider=_str("VEDA_EMAIL_PROVIDER", "capture"),
        email_sender=_str("VEDA_EMAIL_SENDER", "Veda Spaces <no-reply@vedaspaces.com>"),
        email_capture_dir=_env("VEDA_EMAIL_CAPTURE_DIR"),
        ses_configuration_set=_env("VEDA_SES_CONFIGURATION_SET"),
        turnstile_secret=_env("VEDA_TURNSTILE_SECRET"),
        turnstile_mode=_str("VEDA_TURNSTILE_MODE", "dev"),
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
        snapshot_dir=_env("VEDA_SNAPSHOT_DIR"),
        snapshot_bucket=_env("VEDA_SNAPSHOT_BUCKET"),
        snapshot_keep=_intd("VEDA_SNAPSHOT_KEEP", 7),
        snapshot_lock_days=_intd("VEDA_SNAPSHOT_LOCK_DAYS", 35),
        sentry_dsn=_env("VEDA_SENTRY_DSN"),
        log_level=_str("VEDA_LOG_LEVEL", "INFO"),
        break_glass_identity=_str("VEDA_BREAK_GLASS_IDENTITY", "sts"),
        trusted_proxy_cidrs=_list("VEDA_TRUSTED_PROXY_CIDRS", ["127.0.0.1/32", "::1/128"]),
        schema_ahead_accepted=_list("VEDA_SCHEMA_AHEAD_ACCEPTED", []),
    )
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _is_public_https(url: str) -> bool:
    parsed = urlparse(url or "")
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and bool(host)
        and host not in ("localhost", "127.0.0.1", "::1")
        and not host.endswith(".localhost")
    )


def validate_environment(settings: Settings) -> list[str]:
    """Deployed environments (staging, production) refuse development secrets and unsafe settings
    (SEC-005, PLAT-008, IR-09). local and test are accepted as they are."""
    problems: list[str] = []
    if settings.env not in ENVIRONMENTS:
        return [f"VEDA_ENV must be one of {', '.join(ENVIRONMENTS)}"]
    if not settings.is_deployed:
        return problems
    env = settings.env
    required = {
        "VEDA_JWT_PRIVATE_KEY_PEM": settings.jwt_private_key_pem,
        "VEDA_TURNSTILE_SECRET": settings.turnstile_secret,
    }
    problems += [f"{k} is required in {env}" for k, v in required.items() if not v]
    keys = {
        "VEDA_RECOVERY_CODE_HMAC_KEY": settings.recovery_code_hmac_key,
        "VEDA_EMAIL_HASH_HMAC_KEY": settings.email_hash_hmac_key,
        "VEDA_ACTION_TOKEN_KEY": settings.action_token_key,
        "VEDA_CHAIN_KEY": settings.chain_keys.get(settings.chain_key_label, b""),
    }
    for name, value in keys.items():
        if len(value or b"") < MIN_KEY_BYTES:
            problems.append(f"{name} must be at least {MIN_KEY_BYTES} random bytes in {env}")
    if settings.jwt_kid in ("", "dev-1") or settings.chain_key_label.startswith("dev-"):
        problems.append(f"VEDA_JWT_KID and VEDA_CHAIN_KEY_LABEL must not be development labels in {env}")
    if settings.kms_provider != "aws":
        problems.append(f"VEDA_KMS_PROVIDER must be aws in {env}")
    if (
        not _KMS_ARN.match(settings.kms_key_arn or "")
        or ":000000000000:" in settings.kms_key_arn
        or settings.kms_key_arn.endswith("local-dev")
    ):
        problems.append(f"VEDA_KMS_KEY_ARN must be a real KMS key ARN in {env}")
    if settings.email_provider != "ses":
        problems.append(f"VEDA_EMAIL_PROVIDER must be ses in {env}")
    if settings.turnstile_mode != "cloudflare":
        problems.append(f"VEDA_TURNSTILE_MODE must be cloudflare in {env}")
    if not settings.cookie_secure:
        problems.append(f"VEDA_COOKIE_SECURE must be true in {env}")
    if not settings.rate_limits_enabled:
        problems.append(f"VEDA_RATE_LIMITS_ENABLED must be true in {env}")
    if settings.argon2_memory_kib < 19456 or settings.argon2_time_cost < 2:
        problems.append("Argon2id parameters below the OWASP minimum (05 §2.1)")
    for name, url in (
        ("VEDA_APP_ORIGIN", settings.app_origin),
        ("VEDA_API_BASE_URL", settings.api_base_url),
        ("VEDA_APP_BASE_URL", settings.app_base_url),
        *(("VEDA_PUBLIC_SITE_ORIGINS", o) for o in settings.public_site_origins),
    ):
        if not _is_public_https(url):
            problems.append(f"{name} must be a public https origin in {env} (got {url!r})")
    db_url = settings.database_url or ""
    if not (db_url.startswith("sqlite:////") or db_url.startswith("postgresql")):
        problems.append(f"VEDA_DATABASE_URL must be an absolute SQLite path or PostgreSQL URL in {env}")
    if not _env("VEDA_TRUSTED_PROXY_CIDRS") and settings.trusted_proxy_cidrs == ["127.0.0.1/32", "::1/128"]:
        problems.append(f"VEDA_TRUSTED_PROXY_CIDRS must name the proxy in front of the origin in {env}")
    try:
        import ipaddress

        for cidr in settings.trusted_proxy_cidrs:
            ipaddress.ip_network(cidr, strict=False)
    except ValueError:
        problems.append("VEDA_TRUSTED_PROXY_CIDRS contains an invalid network")
    if settings.break_glass_identity != "sts":
        problems.append(f"VEDA_BREAK_GLASS_IDENTITY must be sts in {env}")
    if settings.lead_retention_enabled and not settings.lead_retention_days:
        problems.append("LEAD_RETENTION_ENABLED requires an approved LEAD_RETENTION_DAYS (OWNER-INPUT-002)")
    if settings.is_production:
        if not settings.sentry_dsn:
            problems.append("VEDA_SENTRY_DSN is required in production (LOG-004)")
        if not settings.anchor_bucket:
            problems.append("VEDA_ANCHOR_BUCKET is required in production (SEVT-007)")
        if not settings.snapshot_bucket:
            problems.append("VEDA_SNAPSHOT_BUCKET is required in production (OPS-002)")
    return problems


# Kept for callers written before staging was validated.
validate_production = validate_environment


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
