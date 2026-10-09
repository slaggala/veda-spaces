"""The activation gate for customer specifications with room promises (final pre-activation closure, M1 and M2).

Every activation and every reactivation (rollback) of such a specification on a deployed environment runs the whole
gate; no earlier activation counts as standing approval. The gate reads only the reviewed records packaged with the
running release (`approved/`): the promise matrix, the sales decisions and the owner's approval record. It fails
closed when any of them is missing, incomplete, unapproved or stale against the stored specification, the active
rate card or the customer copy.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from . import customer_spec, promise_matrix

DEPLOYED = ("staging", "production")
DECISIONS = ("APPROVE", "CHANGE")
RELEASE_RE = re.compile(r"^[0-9a-f]{7,40}$")
REPO = Path(__file__).resolve().parents[4]  # the repository root, when running from a checkout
COPY_FILE = REPO / "app/e2e/site-release/assets/estimate-v2-copy.js"


def parse_copy(text: str) -> dict:
    """The V2 customer copy: `window.VEDA_ESTIMATE_COPY = Object.freeze(<JSON>);` (JSON, so Python can read it)."""
    start = text.index("Object.freeze(") + len("Object.freeze(")
    end = text.rindex(");")
    return json.loads(text[start:end])


def customer_copy() -> dict | None:
    """The V2 customer copy, when the repository is present (a checkout); the staging site build checks it otherwise."""
    return parse_copy(COPY_FILE.read_text()) if COPY_FILE.is_file() else None


def warranty_copy(copy: dict) -> dict:
    p = copy["promise"]
    return {"manufacturer": p["manufacturer"], "service": p["service"], "serviceNote": p["serviceNote"]}


def records(spec_code: str) -> dict:
    return {kind: promise_matrix.load(spec_code, kind) for kind in ("promise-matrix", "sales-decisions", "approval")}


def digests(spec_code: str) -> dict:
    """The digests an owner approval record must carry for the records packaged with this release."""
    r = records(spec_code)
    copy = customer_copy()
    return {
        "promise_matrix_sha256": promise_matrix.sha256(r["promise-matrix"]) if r["promise-matrix"] else None,
        "sales_decisions_sha256": promise_matrix.sha256(r["sales-decisions"]) if r["sales-decisions"] else None,
        "customer_copy_sha256": promise_matrix.sha256(copy) if copy else None,
        "warranty_copy_sha256": promise_matrix.sha256(warranty_copy(copy)) if copy else None,
    }


def repository_blockers(paths: list[Path]) -> list[str]:
    """In a checkout, the records must be tracked and unmodified (the reviewed commit, not a local edit)."""
    if not (REPO / ".git").exists():
        return []  # a release image: the files are the ones the image was built from
    out = []
    for p in paths:
        if not p.resolve().is_relative_to(REPO / "api/veda/modules/estimator/approved"):
            out.append(f"{p} is outside the approved repository path")
            continue
        rel = str(p.resolve().relative_to(REPO))
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel], cwd=REPO, capture_output=True)
        if tracked.returncode != 0:
            out.append(f"{rel} is not tracked in the repository")
            continue
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=REPO, capture_output=True)
        if clean.returncode != 0:
            out.append(f"{rel} differs from the committed version")
    return out


def repository_commit() -> str | None:
    if not (REPO / ".git").exists():
        return None
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True)
    return r.stdout.strip() or None


def sales_blockers(sales: dict | None, spec_code: str) -> list[str]:
    if sales is None:
        return ["no sales decision record is packaged for this specification"]
    out = []
    if sales.get("schema") != "veda.estimator.sales-decisions/1" or sales.get("spec_code") != spec_code:
        out.append("the sales decision record is not for this specification")
    for item in sales.get("items") or []:
        if item.get("owner_decision") not in DECISIONS:
            out.append(f"sales {item.get('id')}: no decision")
            continue
        if not str(item.get("owner_name") or "").strip() or not str(item.get("decision_date") or "").strip():
            out.append(f"sales {item.get('id')}: decision without a name and date")
        if item["owner_decision"] == "CHANGE":
            out.append(f"sales {item.get('id')}: CHANGE needs a new specification version and digest, not {spec_code}")
    if len(sales.get("items") or []) != 10:
        out.append("the sales decision record must hold the ten decisions")
    return out


def gate(
    document: dict, stored_sha256: str, *, env: str, active_card_sha256: str | None, approval_reference: str | None
) -> tuple[list[str], dict]:
    """(blockers, evidence) for activating or reactivating a specification with room promises on `env`."""
    spec = customer_spec.parse(document)
    code = spec.spec_code
    r = records(code)
    matrix, sales, approval = r["promise-matrix"], r["sales-decisions"], r["approval"]
    blocked: list[str] = []
    evidence: dict = {"spec": code, "specification_sha256": stored_sha256}
    # The reviewed records, as committed.
    blocked += repository_blockers([promise_matrix.path_for(code, k) for k in r if r[k] is not None])
    # The promise matrix: complete for this specification, every promise operationally confirmed.
    if matrix is None:
        blocked.append("no promise matrix is packaged for this specification")
    else:
        try:
            promise_matrix.validate(document, matrix)
            blocked += promise_matrix.blockers(matrix)
        except promise_matrix.MatrixError as err:
            blocked.append(f"matrix: {err}")
        evidence["promise_matrix_sha256"] = promise_matrix.sha256(matrix)
        evidence["operations_confirmation_version"] = matrix.get("version")
    blocked += sales_blockers(sales, code)
    if sales is not None:
        evidence["sales_decisions_sha256"] = promise_matrix.sha256(sales)
        evidence["sales_decisions_version"] = sales.get("version")
    # The owner's approval record: approved, in scope, and not stale.
    if approval is None:
        blocked.append("no owner approval record is packaged for this specification")
        return blocked, evidence
    evidence["approval_sha256"] = promise_matrix.sha256(approval)
    evidence["approval_version"] = approval.get("version")
    if approval.get("status") != "APPROVED":
        blocked.append(f"the owner approval record is {approval.get('status')}, not APPROVED")
    for field in ("owner", "approved_on", "approval_reference", "reviewed_commit"):
        if not str(approval.get(field) or "").strip():
            blocked.append(f"the owner approval record has no {field}")
    scope = approval.get("scope") or {}
    if env not in (scope.get("environments") or []) or scope.get("package") != spec.package:
        blocked.append(f"the approval does not cover {spec.package} on {env}")
    if scope.get("public_intake") is not False:
        blocked.append("the approval scope must exclude public intake")
    stale = [
        ("specification_sha256", stored_sha256),
        ("promise_matrix_sha256", evidence.get("promise_matrix_sha256")),
        ("sales_decisions_sha256", evidence.get("sales_decisions_sha256")),
    ]
    copy = customer_copy()
    if copy is not None:  # in a checkout; on a release image the staging site build checks the copy
        stale += [
            ("customer_copy_sha256", promise_matrix.sha256(copy)),
            ("warranty_copy_sha256", promise_matrix.sha256(warranty_copy(copy))),
        ]
    for field, current in stale:
        if not approval.get(field) or approval.get(field) != current:
            blocked.append(f"the approval's {field} does not match the release (stale or missing)")
    if matrix is not None and approval.get("operations_confirmation_version") != matrix.get("version"):
        blocked.append("the approval's operations_confirmation_version does not match the matrix")
    if sales is not None and approval.get("sales_decisions_version") != sales.get("version"):
        blocked.append("the approval's sales_decisions_version does not match the sales record")
    eq = approval.get("real_card_equivalence") or {}
    if eq.get("result") != "PASS" or not eq.get("card_sha256"):
        blocked.append("no passing real-card equivalence is recorded")
    elif eq.get("card_sha256") != active_card_sha256:
        blocked.append("the active rate card is not the card the equivalence was run on (stale)")
    if approval_reference is not None and approval_reference.strip() != str(approval.get("approval_reference") or ""):
        blocked.append("--approval does not match the approval record's approval_reference")
    return blocked, evidence
