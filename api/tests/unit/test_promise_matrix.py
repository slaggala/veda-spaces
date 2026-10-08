"""Trust finalisation, Phases 4 and 12: every visible specification statement has an operational chain.

The customer-promise matrix (docs/implementation/estimator/specifications/essential-1.1-promise-matrix.json) must list
exactly the statements the specification shows, category by category, each with its quotation mapping, procurement,
execution and handover checks, warranty source and accountable role. Changing a customer statement therefore fails
here until the matrix, and the operational chain behind it, is reviewed.
"""

import json
from pathlib import Path

import pytest

from veda.modules.estimator import customer_spec

SPECS = Path(__file__).resolve().parents[3] / "docs/implementation/estimator/specifications"
SPEC = json.loads((SPECS / "essential-specification-v1.1.json").read_text())
MATRIX = json.loads((SPECS / "essential-1.1-promise-matrix.json").read_text())
CHAIN = (
    "customer_wording",
    "internal_requirement",
    "equivalent_rule",
    "quotation_mapping",
    "procurement_verification",
    "execution_verification",
    "handover_evidence",
    "warranty_source",
    "accountable_role",
    "status",
)


def visible(c) -> set[str]:
    out = [c.label, c.summary, c.requirement, c.grade, c.finish, *c.thickness, *c.brand_examples, c.equivalent_rule,
           c.final_selection, c.hardware_category, c.warranty_summary, *c.details, *c.phrases.values()]  # fmt: skip
    return {x for x in out if x}


def test_the_matrix_covers_the_specification_category_by_category():
    spec = customer_spec.parse(SPEC)
    assert MATRIX["spec_code"] == spec.spec_code
    assert [r["code"] for r in MATRIX["categories"]] == [c.code for c in spec.categories]
    package = {spec.name, spec.summary, spec.equivalent_policy, spec.final_selection, spec.warranty_summary}
    assert set(MATRIX["package"]["statements"]) == package


@pytest.mark.parametrize("code", [c["code"] for c in SPEC["categories"]])
def test_every_visible_statement_has_an_operational_chain(code):
    category = next(c for c in customer_spec.parse(SPEC).categories if c.code == code)
    row = next(r for r in MATRIX["categories"] if r["code"] == code)
    assert set(row["statements"]) == visible(category), "update the matrix when a customer statement changes"
    assert all(row[field] for field in CHAIN), f"{code}: every link of the chain is filled in"
    assert row["brand_examples"] == list(category.brand_examples)


def test_the_matrix_holds_no_amounts():
    text = json.dumps(MATRIX, ensure_ascii=False)
    assert "₹" not in text and "rate_minor" not in text and "per sheet" not in text
