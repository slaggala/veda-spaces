"""RFC 6238 vectors, drift and replay (MFA-001, MFA-009); Argon2id and policy (AUTH-002, AUTH-003)."""

from datetime import UTC, datetime

import pytest

from veda.platform.auth import passwords, totp
from veda.platform.auth.crypto import (
    RECOVERY_ALPHABET,
    decrypt_secret,
    encrypt_secret,
    new_recovery_code,
    normalize_recovery_code,
)

RFC_SECRET = b"12345678901234567890"


@pytest.mark.parametrize(
    "unix, expected",
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_MFA_001_rfc6238_sha1_vectors(unix, expected):
    assert totp.hotp(RFC_SECRET, unix // 30, digits=8) == expected


def test_MFA_009_drift_and_replay():
    secret = totp.new_secret()
    at = datetime(2026, 9, 29, 10, 0, 15, tzinfo=UTC)
    step = totp.time_step(at)
    previous = totp.hotp(secret, step - 1)
    assert totp.verify(secret, previous, at, None) == step - 1  # T-1 accepted
    assert totp.verify(secret, totp.hotp(secret, step + 2), at, None) is None  # T+2 rejected
    assert totp.verify(secret, totp.hotp(secret, step), at, step) is None  # replay of the used step
    assert totp.is_replay(secret, totp.hotp(secret, step), at, step)
    assert totp.verify(secret, "12345", at, None) is None
    assert len(secret) == 20  # 160-bit (MFA-010)


def test_MFA_010_secret_envelope_encryption_roundtrip():
    secret = totp.new_secret()
    ciphertext, wrapped, arn = encrypt_secret(secret)
    assert secret.hex() not in ciphertext and totp.b32(secret) not in ciphertext
    assert decrypt_secret(ciphertext, wrapped, arn) == secret


def test_MFA_005_recovery_code_format():
    codes = {new_recovery_code() for _ in range(200)}
    assert len(codes) == 200
    for code in codes:
        raw = normalize_recovery_code(code)
        assert len(raw) == 10 and set(raw) <= set(RECOVERY_ALPHABET) and code[5] == "-"
    assert len(RECOVERY_ALPHABET) == 32 and not set("01OI") & set(RECOVERY_ALPHABET)


def test_AUTH_002_argon2id_hash_and_verify():
    h = passwords.hash_password("Terracotta-Lantern-2026!")
    assert h.startswith("$argon2id$")
    assert passwords.verify_password(h, "Terracotta-Lantern-2026!")
    assert not passwords.verify_password(h, "wrong")
    assert not passwords.verify_password(None, "anything")


@pytest.mark.parametrize(
    "password, codes",
    [
        ("short", {"TOO_SHORT"}),
        ("password1234", {"TOO_COMMON"}),
        ("aaaaaaaaaaaaaaaa", {"TOO_COMMON"}),
        ("vedaspaces-rules-2026", {"CONTAINS_PERSONAL_INFO"}),
        ("priya-garden-house-9", {"CONTAINS_PERSONAL_INFO"}),
        ("x" * 129 + "Yz", {"TOO_LONG"}),
        ("Terracotta-Lantern-2026!", set()),
    ],
)
def test_AUTH_003_password_policy(password, codes):
    got = set(passwords.policy_violations(password, email="priya@vedaspaces.com", full_name="Priya Sharma"))
    assert codes <= got if codes else not got
