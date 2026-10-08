"""Pre-activation closure: the customer-promise matrix covers every visible promise with its operational chain.

The matrix (docs/implementation/estimator/specifications/essential-1.1-promise-matrix.json) must list exactly the
statements the specification shows, category by category, and every row must carry the full chain: source of truth,
responsible role, accountable owner, quotation mapping, procurement, receipt, execution, installation, handover,
warranty-document and warranty source, the equivalent rule, the exception process and a status. Activation is blocked
until every row is confirmed by sales, operations or the owner with a named owner; nothing here infers an approval.
The page side (every V2 promise is in the matrix and vice versa) is checked in app/scripts/staging-build.test.mjs.
"""

import copy
import json
from pathlib import Path

import pytest

from veda.modules.estimator import promise_matrix

SPECS = Path(__file__).resolve().parents[3] / "docs/implementation/estimator/specifications"
SPEC = json.loads((SPECS / "essential-specification-v1.1.json").read_text())
MATRIX = json.loads((SPECS / "essential-1.1-promise-matrix.json").read_text())


def test_the_committed_matrix_is_structurally_complete():
    promise_matrix.validate(SPEC, MATRIX)
    assert {r["status"] for r in MATRIX["rows"]} <= set(promise_matrix.STATUSES)


def test_nothing_is_merely_proposed_and_every_unconfirmed_row_blocks_activation():
    assert not any(r["status"] == "PROPOSED" for r in MATRIX["rows"])
    blocked = promise_matrix.blockers(MATRIX)
    unconfirmed = [r for r in MATRIX["rows"] if r["status"] not in promise_matrix.CONFIRMED | {"REMOVED"}]
    unnamed = [
        r for r in MATRIX["rows"] if r["status"] in promise_matrix.CONFIRMED and r["accountable_owner"] == "UNASSIGNED"
    ]
    assert len(blocked) == len(unconfirmed) + len(unnamed)


def _broken(mutate):
    m = copy.deepcopy(MATRIX)
    mutate(m)
    return m


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda m: m["rows"][0]["statements"].pop(), "statements differ"),
        (lambda m: m["rows"].pop(0), "has no row"),
        (lambda m: m["rows"][0].update(status="PROPOSED"), "is not one of"),
        (lambda m: m["rows"][0].update(quotation_mapping=""), "missing quotation_mapping"),
        (lambda m: m["rows"][0].update(blocked_on=""), "blocked_on"),
        (lambda m: m.update(spec_code="ESSENTIAL-1.0"), "not ESSENTIAL-1.1"),
        (lambda m: m["rows"].append(copy.deepcopy(m["rows"][0])), "unique"),
    ],
)
def test_an_incomplete_matrix_is_refused(mutate, message):
    with pytest.raises(promise_matrix.MatrixError, match=message):
        promise_matrix.validate(SPEC, _broken(mutate))


def test_confirmed_rows_with_named_owners_clear_the_blockers():
    def confirm(m):
        for r in m["rows"]:
            r.update(status="OWNER_CONFIRMED", accountable_owner="Named Person (role)")
        m["rows"][-1]["status"] = "REMOVED"

    m = _broken(confirm)
    promise_matrix.validate(SPEC, m)
    assert promise_matrix.blockers(m) == []
    m["rows"][0]["accountable_owner"] = "UNASSIGNED"
    assert promise_matrix.blockers(m) == [f"{m['rows'][0]['id']}: no named accountable owner"]
