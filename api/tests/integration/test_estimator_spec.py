"""ADR-012 T9: the customer specification master and its snapshot on each estimate."""

import copy
import json
from pathlib import Path

import pytest
import sqlalchemy as sa

from tests.integration.test_estimator_api import SITE, body, load_card
from tests.support.dbh import rows
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.estimator import service
from veda.modules.estimator.models import (
    BudgetEstimate,
    EstimatorCustomerSpec,
    EstimatorCustomerSpecItem,
    EstimatorSpecEvent,
)

SPEC_DOC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-customer-spec.json").read_text())
APPROVAL = "Owner approval 2026-10-08 (synthetic specification)"
ON = pytest.mark.settings(estimator_enabled=True)


def spec_version(n: int) -> dict:
    doc = copy.deepcopy(SPEC_DOC)
    doc["version"], doc["spec_code"] = f"{n}.0", f"SYNTHETIC-ESSENTIAL-{n}.0"
    doc["summary"] = f"SYNTHETIC test specification, version {n}."
    return doc


def load_spec(doc, *, activate=True):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, doc)
        if activate:
            service.activate_spec(s, doc["spec_code"], APPROVAL)
    return doc["spec_code"]


def post(api):
    return api.post("/api/v1/public/estimates", body(), anonymous=True, headers={"Origin": SITE})


def test_lifecycle_one_active_per_package_with_audited_events(api):
    load_spec(spec_version(1))
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        with pytest.raises(service.SpecError, match="already loaded"):
            service.load_spec(s, spec_version(1))
    load_spec(spec_version(2), activate=False)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        with pytest.raises(service.SpecError, match="approval reference"):
            service.activate_spec(s, "SYNTHETIC-ESSENTIAL-2.0", "short")
        service.activate_spec(s, "SYNTHETIC-ESSENTIAL-2.0", APPROVAL)
    states = {r.spec_code: r.status for r in rows(sa.select(EstimatorCustomerSpec))}
    assert states == {"SYNTHETIC-ESSENTIAL-1.0": "RETIRED", "SYNTHETIC-ESSENTIAL-2.0": "ACTIVE"}
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        assert service.rollback_spec(s, "ESSENTIAL", APPROVAL).spec_code == "SYNTHETIC-ESSENTIAL-1.0"
    events = [e.event_type for e in rows(sa.select(EstimatorSpecEvent).order_by(EstimatorSpecEvent.created_on))]
    assert events == [
        "SPEC_LOADED",
        "SPEC_ACTIVATED",
        "SPEC_LOADED",
        "SPEC_RETIRED",
        "SPEC_ACTIVATED",
        "SPEC_RETIRED",
        "SPEC_ROLLED_BACK",
    ]
    items = rows(sa.select(EstimatorCustomerSpecItem))
    assert len(items) == 8 and all(i.equivalent_rule and i.final_selection for i in items)


def test_a_specification_with_amounts_is_refused_on_load(api):
    doc = spec_version(3)
    doc["categories"][0]["details"] = ["Laminate up to ₹2,500 per sheet"]
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        with pytest.raises(service.SpecError, match="invalid customer specification"):
            service.load_spec(s, doc)


@ON
def test_each_estimate_snapshots_the_specification_and_history_never_changes(api):
    load_card()
    load_spec(spec_version(1))
    first = post(api)
    assert first.status == 201, first
    shown = first.data["specification"]
    assert shown["spec_code"] == "SYNTHETIC-ESSENTIAL-1.0" and shown["categories"][0]["equivalent_rule"]
    assert "₹" not in json.dumps(shown, ensure_ascii=False)
    load_spec(spec_version(2))  # a new version is activated after the first estimate
    second = post(api)
    assert second.data["specification"]["spec_code"] == "SYNTHETIC-ESSENTIAL-2.0"
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        row = s.execute(
            sa.select(BudgetEstimate).where(BudgetEstimate.public_reference == first.data["reference"])
        ).scalar_one()
        again = service.public_view(row)
        assert again["specification"]["spec_code"] == "SYNTHETIC-ESSENTIAL-1.0", (
            "the first estimate keeps what it showed"
        )
        assert row.customer_spec_sha256 == service._sha(spec_version(1))
        staff = service.staff_view(s, row)
        assert staff["specification"]["spec_code"] == "SYNTHETIC-ESSENTIAL-1.0"


@ON
def test_without_an_active_specification_estimates_still_work(api):
    load_card()
    r = post(api)
    assert r.status == 201 and r.data["specification"] is None


def test_cli_spec_actions_print_codes_and_hashes_only(api, tmp_path, capsys):
    from veda.cli.main import main

    f = tmp_path / "spec.json"
    f.write_text(json.dumps(spec_version(1)))
    assert main(["estimator", "validate-spec", str(f)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["valid"] and out["spec"] == "SYNTHETIC-ESSENTIAL-1.0" and set(out) == {"valid", "spec", "sha256"}
    assert main(["estimator", "load-spec", str(f)]) == 0
    assert main(["estimator", "activate-spec", "--spec", "SYNTHETIC-ESSENTIAL-1.0", "--approval", APPROVAL]) == 0
    assert main(["estimator", "activate-spec", "--spec", "SYNTHETIC-ESSENTIAL-1.0", "--approval", APPROVAL]) == 2
    capsys.readouterr()
    assert main(["estimator", "list-specs"]) == 0
    listed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])["specs"]
    assert [x["status"] for x in listed] == ["ACTIVE"]
