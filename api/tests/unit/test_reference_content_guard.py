"""Fixture guard (docs/engineering/reference-content-policy.md): no real-looking personal, contact, payment, tax or
account data in test and fixture sources, and nothing derived from any external document stored to look for it.

The guard (tests.support.reference_guard) is structural only: it recognises bank-account-like numbers, branch codes,
tax and company identifiers, payment handles, mobile numbers and e-mail addresses by their shape, allows clearly
synthetic forms, and holds a counts-only ratchet for values already on main. Every probe below is synthetic and built
at run time, so no real-looking literal sits in this file.
"""

from __future__ import annotations

import collections
import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.support import reference_guard as g

REPO = Path(__file__).resolve().parents[3]
BINARY = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".ico", ".gif", ".pdf", ".woff", ".woff2", ".ttf", ".zip", ".gz")
FIXTURE_SCOPE = re.compile(r"^(api/tests/|app/test/|app/e2e/|api/veda/.*/fixtures/|infra/.*/fixtures/)")
SELF = {"api/tests/support/reference_guard.py", "api/tests/unit/test_reference_content_guard.py",
        "api/tests/support/fixture_rules_baseline.json"}  # fmt: skip
BASELINE = REPO / "api/tests/support/fixture_rules_baseline.json"


def fixture_files() -> dict[str, str]:
    names = subprocess.run(["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard"], capture_output=True,
                           text=True, check=True).stdout.split("\n")  # fmt: skip
    out = {}
    for name in names:
        p = REPO / name
        if not FIXTURE_SCOPE.match(name) or name in SELF or name.endswith(BINARY) or not p.is_file():
            continue
        try:
            out[name] = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return out


def _digits(seed: str, n: int) -> str:
    """A synthetic digit string (derived at run time, never typed) with enough distinct digits to look real."""
    return "".join(str((int(c) * 7 + i) % 10) for i, c in enumerate((seed * n)[:n]))


@pytest.mark.parametrize("category,line", [
    ("bank-account-like number", lambda: f"Bank account {_digits('31415', 14)} (synthetic probe)"),
    ("bank branch code", lambda: "IFSC " + "ABCD" + "0" + _digits("1234", 6)),
    ("mobile number", lambda: f"Call {'9'}{_digits('2718', 4)} {_digits('1618', 5)}"),
    ("tax or company identifier", lambda: "GSTIN 27" + "ABCDE" + _digits("1234", 4) + "F1Z" + "5"),
    ("payment handle", lambda: "Pay probe.person@" + "oksbi"),
    ("e-mail address", lambda: "Personal mail: probe.person@" + "mailbox" + ".com"),
    ("e-mail address", lambda: "Customer contact: Probe Person, probe.person@" + "inbox" + ".in"),
])  # fmt: skip
def test_structural_rules_catch_synthetic_sensitive_shapes(category, line):
    found = g.rule_findings(line())
    assert [f.split(": ", 1)[1] for f in found] == [category]
    assert all(re.fullmatch(r"line \d+: [a-z -]+", f) for f in found)  # a finding never carries the value


def test_a_customer_contact_block_is_caught_line_by_line():
    block = "\n".join(["Customer: Probe Person", f"Mobile: +91 {'8'}{_digits('5772', 4)} {_digits('1414', 5)}",
                       "Mail: probe.person@" + "mailbox" + ".com"])  # fmt: skip
    assert [f.split(": ", 1) for f in g.rule_findings(block)] == [
        ["line 2", "mobile number"],
        ["line 3", "e-mail address"],
    ]


@pytest.mark.parametrize("text", [
    "Account 00000000000000", "Call +00 00000 00001", "Call 9999999999", "Pay to ZZZZ0SYN001", "Pay synthetic@okexample",
    "GSTIN 27ZZZZZ0000Z1Z5", "Write to someone@example.com or desk@synthetic.example or a@b.test or x@y.invalid",
    "support@vedaspaces.com", "Run 38703925298 finished", "Digest 1792005347706 recorded",
])  # fmt: skip
def test_synthetic_fixtures_pass(text):
    assert g.rule_findings(text) == []


@pytest.mark.parametrize("text", [
    "Wardrobe with laminate shutters, soft-close hinges, a loft and BWR plywood carcass; GST included.",
    "Veda Spaces: interiors, measured and made. Site readiness, handover, warranty and care guidance.",
    "3 BHK apartment: kitchen base units 12.5 running ft, false ceiling 220 sq ft, 18 mm boards.",
    "What happens after you approve: Veda confirmation, scope and design finalisation, installation, joint inspection.",
])  # fmt: skip
def test_legitimate_veda_and_interior_terminology_passes(text):
    assert g.rule_findings(text) == []


def test_the_guard_stores_nothing_derived_from_an_external_document():
    source = Path(g.__file__).read_text(encoding="utf-8")
    # no hashing, no fingerprint table, no salt, no stored digest: nothing to compare a document against
    assert not re.search(r"import hashlib|hashlib\.|sha256\(|FINGERPRINTS|SALT\s*=|[0-9a-f]{20,}", source)
    assert not re.search(r"\d{9,}", source)  # no stored number of any kind


def test_fixture_sources_add_no_real_looking_low_entropy_value():
    """A counts-only ratchet: real-looking values that test and fixture sources on main already held before the guard
    are counted (never stored); a new one, in a new file or a higher count, fails. New fixtures use synthetic forms."""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))["counts"]
    current: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for name, text in fixture_files().items():
        for f in g.rule_findings(text):
            current[f.split(": ", 1)[1]][name] += 1
    over = [f"{name}: {n} {category} value(s), {baseline.get(category, {}).get(name, 0)} allowed — use a synthetic form"
            for category, per_file in current.items() for name, n in per_file.items()
            if n > baseline.get(category, {}).get(name, 0)]  # fmt: skip
    assert not over, over
    assert all(isinstance(n, int) for per in baseline.values() for n in per.values())  # counts only, never values
