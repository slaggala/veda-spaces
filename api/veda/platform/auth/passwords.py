"""Argon2id hashing and the password policy (05 §2, AUTH-002, AUTH-003)."""

from __future__ import annotations

import threading
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from veda.config import settings

MIN_LENGTH = 12
MAX_LENGTH = 128

# Bundled common/breached list (a curated subset; the HIBP k-anonymity check is P1).
COMMON_PASSWORDS = frozenset(
    p.lower()
    for p in """
123456789012 1234567890123 password1234 password12345 passwordpassword qwertyuiop12 qwertyuiopasdf
iloveyou1234 letmein12345 welcome12345 administrator admin1234567 changeme1234 abc123abc123
111111111111 000000000000 123123123123 football1234 monkey123456 dragon123456 sunshine1234
princess1234 baseball1234 superman1234 trustno11234 passw0rd1234 p@ssw0rd1234 p@ssword1234
correcthorsebatterystaple qwerty123456 asdfghjkl123 zxcvbnm12345 india1234567 mumbai123456
hyderabad123 bangalore123 chennai12345 delhi1234567 password@123 Password@123 Welcome@1234
Admin@123456 Qwerty@12345 Test@1234567 abcdefghijkl abcdefgh1234 987654321098 1q2w3e4r5t6y
1qaz2wsx3edc qazwsxedcrfv
""".split()
)

_hasher: PasswordHasher | None = None
_hasher_params: tuple | None = None
_semaphore: threading.BoundedSemaphore | None = None
_dummy_hash: str | None = None


def _get() -> tuple[PasswordHasher, threading.BoundedSemaphore]:
    global _hasher, _hasher_params, _semaphore, _dummy_hash
    s = settings()
    params = (s.argon2_time_cost, s.argon2_memory_kib, s.argon2_parallelism, s.argon2_concurrency)
    if _hasher is None or params != _hasher_params:
        _hasher = PasswordHasher(
            time_cost=params[0], memory_cost=params[1], parallelism=params[2], hash_len=32, salt_len=16
        )
        _hasher_params = params
        _semaphore = threading.BoundedSemaphore(params[3])
        _dummy_hash = _hasher.hash("veda-timing-equalization-dummy")
    return _hasher, _semaphore  # type: ignore[return-value]  # both globals are set just above; mypy sees Optional


def normalize(password: str) -> str:
    return unicodedata.normalize("NFKC", password)


def hash_password(password: str) -> str:
    hasher, sem = _get()
    with sem:
        return hasher.hash(normalize(password))


def verify_password(password_hash: str | None, password: str) -> bool:
    hasher, sem = _get()
    with sem:
        try:
            return hasher.verify(password_hash or _dummy_hash, normalize(password)) and password_hash is not None
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False


def verify_dummy(password: str) -> None:
    """Timing equalization for unknown accounts (05 §2.2)."""
    verify_password(None, password)


def needs_rehash(password_hash: str) -> bool:
    hasher, _ = _get()
    try:
        return hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def policy_violations(password: str, *, email: str | None = None, full_name: str | None = None) -> list[str]:
    """Returns the violated rule codes: TOO_SHORT, TOO_LONG, TOO_COMMON, CONTAINS_PERSONAL_INFO."""
    pw = normalize(password or "")
    problems: list[str] = []
    if len(pw) < MIN_LENGTH:
        problems.append("TOO_SHORT")
    if len(pw) > MAX_LENGTH:
        problems.append("TOO_LONG")
    lowered = pw.lower()
    if lowered in COMMON_PASSWORDS or len(set(lowered)) <= 2:
        problems.append("TOO_COMMON")
    personal = {"veda", "vedaspaces"}
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 3:
            personal.add(local)
    if full_name:
        personal.update(part.lower() for part in full_name.split() if len(part) >= 3)
    if any(token and token in lowered for token in personal):
        problems.append("CONTAINS_PERSONAL_INFO")
    return problems
