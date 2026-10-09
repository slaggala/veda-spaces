"""Final pre-activation closure: the reviewed customer-promise matrix covers every visible promise.

The matrix is packaged with the API (veda/modules/estimator/approved/essential-1.1-promise-matrix.json). It must list
exactly the specification's statements, every promise in the V2 customer copy (estimate-v2-copy.js, which is JSON so
these tests can read it in the API CI job), and the runtime texts the API sends. Activation needs every shown row
OPERATIONALLY_CONFIRMED with a named owner, backup and date; nothing here infers an approval.
"""

import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from veda.modules.estimator import activation, promise_matrix

REPO = Path(__file__).resolve().parents[3]
SPEC = json.loads((REPO / "docs/implementation/estimator/specifications/essential-specification-v1.1.json").read_text())
MATRIX = promise_matrix.load("ESSENTIAL-1.1")
COPY = activation.customer_copy()
PAGE = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (REPO / "app/e2e/site-release/estimate.html").read_text()))


def leaves(node):
    if isinstance(node, str):
        return [node]
    values = node.values() if isinstance(node, dict) else node
    return [leaf for v in values for leaf in leaves(v)]


def test_the_packaged_matrix_is_structurally_complete():
    promise_matrix.validate(SPEC, MATRIX)
    assert {r["status"] for r in MATRIX["rows"]} <= set(promise_matrix.STATUSES)


def test_no_row_is_ready_until_operations_confirms_it():
    blocked = promise_matrix.blockers(MATRIX)
    shown = [r for r in MATRIX["rows"] if r["status"] != "REMOVED"]
    assert len(blocked) == len(shown), "every shown row blocks activation today"
    assert not any(r["status"] in ("PROPOSED", "OWNER_CONFIRMED") for r in MATRIX["rows"])


def test_every_copy_promise_is_in_the_matrix_and_every_page_row_is_shown():
    """L4: the page-row verification runs here too, not only in the Node staging-build test."""
    listed = {t for r in MATRIX["rows"] for t in r["statements"]}
    promises = leaves(COPY["promise"])
    assert [t for t in promises if t not in listed] == []
    for r in MATRIX["rows"]:
        if r["kind"] != "page" or r["where"].startswith("Estimate response"):
            continue
        for t in r["statements"]:
            shown = t in promises or t in PAGE
            assert (not shown) if r["status"] == "REMOVED" else shown, f"{r['id']}: {t}"


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
        (lambda m: m["rows"][0].update(backup_owner=""), "missing backup_owner"),
        (lambda m: m["rows"][0].pop("confirmed_on"), "confirmed_on"),
        (lambda m: m["rows"][0].update(blocked_on=""), "blocked_on"),
        (lambda m: m.update(spec_code="ESSENTIAL-1.0"), "not ESSENTIAL-1.1"),
        (lambda m: m["rows"].append(copy.deepcopy(m["rows"][0])), "unique"),
        (lambda m: m["rows"][0].update(internal_requirement="Laminate within ₹1,200 per sheet"), "amount or a rate"),
        (lambda m: m["rows"][0].update(quotation_mapping="Uses rate_minor from the card"), "amount or a rate"),
    ],
)
def test_an_incomplete_or_commercial_matrix_is_refused(mutate, message):
    with pytest.raises(promise_matrix.MatrixError, match=message):
        promise_matrix.validate(SPEC, _broken(mutate))


def confirm(m, **override):
    for r in m["rows"]:
        r.update(
            status="OPERATIONALLY_CONFIRMED",
            accountable_owner="Named Person (role)",
            backup_owner="Second Person (role)",
            confirmed_on="2026-10-10",
        )
        r.update(override)
    return m


def test_only_operational_confirmation_with_owners_clears_the_blockers():
    m = confirm(copy.deepcopy(MATRIX))
    promise_matrix.validate(SPEC, m)
    assert promise_matrix.blockers(m) == []
    for field, value, message in [
        ("status", "OWNER_CONFIRMED", "OWNER_CONFIRMED"),
        ("status", "SALES_CONFIRMED", "SALES_CONFIRMED"),
        ("accountable_owner", "UNASSIGNED", "missing a named accountable owner"),
        ("backup_owner", "UNASSIGNED", "missing a named backup"),
        ("confirmed_on", None, "missing a confirmation date"),
    ]:
        one = copy.deepcopy(m)
        one["rows"][0][field] = value
        assert [b for b in promise_matrix.blockers(one) if b.startswith(one["rows"][0]["id"])][0].count(message) == 1
    removed = copy.deepcopy(m)
    removed["rows"][0].update(status="REMOVED", accountable_owner="UNASSIGNED")
    assert promise_matrix.blockers(removed) == []


def test_unregistered_runtime_text_is_suppressed():
    view = {
        "disclaimer": "This is a preliminary budgetary estimate for planning purposes and is not a final quotation or contractual offer.",
        "exclusions": ["Civil, plumbing-line and structural changes", "Free modular kitchen upgrade"],
        "client_scope": ["Sink", "Chimney"],
    }
    rooms = [
        {
            "room": "KITCHEN",
            "assumptions": [
                "Kitchen – Modular kitchen: counter length assumed 12 ft (typical for 3 bhk).",
                "Guaranteed lowest price for 10 years.",
            ],
        }
    ]
    out = promise_matrix.registered_text(MATRIX, view, rooms)
    assert out["approved"] and out["matrix"]["sha256"] == promise_matrix.sha256(MATRIX)
    assert out["disclaimer"] == view["disclaimer"]
    assert out["exclusions"] == ["Civil, plumbing-line and structural changes"]
    assert out["client_scope"] == ["Sink"]
    assert out["assumptions"] == {
        "KITCHEN": ["Kitchen – Modular kitchen: counter length assumed 12 ft (typical for 3 bhk)."]
    }
    assert out["suppressed"] == 3
    changed = promise_matrix.registered_text(MATRIX, {**view, "disclaimer": "This is your final price."}, [])
    assert changed["disclaimer"] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_site_build_and_the_api_compute_the_same_copy_digests():
    script = (
        "import { canonicalSha256, readCopy } from './app/scripts/staging-build.mjs';"
        "const c = readCopy('app/e2e/site-release/assets/estimate-v2-copy.js'); const p = c.promise;"
        "console.log(canonicalSha256(c), canonicalSha256({ manufacturer: p.manufacturer, service: p.service,"
        " serviceNote: p.serviceNote }));"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split()
    d = activation.digests("ESSENTIAL-1.1")
    assert out == [d["customer_copy_sha256"], d["warranty_copy_sha256"]]
