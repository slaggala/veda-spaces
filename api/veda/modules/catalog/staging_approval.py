"""The V3 staging approval record (targeted media enablement, Phase 11; activation remediation).

`api/veda/modules/catalog/approved/v3-staging-approval.json` is the owner's record that V3 may be activated on protected
staging. It references by digest every piece of evidence the activation rests on. It does not itself enable anything.

The rules are defined once, in `v3_approval_policy.json` next to this module. Four gates apply them:
- the Terraform plan (infra/terraform/modules/v3-approval);
- the staging build (app/scripts/v3-approval.mjs);
- the deployment check (deploy.sh runs this module);
- the runtime, on every public V3 request and every media operation on staging (configure.require_staging_approval).

Each gate reports the failing rule codes in the policy's order. The shared conformance cases in
api/tests/fixtures/v3_approval/cases.json prove that the three implementations decide every case identically.

No record is committed until the owner approves one: the template in docs/implementation/catalog/ is DRAFT with empty
evidence, and no owner value or date is ever filled in automatically.

    python -m veda.modules.catalog.staging_approval [record.json]
    # exit 0 only for a current APPROVED record bound by VEDA_CATALOG_APPROVAL_SHA256
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import UTC, date, timedelta
from pathlib import Path
from typing import Any

RECORD = Path(__file__).resolve().parent / "approved" / "v3-staging-approval.json"
POLICY_FILE = Path(__file__).resolve().parent / "v3_approval_policy.json"
POLICY: dict[str, Any] = json.loads(POLICY_FILE.read_text())

SCHEMA: str = POLICY["schema"]
MAX_REVIEW_DAYS: int = POLICY["max_review_days"]
GIT_EVIDENCE: tuple[str, ...] = tuple(POLICY["git_evidence"])
DIGEST_EVIDENCE: tuple[str, ...] = tuple(POLICY["digest_evidence"])
REQUIRED_EVIDENCE = (*GIT_EVIDENCE, *DIGEST_EVIDENCE)
CODES: tuple[str, ...] = tuple(c["code"] for c in POLICY["codes"])
MESSAGES: dict[str, str] = {c["code"]: c["message"] for c in POLICY["codes"]}

_SPACE = re.compile(r"[ \t\r\n]+")
_EDGE = re.compile(r"^[ \t\r\n]+|[ \t\r\n]+$")


def _match(pattern: str, value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None  # no trailing-newline match


def _date(value: object) -> date | None:
    if not _match(POLICY["date_pattern"], value):
        return None
    try:
        return date.fromisoformat(value)  # type: ignore[arg-type]
    except ValueError:
        return None


def _trim(value: str) -> str:
    return _EDGE.sub("", value)


def _norm(value: object) -> str | None:
    return _SPACE.sub(" ", _trim(value)).lower() if isinstance(value, str) else None


def read(path: Path = RECORD) -> bytes | None:
    """The record file's bytes, or None when there is none to read."""
    try:
        return path.read_bytes()
    except OSError:
        return None


def evaluate(raw: bytes | None, *, today: date, bound_sha256: object, release: str | None = None) -> list[str]:
    """The failing rule codes, in policy order (empty: the record authorises V3 on protected staging today).

    `raw` is the record file's bytes; `bound_sha256` is the digest the record must have; `release`, when given, is the
    active catalog release's code (runtime routes that serve the active release)."""
    if raw is None:
        return ["NO_RECORD"]
    try:
        doc = json.loads(raw)
    except ValueError:
        doc = None
    if not isinstance(doc, dict):
        return ["MALFORMED"]
    failing: set[str] = set()
    get = doc.get

    if get("schema") != SCHEMA:
        failing.add("SCHEMA")
    if get("status") != POLICY["approved_status"]:
        failing.add("STATUS")
    if get("environment") != POLICY["environment"]:
        failing.add("ENVIRONMENT")
    if not _match(POLICY["release_pattern"], get("release")):
        failing.add("RELEASE")

    scope = get("approval_scope")
    if not (
        isinstance(scope, dict)
        and all(scope.get(k) is v if isinstance(v, bool) else scope.get(k) == v for k, v in POLICY["scope"].items())
        and isinstance(scope.get("media_delivery"), bool)
    ):
        failing.add("SCOPE")

    if (
        get("status") == POLICY["revoked_status"]
        or get("revoked_at") is not None
        or get("revocation_reason") is not None
    ):
        failing.add("REVOKED")

    names = (get("approver"), get("author"))
    approver, author = _norm(names[0]), _norm(names[1])
    placeholder = POLICY["placeholder"].upper()
    if not approver or not author or approver == author or any(placeholder in str(n).upper() for n in names):
        failing.add("APPROVER")

    approved = _date(get("approved_at"))
    if approved is None:
        failing.add("APPROVAL_DATE")
    elif approved > today:
        failing.add("APPROVAL_IN_FUTURE")

    review = _date(get("review_by"))
    if review is None or (
        approved is not None and not (approved < review <= approved + timedelta(days=MAX_REVIEW_DAYS))
    ):
        failing.add("REVIEW_WINDOW")
    if review is not None and review <= today:
        failing.add("REVIEW_REACHED")

    has_expiry, has_decision = get("expires_at") is not None, get("non_expiring_decision") is not None
    expires = _date(get("expires_at"))
    decision = get("non_expiring_decision")
    if (
        has_expiry == has_decision
        or (has_expiry and (expires is None or (approved is not None and expires <= approved)))
        or (
            has_decision
            and not (isinstance(decision, str) and len(_trim(decision)) >= POLICY["non_expiring_min_length"])
        )
    ):
        failing.add("EXPIRY_POLICY")
    if expires is not None and expires <= today:
        failing.add("EXPIRED")

    if not _evidence_ok(get("evidence")):
        failing.add("EVIDENCE")

    if not (_match(POLICY["sha256_pattern"], bound_sha256) and bound_sha256 == hashlib.sha256(raw).hexdigest()):
        failing.add("DIGEST_MISMATCH")

    if release is not None and get("release") != release:
        failing.add("RELEASE_MISMATCH")

    return [c for c in CODES if c in failing]


def _evidence_ok(evidence: object) -> bool:
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_EVIDENCE):
        return False
    for key, value in evidence.items():
        if not isinstance(value, dict):
            return False
        ref = value.get("reference")
        if not (isinstance(ref, str) and len(_trim(ref)) >= POLICY["reference_min_length"]):
            return False
        field, pattern = ("git_sha", "git_sha_pattern") if key in GIT_EVIDENCE else ("sha256", "sha256_pattern")
        if not _match(POLICY[pattern], value.get(field)):
            return False
    return True


def today() -> date:
    """The current UTC date: the same day the plan (plantimestamp) and the build (UTC) judge by."""
    from veda.kernel import clock

    return clock.now().astimezone(UTC).date()


def messages(codes: list[str]) -> list[str]:
    return [MESSAGES[c] for c in codes]


def main(argv: list[str]) -> int:
    """The deployment check: the packaged record against the digest rendered from SSM (VEDA_CATALOG_APPROVAL_SHA256)."""
    from veda.config import settings

    path = Path(argv[1]) if len(argv) > 1 else RECORD
    codes = evaluate(read(path), today=today(), bound_sha256=settings().catalog_approval_sha256)
    if codes:
        print(f"refused: {'; '.join(f'{c}: {m}' for c, m in zip(codes, messages(codes), strict=True))}")
        return 1
    print("APPROVED and current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
