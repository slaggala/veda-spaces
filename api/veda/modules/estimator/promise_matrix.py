"""The customer-promise matrix: every promise a customer can see, with its operational chain.

The reviewed matrix is packaged with the API (`approved/<spec code>-promise-matrix.json`), so each release carries the
matrix of the commit it was built from; activation never reads an operator-supplied file (final pre-activation
closure, M1). `validate` checks the structure (CI fails on it). `blockers` lists what still prevents activation: a row
not OPERATIONALLY_CONFIRMED, or without a named accountable owner, backup and confirmation date. `registered_text`
filters runtime text from the API (disclaimer, exclusions, client scope, assumptions) to what the matrix registers,
so unregistered wording never reaches V2 (M3). Nothing here infers an approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import customer_spec

SCHEMA = "veda.estimator.promise-matrix/3"
STATUSES = ("OPERATIONALLY_CONFIRMED", "SALES_CONFIRMED", "OWNER_CONFIRMED", "BLOCKED", "REMOVED")
READY = "OPERATIONALLY_CONFIRMED"  # the only status that satisfies activation (REMOVED rows are not shown)
CHAIN = (
    "source_of_truth",
    "responsible_role",
    "accountable_owner",
    "backup_owner",
    "quotation_mapping",
    "procurement_check",
    "receipt_check",
    "execution_check",
    "installation_check",
    "handover_evidence",
    "warranty_document_check",
    "warranty_source",
    "equivalent_rule",
    "exception_process",
    "wording",
    "status",
)
UNASSIGNED = "UNASSIGNED"
APPROVED_DIR = Path(__file__).resolve().parent / "approved"
# The matrix is internal text, but it is published with the code: it never states an amount or a rate (L1).
_AMOUNTS = re.compile(r"₹|\brs\.?\s*\d|\binr\b|\brupees?\b|\blakh|rate_minor|amount_minor|\bper sheet\b|\bper sq", re.I)


class MatrixError(ValueError):
    pass


def sha256(document: dict) -> str:
    """The canonical digest used for every approval record (the same as the specification digest)."""
    return hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def path_for(spec_code: str, kind: str = "promise-matrix") -> Path:
    return APPROVED_DIR / f"{spec_code.lower()}-{kind}.json"


def load(spec_code: str, kind: str = "promise-matrix") -> dict | None:
    """The packaged, reviewed record for a specification, or None when the release carries none."""
    p = path_for(spec_code, kind)
    return json.loads(p.read_text()) if p.is_file() else None


def visible(category: customer_spec.Category) -> set[str]:
    """Every statement a customer can read for a specification category."""
    out = [
        category.label,
        category.summary,
        category.requirement,
        category.grade,
        category.finish,
        *category.thickness,
        *category.brand_examples,
        category.equivalent_rule,
        category.final_selection,
        category.hardware_category,
        category.warranty_summary,
        *category.details,
        *category.phrases.values(),
    ]
    return {x for x in out if x}


def package_statements(spec: customer_spec.CustomerSpec) -> set[str]:
    return {spec.name, spec.summary, spec.equivalent_policy, spec.final_selection, spec.warranty_summary}


def validate(document: dict, matrix: dict) -> None:
    """Structure: the matrix covers exactly this specification's statements and every row carries the full chain."""
    spec = customer_spec.parse(document)
    problems: list[str] = []
    if matrix.get("schema") != SCHEMA:
        problems.append(f"schema must be {SCHEMA}")
    if not str(matrix.get("version") or "").strip():
        problems.append("the matrix needs a version")
    if matrix.get("spec_code") != spec.spec_code:
        problems.append(f"the matrix is for {matrix.get('spec_code')}, not {spec.spec_code}")
    if _AMOUNTS.search(json.dumps(matrix, ensure_ascii=False)):
        problems.append("the matrix states an amount or a rate")
    rows = matrix.get("rows") or []
    ids = [r.get("id") for r in rows]
    if len(set(ids)) != len(ids) or not all(ids):
        problems.append("row ids must be present and unique")
    by_category = {r.get("category"): r for r in rows if r.get("kind") == "category"}
    for c in spec.categories:
        row = by_category.get(c.code)
        if row is None:
            problems.append(f"category {c.code} has no row")
        elif set(row.get("statements") or []) != visible(c):
            problems.append(f"category {c.code}: the statements differ from the specification")
    if set(by_category) - {c.code for c in spec.categories}:
        problems.append("rows for categories the specification does not have")
    package = [r for r in rows if r.get("kind") == "package"]
    if len(package) != 1 or set(package[0].get("statements") or []) != package_statements(spec):
        problems.append("one package row must list the specification's package-level statements")
    for r in rows:
        missing = [f for f in CHAIN if not str(r.get(f) or "").strip()]
        if missing:
            problems.append(f"{r.get('id')}: missing {', '.join(missing)}")
        if "confirmed_on" not in r:
            problems.append(f"{r.get('id')}: missing confirmed_on (null until confirmed)")
        if r.get("status") not in STATUSES:
            problems.append(f"{r.get('id')}: status {r.get('status')!r} is not one of {', '.join(STATUSES)}")
        if r.get("status") == "BLOCKED" and not str(r.get("blocked_on") or "").strip():
            problems.append(f"{r.get('id')}: a BLOCKED row says what it waits for (blocked_on)")
        if not r.get("statements"):
            problems.append(f"{r.get('id')}: no statements")
    if problems:
        raise MatrixError("; ".join(problems))


def _named(value) -> bool:
    return str(value or "").strip() not in ("", UNASSIGNED)


def blockers(matrix: dict) -> list[str]:
    """What prevents activation: any shown row that is not operationally confirmed with named owners and a date."""
    out = []
    for r in matrix.get("rows") or []:
        if r.get("status") == "REMOVED":
            continue
        if r.get("status") != READY:
            out.append(f"{r['id']}: {r.get('status')} (waiting for {r.get('blocked_on') or 'operations confirmation'})")
            continue
        missing = [
            what
            for what, ok in (
                ("a named accountable owner", _named(r.get("accountable_owner"))),
                ("a named backup", _named(r.get("backup_owner"))),
                ("a confirmation date", bool(r.get("confirmed_on"))),
            )
            if not ok
        ]
        if missing:
            out.append(f"{r['id']}: missing {', '.join(missing)}")
    return out


def _template(statement: str) -> re.Pattern[str]:
    parts = re.split(r"\{\w+\}", statement)
    return re.compile("^" + ".+?".join(re.escape(p) for p in parts) + "$")


def registered_text(matrix: dict, view: dict, room_details: list[dict]) -> dict:
    """Runtime customer text, keeping only what the matrix registers (exact statements, or templates with {fields}).

    Unregistered text is suppressed, never shown: V2 renders the disclaimer, exclusions, client scope and assumptions
    from this block only.
    """
    rows = [r for r in matrix.get("rows") or [] if r.get("status") != "REMOVED"]
    exact = {t for r in rows for t in r.get("statements") or [] if "{" not in t}
    templates = [_template(t) for r in rows for t in r.get("statements") or [] if "{" in t]

    def ok(text: str) -> bool:
        return text in exact or any(t.match(text) for t in templates)

    suppressed = 0

    def keep(items):
        nonlocal suppressed
        kept = [x for x in items if ok(x)]
        suppressed += len(items) - len(kept)
        return kept

    disclaimer = view.get("disclaimer")
    if disclaimer and not ok(disclaimer):
        disclaimer, suppressed = None, suppressed + 1
    return {
        "approved": True,
        "matrix": {"spec_code": matrix.get("spec_code"), "version": matrix.get("version"), "sha256": sha256(matrix)},
        "disclaimer": disclaimer,
        "exclusions": keep(view.get("exclusions") or []),
        "client_scope": keep(view.get("client_scope") or []),
        "assumptions": {d["room"]: keep(d.get("assumptions") or []) for d in room_details},
        "suppressed": suppressed,
    }
