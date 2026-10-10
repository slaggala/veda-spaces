"""Synthetic claim governance for tests: role placeholders, never people; references that are not placeholders."""

from veda.modules.catalog import text


def governance(statement: str, **over) -> dict:
    """Approved, complete claim governance for `statement`, with the categories detected in it and its digest."""
    cats = text.marketing_claims_in(statement)
    doc = {
        "categories": cats or ["popularity"], "status": "APPROVED",
        "source": "Order data export 2026-Q3 (synthetic)", "evidence_reference": "Synthetic sales dataset 2026-Q3 v1",
        "evidence_period": "2026-07-01 to 2026-09-30", "owner": "Sales lead (role, test)",
        "backup_owner": "Marketing lead (role, test)", "approver": "Compliance lead (role, test)",
        "approved_on": "2026-09-30", "effective_from": "2026-10-01", "review_by": "2027-03-31", "environments": ["test"],
        "canonical_sha256": text.canonical_digest(statement),
    }  # fmt: skip
    if text.absolute_in(statement) or set(cats) & {"ranking", "price"}:
        doc["substantiation"] = "Independent survey report 2026 (synthetic)"
    doc.update(over)
    return {k: v for k, v in doc.items() if v is not None}


def claim_copy(statement: str, *, category: str = "badge", packages=("slice.essential",), **over) -> dict:
    return {"statement": statement, "category": category, "promise": False, "claim": governance(statement, **over),
            "applies_to": {"packages": list(packages)}, "content_policy": "GOVERNED_CLAIM_REFERENCE"}  # fmt: skip
