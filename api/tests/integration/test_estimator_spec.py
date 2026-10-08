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
    BudgetEstimateProjectItem,
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
    assert len(items) == 2 * len(SPEC_DOC["categories"]) and all(i.equivalent_rule and i.final_selection for i in items)


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


@ON
def test_room_details_carry_promises_from_the_priced_lines_and_the_assumptions(api):
    load_card()
    load_spec(spec_version(1))
    r = post(api)  # a kitchen and a measured sliding wardrobe (with its loft)
    assert r.status == 201, r
    details = {d["room"]: d for d in r.data["room_details"]}
    assert details["KITCHEN"]["materials"]["line"] == (
        "Branded plywood cabinetry · Laminate finish · Soft-close kitchen hardware"
    )
    assert details["MASTER_BEDROOM"]["materials"]["line"] == (
        "Branded plywood wardrobe · Laminate finish · Soft-close wardrobe hardware"  # the loft keeps soft-close hinges
    )
    assert "soft_close" in details["MASTER_BEDROOM"]["materials"]["categories"]
    assert details["KITCHEN"]["assumptions"] and all("Kitchen" in a for a in details["KITCHEN"]["assumptions"])
    assert not any("width" in a for a in details["MASTER_BEDROOM"]["assumptions"]), "the measured width is not assumed"
    assert "₹" not in json.dumps(r.data["room_details"], ensure_ascii=False)
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        row = s.execute(
            sa.select(BudgetEstimate).where(BudgetEstimate.public_reference == r.data["reference"])
        ).scalar_one()
        assert service.staff_view(s, row)["room_details"] == r.data["room_details"]


@ON
def test_room_details_without_a_specification_keep_the_assumptions_only(api):
    load_card()
    r = post(api)
    assert r.status == 201 and all(d["materials"] is None for d in r.data["room_details"])
    assert any(d["assumptions"] for d in r.data["room_details"])


# --- pre-activation closure: guards, F1 through the API, package components -------------------------------------------
DOCS = Path(__file__).resolve().parents[3] / "docs/implementation/estimator/specifications"
ESSENTIAL_10 = json.loads((DOCS / "essential-specification-v1.0.json").read_text())
ESSENTIAL_11 = json.loads((DOCS / "essential-specification-v1.1.json").read_text())
MATRIX = json.loads((DOCS / "essential-1.1-promise-matrix.json").read_text())


def _confirmed_matrix():
    m = copy.deepcopy(MATRIX)
    for r in m["rows"]:
        r.update(status="OWNER_CONFIRMED", accountable_owner="Named Person (test)")
    return m


def test_a_specification_without_room_promises_needs_ux_v1_confirmed(api):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_10)
        with pytest.raises(service.SpecError, match="STAGING_ESTIMATOR_UX=v1"):
            service.activate_spec(s, "ESSENTIAL-1.0", APPROVAL)
        service.activate_spec(s, "ESSENTIAL-1.0", APPROVAL, ux_v1_confirmed=True)
        service.load_spec(s, spec_version(1))
        service.activate_spec(s, "SYNTHETIC-ESSENTIAL-1.0", APPROVAL)
        with pytest.raises(service.SpecError, match="STAGING_ESTIMATOR_UX=v1"):
            service.rollback_spec(s, "ESSENTIAL", APPROVAL)  # back to 1.0: V2 must be switched off first
        assert service.rollback_spec(s, "ESSENTIAL", APPROVAL, ux_v1_confirmed=True).spec_code == "ESSENTIAL-1.0"
        with pytest.raises(service.SpecError, match="approval reference"):
            service.rollback_spec(s, "ESSENTIAL", "short")
    assert [x["spec"] for x in service_list() if x["status"] == "ACTIVE"] == ["ESSENTIAL-1.0"]


def service_list():
    with db.unit_of_work(write=False) as s:
        return service.list_specs(s)


def test_on_staging_activation_needs_a_confirmed_matrix(api, monkeypatch):
    monkeypatch.setattr(service, "settings", lambda: type("S", (), {"env": "staging"})())
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_11)
        with pytest.raises(service.SpecError, match="matrix is required"):
            service.activate_spec(s, "ESSENTIAL-1.1", APPROVAL)
        with pytest.raises(service.SpecError, match="not ready for activation: spec.structure: BLOCKED"):
            service.activate_spec(s, "ESSENTIAL-1.1", APPROVAL, matrix=MATRIX)
        broken = copy.deepcopy(MATRIX)
        broken["rows"].pop(0)
        with pytest.raises(service.SpecError, match="matrix: category structure has no row"):
            service.activate_spec(s, "ESSENTIAL-1.1", APPROVAL, matrix=broken)
        assert service.activate_spec(s, "ESSENTIAL-1.1", APPROVAL, matrix=_confirmed_matrix()).status == "ACTIVE"
    assert [(x["spec"], x["status"]) for x in service_list()] == [("ESSENTIAL-1.1", "ACTIVE")]


def test_cli_activation_check_reports_every_guard_and_never_activates(api, tmp_path, capsys):
    from veda.cli.main import main

    spec_file, matrix_file = tmp_path / "spec.json", tmp_path / "matrix.json"
    spec_file.write_text(json.dumps(ESSENTIAL_11))
    matrix_file.write_text(json.dumps(MATRIX))
    digest = service._sha(ESSENTIAL_11)
    args = ["estimator", "activation-check", str(spec_file), "--matrix", str(matrix_file)]
    assert main([*args, "--expect-sha", digest]) == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ready"] is False and out["sha256"] == digest and any("BLOCKED" in b for b in out["blockers"])
    assert main([*args, "--expect-sha", "0" * 64]) == 3
    assert "not the owner-approved digest" in capsys.readouterr().out
    matrix_file.write_text(json.dumps(_confirmed_matrix()))
    assert main([*args, "--expect-sha", digest]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {
        "spec": "ESSENTIAL-1.1",
        "sha256": digest,
        "blockers": [],
        "active_now": [],
        "ready": True,
    }
    assert service_list() == [], "a check never loads or activates anything"


@ON
def test_essential_10_never_reaches_v2_room_details_through_the_api(api):
    """F1 regression through the API: with ESSENTIAL-1.0 active, no room carries a category or a line."""
    load_card()
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_10)
        service.activate_spec(s, "ESSENTIAL-1.0", APPROVAL, ux_v1_confirmed=True)
    r = post(api)
    assert r.status == 201
    assert r.data["specification"]["room_promises"] is False
    assert all(d["materials"] == {"line": None, "categories": []} for d in r.data["room_details"])


@ON
@pytest.mark.parametrize("scope", ["kitchen_and_wardrobe", "ceiling_only"])
def test_package_components_reconcile_priced_visible_and_stored(api, scope):
    load_card()
    selections = None
    if scope == "ceiling_only":
        selections = [{"room": "WHOLE_HOME", "product": "FALSE_CEILING"}]
    r = api.post(
        "/api/v1/public/estimates",
        body(**({"selections": selections} if selections else {})),
        anonymous=True,
        headers={"Origin": SITE},
    )
    assert r.status == 201, r
    visible = r.data["project_preparation"]
    with actor(system_context("CLI")), db.unit_of_work(write=False) as s:
        row = s.execute(
            sa.select(BudgetEstimate).where(BudgetEstimate.public_reference == r.data["reference"])
        ).scalar_one()
        priced = service.staff_view(s, row)["estimate"]["project_preparation"]["components"]
        stored = sorted(
            (i.component_code, i.amount_minor)
            for i in s.execute(
                sa.select(BudgetEstimateProjectItem).where(BudgetEstimateProjectItem.estimate_id == row.id)
            ).scalars()
        )
    assert visible["component_codes"] == [c["code"] for c in priced]
    assert sorted((c["code"], c["amount_minor"]) for c in priced) == stored, "the stored snapshot is what was priced"
    assert visible["amount_minor"] == sum(c["amount_minor"] for c in priced)
    assert visible["inclusions"] == list(dict.fromkeys(c["inclusion"] for c in priced))
    if scope == "ceiling_only":  # no carpentry: no plywood protection, no pest-control preparation
        assert not {"PLY_PROTECTION", "PEST_CONTROL"} & set(visible["component_codes"]) and visible["component_codes"]
    else:
        assert {"PLY_PROTECTION", "PEST_CONTROL"} <= set(visible["component_codes"])
