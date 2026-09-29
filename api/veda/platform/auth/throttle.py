"""Login and MFA throttling (05 §4, AUTH-010, A-01).

* Per (account, network): after 5 consecutive password failures from one
  IPv4 /24 or IPv6 /64, that pair is throttled with an escalating delay (max
  15 min) and its next attempt needs a Turnstile token. The account is not
  globally locked.
* Global: failures from ≥ 5 distinct networks within 15 minutes throttle the
  account for 15 minutes (``user_credential.locked_until``). Holders of an
  ACTIVE factor are exempt: password + TOTP still succeeds.
* MFA: 10 MFA or recovery failures per account in 15 minutes throttle MFA
  for 15 minutes.
* Password re-entry: 10 failed re-authentications or current-password checks
  per account in 15 minutes throttle both for 15 minutes (IR-24), so a stolen
  bearer token cannot be used to guess the password that satisfies step-up.

The per-network state is in-process and authoritative because exactly one
application process runs (OPS-010, F-09).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from veda.kernel import clock

PAIR_THRESHOLD = 5
MAX_PAIR_DELAY = timedelta(minutes=15)
GLOBAL_NETWORKS = 5
GLOBAL_WINDOW = timedelta(minutes=15)
GLOBAL_THROTTLE = timedelta(minutes=15)
MFA_FAILURES = 10
MFA_WINDOW = timedelta(minutes=15)
MFA_THROTTLE = timedelta(minutes=15)
REAUTH_FAILURES = 10
REAUTH_WINDOW = timedelta(minutes=15)
REAUTH_THROTTLE = timedelta(minutes=15)


@dataclass
class _Pair:
    failures: int = 0
    blocked_until: datetime | None = None


@dataclass
class _Account:
    network_failures: dict[str, datetime] = field(default_factory=dict)
    mfa_failures: list[datetime] = field(default_factory=list)
    mfa_blocked_until: datetime | None = None
    reauth_failures: list[datetime] = field(default_factory=list)
    reauth_blocked_until: datetime | None = None


_lock = threading.Lock()
_pairs: dict[tuple[str, str], _Pair] = {}
_accounts: dict[str, _Account] = {}


def reset() -> None:
    with _lock:
        _pairs.clear()
        _accounts.clear()


def pair_state(account_key: str, network: str) -> tuple[bool, bool]:
    """(blocked_now, captcha_required)."""
    now = clock.now()
    with _lock:
        pair = _pairs.get((account_key, network))
        if pair is None:
            return False, False
        blocked = pair.blocked_until is not None and pair.blocked_until > now
        return blocked, pair.failures >= PAIR_THRESHOLD


def record_password_failure(account_key: str, network: str) -> bool:
    """Returns True when this failure starts the per-(account, network) throttle."""
    now = clock.now()
    with _lock:
        pair = _pairs.setdefault((account_key, network), _Pair())
        pair.failures += 1
        if pair.failures >= PAIR_THRESHOLD:
            delay = min(MAX_PAIR_DELAY, timedelta(seconds=30 * 2 ** (pair.failures - PAIR_THRESHOLD)))
            pair.blocked_until = now + delay
        return pair.failures == PAIR_THRESHOLD


def record_password_success(account_key: str, network: str) -> None:
    with _lock:
        _pairs.pop((account_key, network), None)


def record_network_failure(user_id: str, network: str) -> int:
    """Returns the number of distinct failing networks in the window."""
    now = clock.now()
    with _lock:
        acct = _accounts.setdefault(user_id, _Account())
        acct.network_failures[network] = now
        acct.network_failures = {n: t for n, t in acct.network_failures.items() if now - t <= GLOBAL_WINDOW}
        return len(acct.network_failures)


def clear_account(user_id: str) -> None:
    with _lock:
        _accounts.pop(user_id, None)
        for key in [k for k in _pairs if k[0] == user_id]:
            _pairs.pop(key, None)


def mfa_blocked(user_id: str) -> datetime | None:
    now = clock.now()
    with _lock:
        acct = _accounts.get(user_id)
        if acct and acct.mfa_blocked_until and acct.mfa_blocked_until > now:
            return acct.mfa_blocked_until
        return None


def record_mfa_failure(user_id: str) -> bool:
    """Returns True when this failure starts an MFA throttle."""
    now = clock.now()
    with _lock:
        acct = _accounts.setdefault(user_id, _Account())
        acct.mfa_failures = [t for t in acct.mfa_failures if now - t <= MFA_WINDOW] + [now]
        if len(acct.mfa_failures) >= MFA_FAILURES:
            acct.mfa_blocked_until = now + MFA_THROTTLE
            acct.mfa_failures = []
            return True
        return False


def reauth_blocked(user_id: str) -> datetime | None:
    now = clock.now()
    with _lock:
        acct = _accounts.get(user_id)
        if acct and acct.reauth_blocked_until and acct.reauth_blocked_until > now:
            return acct.reauth_blocked_until
        return None


def record_reauth_failure(user_id: str) -> bool:
    """Returns True when this failure starts a re-authentication throttle."""
    now = clock.now()
    with _lock:
        acct = _accounts.setdefault(user_id, _Account())
        acct.reauth_failures = [t for t in acct.reauth_failures if now - t <= REAUTH_WINDOW] + [now]
        if len(acct.reauth_failures) >= REAUTH_FAILURES:
            acct.reauth_blocked_until = now + REAUTH_THROTTLE
            acct.reauth_failures = []
            return True
        return False
