"""The customer-promise matrix (pre-activation closure): every promise a customer can see, with its operational chain.

`validate` checks the structure (always required: CI fails on it); `blockers` lists what still prevents activation of
the specification on a deployed environment: any row that is not confirmed by sales, operations or the owner, or has
no named accountable owner. Nothing here infers an approval: statuses are written by people, in the reviewed file.
"""

from __future__ import annotations

from . import customer_spec

SCHEMA = "veda.estimator.promise-matrix/2"
STATUSES = ("OPERATIONALLY_CONFIRMED", "SALES_CONFIRMED", "OWNER_CONFIRMED", "BLOCKED", "REMOVED")
CONFIRMED = frozenset(STATUSES[:3])
CHAIN = (
    "source_of_truth",
    "responsible_role",
    "accountable_owner",
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
    "status",
)
UNASSIGNED = "UNASSIGNED"


class MatrixError(ValueError):
    pass


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
    if matrix.get("spec_code") != spec.spec_code:
        problems.append(f"the matrix is for {matrix.get('spec_code')}, not {spec.spec_code}")
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
        if r.get("status") not in STATUSES:
            problems.append(f"{r.get('id')}: status {r.get('status')!r} is not one of {', '.join(STATUSES)}")
        if r.get("status") == "BLOCKED" and not str(r.get("blocked_on") or "").strip():
            problems.append(f"{r.get('id')}: a BLOCKED row says what it waits for (blocked_on)")
        if not r.get("statements"):
            problems.append(f"{r.get('id')}: no statements")
    if problems:
        raise MatrixError("; ".join(problems))


def blockers(matrix: dict) -> list[str]:
    """What prevents activation: unconfirmed rows and rows without a named accountable owner (REMOVED rows aside)."""
    out = []
    for r in matrix.get("rows") or []:
        if r.get("status") == "REMOVED":
            continue
        if r.get("status") not in CONFIRMED:
            out.append(f"{r['id']}: {r.get('status')} (waiting for {r.get('blocked_on') or 'confirmation'})")
        elif str(r.get("accountable_owner") or "").strip() in ("", UNASSIGNED):
            out.append(f"{r['id']}: no named accountable owner")
    return out
