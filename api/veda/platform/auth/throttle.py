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

Layered bounds on distributed guessing (RR-04; proposed amendment AM-7, revised). They apply to every
identifier — account holders with or without a factor, and addresses with no account — and never lock
anyone out, so they cannot be used to deny a victim sign-in:

* Account budget, across all networks: after 10 failures in 15 minutes every attempt for the identifier
  needs a Turnstile token (challenge escalation); after 20, attempts are also spaced by an escalating
  minimum interval (2 s doubling to 30 s) answered with 429 + Retry-After. A successful password does
  not reset the budget (the attacker's failures only decay with the window), so a victim signing in
  does not reopen the account to guessing.
* Aggregate: 200 failures across all identifiers in 5 minutes require Turnstile for every sign-in until
  the window drains (credential stuffing from many networks against many accounts).
* Reset emails: at most 3 per account per hour across all networks; further requests are answered
  identically and send nothing.

Identifiers are the user id or an HMAC of the normalized email (never the raw address). Tracked keys are
capped (``MAX_TRACKED``): expired entries are pruned first, then the oldest; a flood of fresh identifiers
large enough to evict entries also trips the aggregate escalation.

The per-network state is in-process and authoritative because exactly one
application process runs (OPS-010, F-09).
"""

from __future__ import annotations

import threading
from collections import deque
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
ACCOUNT_WINDOW = timedelta(minutes=15)
ACCOUNT_CAPTCHA_FAILURES = 10
ACCOUNT_DELAY_FAILURES = 20
ACCOUNT_MIN_INTERVAL = timedelta(seconds=2)
ACCOUNT_MAX_INTERVAL = timedelta(seconds=30)
AGGREGATE_WINDOW = timedelta(minutes=5)
AGGREGATE_CAPTCHA_FAILURES = 200
RESET_EMAILS = 3
RESET_WINDOW = timedelta(hours=1)
MAX_TRACKED = 50_000


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


@dataclass
class _Budget:
    failures: deque = field(default_factory=deque)
    last_failure: datetime | None = None


_lock = threading.Lock()
_pairs: dict[tuple[str, str], _Pair] = {}
_accounts: dict[str, _Account] = {}
_budgets: dict[str, _Budget] = {}
_aggregate: deque = deque(maxlen=AGGREGATE_CAPTCHA_FAILURES)
_reset_emails: dict[str, deque] = {}


def reset() -> None:
    with _lock:
        _pairs.clear()
        _accounts.clear()
        _budgets.clear()
        _aggregate.clear()
        _reset_emails.clear()


def _bound(table: dict, stale) -> None:
    """Keep ``table`` at most MAX_TRACKED entries: drop stale entries, then the oldest (insertion order)."""
    if len(table) <= MAX_TRACKED:
        return
    for key in [k for k, v in table.items() if stale(v)]:
        table.pop(key, None)
    while len(table) > MAX_TRACKED:
        table.pop(next(iter(table)))


def _trim(q: deque, now: datetime, window: timedelta) -> None:
    while q and now - q[0] > window:
        q.popleft()


def account_state(account_key: str) -> tuple[bool, int | None]:
    """(captcha_required, retry_after_seconds) from the cross-network budget and the aggregate bound."""
    now = clock.now()
    with _lock:
        captcha = len(_aggregate) >= AGGREGATE_CAPTCHA_FAILURES and now - _aggregate[0] <= AGGREGATE_WINDOW
        budget = _budgets.get(account_key)
        if budget is None:
            return captcha, None
        _trim(budget.failures, now, ACCOUNT_WINDOW)
        n = len(budget.failures)
        captcha = captcha or n >= ACCOUNT_CAPTCHA_FAILURES
        if n >= ACCOUNT_DELAY_FAILURES and budget.last_failure is not None:
            step = min(n - ACCOUNT_DELAY_FAILURES, 8)  # 2 s, 4 s, … capped at ACCOUNT_MAX_INTERVAL
            interval = min(ACCOUNT_MAX_INTERVAL, ACCOUNT_MIN_INTERVAL * 2**step)
            wait = budget.last_failure + interval - now
            if wait.total_seconds() > 0:
                return captcha, max(1, int(wait.total_seconds() + 0.999))
        return captcha, None


def record_account_failure(account_key: str) -> int:
    """Count a failed password attempt against the identifier's budget and the aggregate; returns the count."""
    now = clock.now()
    with _lock:
        budget = _budgets.pop(account_key, None) or _Budget()
        _bound(_budgets, lambda b: b.last_failure is None or now - b.last_failure > ACCOUNT_WINDOW)
        _budgets[account_key] = budget  # re-inserted: insertion order is recency order for eviction
        _trim(budget.failures, now, ACCOUNT_WINDOW)
        budget.failures.append(now)
        budget.last_failure = now
        _aggregate.append(now)
        return len(budget.failures)


def reset_email_allowed(user_id: str) -> bool:
    """At most RESET_EMAILS reset emails per account per RESET_WINDOW, whatever the requesting network."""
    now = clock.now()
    with _lock:
        sent = _reset_emails.pop(user_id, None) or deque()
        _bound(_reset_emails, lambda q: not q or now - q[-1] > RESET_WINDOW)
        _reset_emails[user_id] = sent
        _trim(sent, now, RESET_WINDOW)
        if len(sent) >= RESET_EMAILS:
            return False
        sent.append(now)
        return True


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
        _bound(_pairs, lambda p: p.blocked_until is None or now - p.blocked_until > MAX_PAIR_DELAY)
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
        _bound(_accounts, lambda a: not a.network_failures and not a.mfa_failures and not a.reauth_failures)
        acct = _accounts.setdefault(user_id, _Account())
        acct.network_failures[network] = now
        acct.network_failures = {n: t for n, t in acct.network_failures.items() if now - t <= GLOBAL_WINDOW}
        return len(acct.network_failures)


def clear_account(user_id: str) -> None:
    """Administrative unlock and password reset: the account's own throttles and budget end."""
    with _lock:
        _accounts.pop(user_id, None)
        _budgets.pop(user_id, None)
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
