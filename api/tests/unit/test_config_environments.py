"""IR-09: configuration fails closed (SEC-005, PLAT-008, OPS-003, AUTH-004).

VEDA_ENV must name one of local/test/staging/production; only local and test derive development keys;
staging and production run the full deployed-environment validation, and the application, the CLI and
migrations refuse to start on any problem.
"""

import base64
import os

import pytest

from veda import config

GOOD_KEY = base64.b64encode(os.urandom(32)).decode()


def deployed_env(monkeypatch, env="production", **overrides):
    values = {
        "VEDA_ENV": env,
        "VEDA_JWT_PRIVATE_KEY_PEM": "test-placeholder-pem",
        "VEDA_JWT_KID": "prod-2026-09",
        "VEDA_CHAIN_KEY_LABEL": "prod-2026",
        "VEDA_RECOVERY_CODE_HMAC_KEY": GOOD_KEY,
        "VEDA_EMAIL_HASH_HMAC_KEY": GOOD_KEY,
        "VEDA_ACTION_TOKEN_KEY": GOOD_KEY,
        "VEDA_CHAIN_KEY": GOOD_KEY,
        "VEDA_TURNSTILE_SECRET": "0x-secret",
        "VEDA_TURNSTILE_MODE": "cloudflare",
        "VEDA_KMS_PROVIDER": "aws",
        "VEDA_KMS_KEY_ARN": "arn:aws:kms:ap-south-1:123456789012:key/1234abcd-12ab-34cd-56ef-1234567890ab",
        "VEDA_EMAIL_PROVIDER": "ses",
        "VEDA_APP_ORIGIN": "https://app.vedaspaces.com",
        "VEDA_PUBLIC_SITE_ORIGINS": "https://vedaspaces.com",
        "VEDA_API_BASE_URL": "https://api.vedaspaces.com",
        "VEDA_APP_BASE_URL": "https://app.vedaspaces.com",
        "VEDA_DATABASE_URL": "sqlite:////var/lib/veda/veda.db",
        "VEDA_SENTRY_DSN": "https://key@o1.ingest.sentry.io/1",
        "VEDA_ANCHOR_BUCKET": "veda-anchors",
        "VEDA_TRUSTED_PROXY_CIDRS": "172.18.0.1/32",
        "VEDA_SNAPSHOT_BUCKET": "veda-snapshots",
    }
    values.update(overrides)
    for name in list(os.environ):
        if name.startswith("VEDA_"):
            monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        if value is not None:
            monkeypatch.setenv(name, value)
    return config.load_settings()


@pytest.mark.parametrize("value", [None, "", "prod", "Production", "PRODUCTION", "stage", "dev", "qa"])
def test_IR09_unknown_or_missing_environment_refuses_to_load(monkeypatch, value):
    monkeypatch.delenv("VEDA_ENV", raising=False)
    if value is not None:
        monkeypatch.setenv("VEDA_ENV", value)
    with pytest.raises(config.ConfigError):
        config.load_settings()


@pytest.mark.parametrize("env", ["staging", "production"])
def test_IR09_complete_deployed_configuration_passes(monkeypatch, env):
    assert config.validate_environment(deployed_env(monkeypatch, env)) == []


@pytest.mark.parametrize("env", ["staging", "production"])
def test_IR09_deployed_environments_never_derive_development_keys(monkeypatch, env):
    s = deployed_env(
        monkeypatch, env, VEDA_RECOVERY_CODE_HMAC_KEY=None, VEDA_ACTION_TOKEN_KEY=None, VEDA_CHAIN_KEY=None
    )
    assert s.recovery_code_hmac_key == b"" and s.action_token_key == b""
    problems = " ".join(config.validate_environment(s))
    for name in ("VEDA_RECOVERY_CODE_HMAC_KEY", "VEDA_ACTION_TOKEN_KEY", "VEDA_CHAIN_KEY"):
        assert name in problems


@pytest.mark.parametrize("env", ["staging", "production"])
@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"VEDA_JWT_PRIVATE_KEY_PEM": None}, "VEDA_JWT_PRIVATE_KEY_PEM"),
        ({"VEDA_TURNSTILE_SECRET": None}, "VEDA_TURNSTILE_SECRET"),
        ({"VEDA_ACTION_TOKEN_KEY": base64.b64encode(b"x").decode()}, "VEDA_ACTION_TOKEN_KEY must be at least 32"),
        ({"VEDA_JWT_KID": "dev-1"}, "development labels"),
        ({"VEDA_KMS_PROVIDER": "local"}, "VEDA_KMS_PROVIDER"),
        ({"VEDA_KMS_KEY_ARN": "arn:aws:kms:ap-south-1:000000000000:key/local-dev"}, "VEDA_KMS_KEY_ARN"),
        ({"VEDA_EMAIL_PROVIDER": "capture"}, "VEDA_EMAIL_PROVIDER"),
        ({"VEDA_TURNSTILE_MODE": "dev"}, "VEDA_TURNSTILE_MODE"),
        ({"VEDA_COOKIE_SECURE": "false"}, "VEDA_COOKIE_SECURE"),
        ({"VEDA_RATE_LIMITS_ENABLED": "false"}, "VEDA_RATE_LIMITS_ENABLED"),
        ({"VEDA_ARGON2_MEMORY_KIB": "1024"}, "Argon2id"),
        ({"VEDA_APP_ORIGIN": "http://localhost:5173"}, "VEDA_APP_ORIGIN"),
        ({"VEDA_PUBLIC_SITE_ORIGINS": "http://vedaspaces.com"}, "VEDA_PUBLIC_SITE_ORIGINS"),
        ({"VEDA_API_BASE_URL": "https://127.0.0.1"}, "VEDA_API_BASE_URL"),
        ({"VEDA_DATABASE_URL": "sqlite:///var/veda.db"}, "VEDA_DATABASE_URL"),
        ({"VEDA_BREAK_GLASS_IDENTITY": "asserted"}, "VEDA_BREAK_GLASS_IDENTITY"),
        ({"VEDA_TRUSTED_PROXY_CIDRS": None}, "VEDA_TRUSTED_PROXY_CIDRS"),
        ({"VEDA_TRUSTED_PROXY_CIDRS": "not-a-network"}, "invalid network"),
        ({"VEDA_LEAD_RETENTION_ENABLED": "true"}, "LEAD_RETENTION_DAYS"),
    ],
)
def test_IR09_each_missing_or_weak_setting_is_reported(monkeypatch, env, override, fragment):
    problems = config.validate_environment(deployed_env(monkeypatch, env, **override))
    assert any(fragment in p for p in problems), problems


@pytest.mark.parametrize(
    "override,fragment",
    [
        ({"VEDA_SENTRY_DSN": None}, "VEDA_SENTRY_DSN"),
        ({"VEDA_ANCHOR_BUCKET": None}, "VEDA_ANCHOR_BUCKET"),
    ],
)
def test_IR09_production_only_requirements(monkeypatch, override, fragment):
    assert any(fragment in p for p in config.validate_environment(deployed_env(monkeypatch, "production", **override)))
    assert config.validate_environment(deployed_env(monkeypatch, "staging", **override)) == []


def test_IR09_invalid_base64_key_is_a_configuration_error(monkeypatch):
    with pytest.raises(config.ConfigError):
        deployed_env(monkeypatch, "staging", VEDA_CHAIN_KEY="not base64!")


def test_IR09_create_app_refuses_unsafe_staging(monkeypatch):
    from veda.app import create_app

    s = deployed_env(monkeypatch, "staging", VEDA_JWT_PRIVATE_KEY_PEM=None)
    with pytest.raises(RuntimeError, match="unsafe staging configuration"):
        create_app(s)


def test_IR09_migrate_refuses_unsafe_configuration(monkeypatch):
    from veda.cli.main import main

    deployed_env(monkeypatch, "production", VEDA_KMS_PROVIDER="local")
    with pytest.raises(SystemExit, match="unsafe production configuration"):
        main(["migrate"])


def test_IR09_P6b_development_jwt_key_and_verifier_are_unavailable_outside_local_and_test(monkeypatch):
    from veda.kernel import turnstile
    from veda.platform.auth import crypto, jwt_tokens

    previous = config._current
    try:
        config.use_settings(config.Settings(env="staging", turnstile_mode="dev", kms_provider="local"))
        jwt_tokens._keys = None
        with pytest.raises(RuntimeError, match="VEDA_JWT_PRIVATE_KEY_PEM"):
            jwt_tokens.issue(user_id="u", session_id="s", authz_version=1, amr=["pwd"], session_type="FULL")
        assert turnstile.verify("any-token", None) is False, "the accept-anything verifier fails closed"
        crypto.reset_provider()
        with pytest.raises(RuntimeError, match="local KMS"):
            crypto.kms_provider()
    finally:
        config._current = previous
        jwt_tokens._keys = None
        crypto.reset_provider()


@pytest.mark.parametrize("env", ["local", "test"])
def test_IR09_local_and_test_keep_development_defaults(monkeypatch, env):
    for name in list(os.environ):
        if name.startswith("VEDA_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VEDA_ENV", env)
    s = config.load_settings()
    assert len(s.action_token_key) == 32 and config.validate_environment(s) == []


def test_IRA13_siteverify_hostname_must_be_ours():
    from veda.kernel import turnstile

    previous = config._current
    config.use_settings(
        config.Settings(
            env="test", public_site_origins=["https://www.vedaspaces.com"], app_origin="https://app.vedaspaces.com"
        )
    )
    try:
        assert turnstile.accept({"success": True, "hostname": "www.vedaspaces.com"})
        assert not turnstile.accept({"success": True, "hostname": "evil.example"})
        assert not turnstile.accept({"success": False, "hostname": "www.vedaspaces.com"})
        assert not turnstile.accept({"success": True})
    finally:
        config._current = previous
