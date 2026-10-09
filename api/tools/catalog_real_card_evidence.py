"""Owner-run real-card evidence for V2/V3 equivalence (canonical customer-copy closure, Phase 11).

The owner runs this on their own machine, where the private rate card lives outside the repository:

    .venv/bin/python tools/catalog_real_card_evidence.py \\
        --card ~/veda-private/<path>/rate-card.json --expected-sha256 <fingerprint> --operator "<role or name>"

What it does:
1. Refuses a card inside the repository and a card whose canonical fingerprint is not the expected one. The card is
   read in place and never copied.
2. Runs tests/integration/test_catalog_real_card.py on SQLite and on PostgreSQL, with every test's output discarded.
   Those tests assert equality and print no amount.
3. Writes one JSON artifact (mode 0600) to the private evidence directory (default ~/veda-private/evidence).

The artifact holds only these fields: card fingerprint, commit SHA, engines, scenario IDs with their outcomes,
equality result, timestamp and operator, plus `artifact_sha256`, the SHA-256 of the canonical JSON of those fields.
It contains no rate, no amount and no card content, so it is also the sanitised copy a reviewer may be given.

Not independent verification: the artifact records what the operator ran. Without an artifact, nobody may claim that
the real-card equivalence was verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess  # nosec B404 - runs this repository's own test suite and git, with fixed arguments
import sys
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 - parses the junit file pytest just wrote, not untrusted input
from datetime import UTC, datetime
from pathlib import Path

API = Path(__file__).resolve().parents[1]
REPO = API.parent
TESTS = "tests/integration/test_catalog_real_card.py"
FIELDS = ("card_fingerprint_sha256", "commit_sha", "engines", "scenarios", "equality", "timestamp", "operator")
ENGINES = ("sqlite", "postgresql")


def fingerprint(path: Path) -> str:
    """The canonical SHA-256 of the card document (sorted keys, no whitespace), as the tests compute it."""
    doc = json.loads(path.read_bytes())
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def commit() -> str:
    run = lambda *a: subprocess.run(["git", *a], cwd=REPO, capture_output=True, text=True, check=True).stdout  # noqa: E731  # nosec B603 B607
    sha = run("rev-parse", "HEAD").strip()
    return sha + ("-dirty" if run("status", "--porcelain", "--untracked-files=no").strip() else "")


def run_engine(engine: str, card: Path, expected: str) -> list[dict]:
    """The scenario IDs and outcomes of the real-card tests on one engine (test output discarded)."""
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        env = {**os.environ, "VEDA_PRIVATE_CARD": str(card), "VEDA_PRIVATE_CARD_SHA256": expected,
               "VEDA_TEST_ENGINES": engine}  # fmt: skip
        subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:randomly", "-p", "no:cacheprovider",
                        f"--junitxml={junit}", TESTS], cwd=API, env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)  # fmt: skip  # nosec B603
        if not junit.exists():
            return [{"id": f"{TESTS}::collection", "engine": engine, "outcome": "error"}]
        out = []
        for case in ET.parse(junit).getroot().iter("testcase"):  # nosec B314 - our own pytest output
            name = case.get("name", "")
            if not re.fullmatch(r"[A-Za-z0-9_\[\]\-]+", name):
                name = "unnamed"
            outcome = "passed"
            for tag in ("failure", "error", "skipped"):
                if case.find(tag) is not None:
                    outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[tag]
            out.append({"id": f"{TESTS}::{name}", "engine": engine, "outcome": outcome})
        return out


def artifact(fields: dict) -> dict:
    body = {k: fields[k] for k in FIELDS}
    body["artifact_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return body


def verify(doc: dict) -> bool:
    """True when an artifact holds only the allowed fields and its hash is intact (for the reviewer)."""
    if set(doc) != {*FIELDS, "artifact_sha256"}:
        return False
    return artifact(doc)["artifact_sha256"] == doc["artifact_sha256"]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--card", type=Path, help="the private card, outside the repository (read in place)")
    p.add_argument("--expected-sha256", help="the card's known canonical fingerprint")
    p.add_argument("--operator", help="who ran it (a role or the owner's name, entered by the operator)")
    p.add_argument("--out-dir", type=Path, default=Path("~/veda-private/evidence"))
    p.add_argument("--engines", default=",".join(ENGINES))
    p.add_argument("--verify", type=Path, help="check an existing artifact's fields and hash, and exit")
    a = p.parse_args(argv)
    if a.verify:
        ok = verify(json.loads(a.verify.read_text()))
        print("artifact intact" if ok else "artifact NOT intact or has extra fields")
        return 0 if ok else 1
    if not (a.card and a.expected_sha256 and a.operator):
        p.error("--card, --expected-sha256 and --operator are required")
    card = a.card.expanduser().resolve()
    if REPO == card or REPO in card.parents:
        print("refused: the card must stay outside the repository", file=sys.stderr)
        return 2
    if not re.fullmatch(r"[0-9a-f]{64}", a.expected_sha256):
        print("refused: --expected-sha256 is a 64-character lowercase hex fingerprint", file=sys.stderr)
        return 2
    found = fingerprint(card)
    if found != a.expected_sha256:
        print("refused: the card's fingerprint is not the expected one", file=sys.stderr)
        return 2
    engines = [e for e in a.engines.split(",") if e in ENGINES]
    scenarios = [s for e in engines for s in run_engine(e, card, found)]
    ran = [s for s in scenarios if s["outcome"] != "skipped"]
    equality = (
        "PASS"
        if ran and all(s["outcome"] == "passed" for s in ran) and {s["engine"] for s in ran} == set(engines)
        else "FAIL"
    )
    doc = artifact({"card_fingerprint_sha256": found, "commit_sha": commit(), "engines": engines, "scenarios": scenarios,
                    "equality": equality, "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
                    "operator": a.operator.strip()[:80]})  # fmt: skip
    out_dir = a.out_dir.expanduser().resolve()
    if REPO == out_dir or REPO in out_dir.parents:
        print("refused: evidence is kept outside the repository", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"real-card-evidence-{doc['timestamp'].replace(':', '')}.json"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as fh:
        json.dump(doc, fh, indent=2, sort_keys=True)
    print(
        f"{equality}: {len(ran)} scenario runs on {', '.join(engines)}; artifact {path} ({doc['artifact_sha256'][:12]}…)"
    )
    return 0 if equality == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
