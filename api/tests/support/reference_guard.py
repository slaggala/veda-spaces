"""Fixture guard: no real-looking personal, contact, payment, tax or account data in test and fixture sources.

Policy: docs/engineering/reference-content-policy.md. The guard stores **nothing derived from any external or
reference document**: no value, no hash, no fingerprint. It recognises low-entropy sensitive data by its *structure*
(``rule_findings``): bank-account-like numbers in a banking context, bank branch codes, tax and company identifiers,
payment handles, mobile numbers and e-mail addresses. A clearly synthetic form is always allowed (``synthetic``): two or
fewer distinct digits, the synthetic namespaces (``ZZZZ0…`` branch codes, identifiers containing ``ZZZ``, handles
starting ``synthetic`` or ``test``), and reserved e-mail domains (``example.com/.net/.org``, ``*.example``, ``*.test``,
``*.invalid``, ``*.localhost``) or Veda Spaces' own. Applied to test and fixture sources with a counts-only ratchet
(``tests/support/fixture_rules_baseline.json``): a new real-looking value fails.

Copied wording from a reference document is prevented by policy, code review, the synthetic-fixture rule and the
customer-copy governance (``mtq_commercial.customer_pack``), not by stored signatures of that document.
"""

from __future__ import annotations

import re

# --- structural rules (shape, never a value) ------------------------------------------------------------------------------
BANK_CONTEXT = re.compile(r"\b(account|a/c|acct|ifsc|bank|upi|neft|rtgs|imps)\b", re.I)
RULES: dict[str, re.Pattern[str]] = {
    "bank-account-like number": re.compile(r"(?<![\w.-])\d{9,18}(?![\w.-])"),
    "bank branch code": re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
    "tax or company identifier": re.compile(
        r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b|\b[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]\b|\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b"
    ),
    "payment handle": re.compile(
        r"\b[\w.-]{2,}@(?:ok)?(?:hdfcbank|hdfc|icici|axisbank|axis|sbi|ybl|paytm|upi|ibl|apl|kotak|yesbank|indus|federal|"
        r"idfcbank|pnb|aubank|freecharge|barodampay)\b",
        re.I,
    ),
    "mobile number": re.compile(r"(?<![\w.+])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w.])"),
    "e-mail address": re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),
}
RESERVED_MAIL = re.compile(
    r"@(?:[\w-]+\.)*(?:example\.(?:com|net|org)|example|test|invalid|localhost)$|@(?:[\w-]+\.)*vedaspaces\.(?:com|in)$",
    re.I,
)


def synthetic(category: str, value: str) -> bool:
    """A value in a clearly synthetic form, always allowed in fixtures."""
    digits = re.sub(r"\D", "", value)
    if category in ("bank-account-like number", "mobile number"):
        return len(set(digits)) <= 2
    if category == "bank branch code":
        return value.upper().startswith("ZZZZ0")
    if category == "tax or company identifier":
        return "ZZZ" in value.upper()
    if category == "payment handle":
        return value.lower().startswith(("synthetic", "test"))
    if category == "e-mail address":
        return bool(RESERVED_MAIL.search(value))
    return False


def rule_findings(text: str) -> list[str]:
    """Each real-looking low-entropy sensitive value's line N: category (the value itself is never returned)."""
    out: list[str] = []
    for n, line in enumerate(text.splitlines(), start=1):
        for category, rx in RULES.items():
            if category == "bank-account-like number" and not BANK_CONTEXT.search(line):
                continue  # long numbers elsewhere are run ids, timestamps, digests
            for m in rx.finditer(line):
                if not synthetic(category, m.group(0)):
                    out.append(f"line {n}: {category}")
    return out
