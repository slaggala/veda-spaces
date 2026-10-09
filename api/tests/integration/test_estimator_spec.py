"""ADR-012 T9: the customer specification master and its snapshot on each estimate."""

import copy
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa

from tests.integration.test_estimator_api import CARD_DOC, SITE, body, load_card
from tests.support.dbh import rows
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.estimator import activation, promise_matrix, service
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


# --- final pre-activation closure: the gate, reactivation, rollback, runtime text ------------------------------------
DOCS = Path(__file__).resolve().parents[3] / "docs/implementation/estimator/specifications"
ESSENTIAL_10 = json.loads((DOCS / "essential-specification-v1.0.json").read_text())
ESSENTIAL_11 = json.loads((DOCS / "essential-specification-v1.1.json").read_text())
OWNER_APPROVAL = "Owner approval 2026-10-10, ESSENTIAL-1.1 protected staging"
RELEASE = "0123abcd4567"  # pragma: allowlist secret (a test release id)


def staging(monkeypatch):
    monkeypatch.setattr(service, "settings", lambda: SimpleNamespace(env="staging"))


def active_card_sha():
    with db.unit_of_work(write=False) as s:
        return service._active_card_sha(s)


def write(path, doc):
    path.write_text(json.dumps(doc))


def approve_all(tmp_path, monkeypatch):
    """A fully approved, current set of reviewed records (the shape operations, sales and the owner will produce)."""
    d = tmp_path / "approved"
    d.mkdir()
    matrix = copy.deepcopy(promise_matrix.load("ESSENTIAL-1.1"))
    for r in matrix["rows"]:
        r.update(
            status="OPERATIONALLY_CONFIRMED",
            accountable_owner="Named Person (ops)",
            backup_owner="Second Person (ops)",
            confirmed_on="2026-10-10",
        )
    sales = copy.deepcopy(promise_matrix.load("ESSENTIAL-1.1", "sales-decisions"))
    for item in sales["items"]:
        item.update(owner_decision="APPROVE", owner_name="Sales Lead", decision_date="2026-10-10")
    write(d / "essential-1.1-promise-matrix.json", matrix)
    write(d / "essential-1.1-sales-decisions.json", sales)
    monkeypatch.setattr(promise_matrix, "APPROVED_DIR", d)
    monkeypatch.setattr(activation, "repository_blockers", lambda paths: [])
    digests = activation.digests("ESSENTIAL-1.1")
    approval = copy.deepcopy(
        json.loads((DOCS.parents[3] / "api/veda/modules/estimator/approved/essential-1.1-approval.json").read_text())
    )
    approval.update(
        status="APPROVED",
        owner="Owner Name",
        approved_on="2026-10-10",
        approval_reference=OWNER_APPROVAL,
        reviewed_commit="0123abcd",
        specification_sha256=service._sha(ESSENTIAL_11),
        sales_decisions_version=sales["version"],
        operations_confirmation_version=matrix["version"],
        real_card_equivalence={
            "card_version": "SYNTHETIC-2",
            "card_sha256": active_card_sha(),
            "result": "PASS",
            "run_on": "2026-10-10",
            "commit": "0123abcd",
        },
        **digests,
    )
    write(d / "essential-1.1-approval.json", approval)
    return d


def load_11(activate=False, **kw):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_11)
        if activate:
            service.activate_spec(s, "ESSENTIAL-1.1", OWNER_APPROVAL, **kw)


def activate(code, approval=OWNER_APPROVAL, **kw):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        return service.activate_spec(s, code, approval, **kw).status


def rollback(approval=OWNER_APPROVAL, **kw):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        return service.rollback_spec(s, "ESSENTIAL", approval, **kw).spec_code


def service_list():
    with db.unit_of_work(write=False) as s:
        return service.list_specs(s)


def last_event():
    return rows(sa.select(EstimatorSpecEvent).order_by(EstimatorSpecEvent.id.desc()))[0]  # UUIDv7: time-ordered


def test_a_specification_without_room_promises_needs_ux_v1_confirmed(api):
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_10)
        with pytest.raises(service.SpecError, match="STAGING_ESTIMATOR_UX=v1"):
            service.activate_spec(s, "ESSENTIAL-1.0", APPROVAL)
        service.activate_spec(s, "ESSENTIAL-1.0", APPROVAL, ux_v1_confirmed=True)
        service.load_spec(s, spec_version(1))
        service.activate_spec(s, "SYNTHETIC-ESSENTIAL-1.0", APPROVAL)
        with pytest.raises(service.SpecError, match="STAGING_ESTIMATOR_UX=v1"):
            service.rollback_spec(s, "ESSENTIAL", APPROVAL)
        assert service.rollback_spec(s, "ESSENTIAL", APPROVAL, ux_v1_confirmed=True).spec_code == "ESSENTIAL-1.0"
        with pytest.raises(service.SpecError, match="approval reference"):
            service.rollback_spec(s, "ESSENTIAL", "short")
    assert [x["spec"] for x in service_list() if x["status"] == "ACTIVE"] == ["ESSENTIAL-1.0"]


def test_on_staging_activation_uses_only_the_reviewed_records_and_records_the_evidence(api, tmp_path, monkeypatch):
    load_card()
    load_11()
    approve_all(tmp_path, monkeypatch)
    staging(monkeypatch)
    with pytest.raises(service.SpecError, match="--release"):
        activate("ESSENTIAL-1.1")
    assert activate("ESSENTIAL-1.1", release=RELEASE, operator="ops-user") == "ACTIVE"
    detail = last_event().detail
    assert last_event().event_type == "SPEC_ACTIVATED"
    assert detail["release"] == RELEASE and detail["operator"] == "ops-user" and detail["environment"] == "staging"
    assert detail["specification_sha256"] == service._sha(ESSENTIAL_11)
    assert detail["promise_matrix_sha256"] == promise_matrix.sha256(promise_matrix.load("ESSENTIAL-1.1"))
    assert detail["sales_decisions_version"] == "1" and detail["approval_version"] == "1"
    assert detail["approval_reference"] == OWNER_APPROVAL and detail["at"]
    assert [(x["spec"], x["status"]) for x in service_list()] == [("ESSENTIAL-1.1", "ACTIVE")]


def test_on_staging_the_committed_pending_records_refuse_activation(api, monkeypatch):
    load_card()
    load_11()
    staging(monkeypatch)
    monkeypatch.setattr(activation, "repository_blockers", lambda paths: [])
    with pytest.raises(service.SpecError, match="not ready for activation: spec.structure: BLOCKED"):
        activate("ESSENTIAL-1.1", release=RELEASE)


def _mutate_matrix(d):
    m = json.loads((d / "essential-1.1-promise-matrix.json").read_text())
    m["rows"][0]["status"] = "BLOCKED"
    m["rows"][0]["blocked_on"] = "re-opened by operations"
    write(d / "essential-1.1-promise-matrix.json", m)


def _mutate_sales(field, value):
    def apply(d):
        sales = json.loads((d / "essential-1.1-sales-decisions.json").read_text())
        sales["items"][0][field] = value
        write(d / "essential-1.1-sales-decisions.json", sales)

    return apply


def _mutate_approval(**changes):
    def apply(d):
        a = json.loads((d / "essential-1.1-approval.json").read_text())
        a.update(changes)
        write(d / "essential-1.1-approval.json", a)

    return apply


@pytest.mark.parametrize(
    "mutate,message",
    [
        (_mutate_matrix, "spec.structure: BLOCKED"),
        (_mutate_sales("owner_decision", None), "sales S1: no decision"),
        (_mutate_sales("owner_decision", "CHANGE"), "CHANGE needs a new specification version"),
        (_mutate_approval(status="PENDING"), "is PENDING, not APPROVED"),
        (_mutate_approval(owner=""), "has no owner"),
        (_mutate_approval(specification_sha256="0" * 64), "specification_sha256 does not match"),
        (_mutate_approval(customer_copy_sha256="0" * 64), "customer_copy_sha256 does not match"),
        (_mutate_approval(warranty_copy_sha256="0" * 64), "warranty_copy_sha256 does not match"),
        (
            _mutate_approval(scope={"environments": ["production"], "package": "ESSENTIAL", "public_intake": False}),
            "does not cover",
        ),
        (
            _mutate_approval(scope={"environments": ["staging"], "package": "ESSENTIAL", "public_intake": True}),
            "exclude public intake",
        ),
        (
            _mutate_approval(real_card_equivalence={"card_sha256": "f" * 64, "result": "PASS"}),
            "not the card the equivalence",
        ),
        (_mutate_approval(real_card_equivalence={"card_sha256": None, "result": None}), "no passing real-card"),
        (_mutate_approval(approval_reference="Some other approval"), "--approval does not match"),
    ],
)
def test_any_missing_stale_or_changed_record_fails_closed(api, tmp_path, monkeypatch, mutate, message):
    load_card()
    load_11()
    d = approve_all(tmp_path, monkeypatch)
    mutate(d)
    staging(monkeypatch)
    with pytest.raises(service.SpecError, match=message):
        activate("ESSENTIAL-1.1", release=RELEASE)
    assert not [x for x in service_list() if x["status"] == "ACTIVE"]


def test_reactivation_after_rollback_to_v1_reruns_the_whole_gate(api, tmp_path, monkeypatch):
    load_card()
    load_11()
    d = approve_all(tmp_path, monkeypatch)
    staging(monkeypatch)
    activate("ESSENTIAL-1.1", release=RELEASE)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        service.load_spec(s, ESSENTIAL_10)
    assert activate("ESSENTIAL-1.0", ux_v1_confirmed=True, release=RELEASE) == "ACTIVE"  # back to V1
    assert rollback(release=RELEASE) == "ESSENTIAL-1.1", "a current approval lets 1.1 come back"
    assert last_event().event_type == "SPEC_ROLLED_BACK" and last_event().detail["promise_matrix_sha256"]
    assert activate("ESSENTIAL-1.0", ux_v1_confirmed=True, release=RELEASE) == "ACTIVE"
    _mutate_matrix(d)  # an operations row re-opened after the first activation
    with pytest.raises(service.SpecError, match="not ready for activation"):
        rollback(release=RELEASE)
    load_card(version="SYNTHETIC-3")  # and a different active card makes the equivalence stale
    (tmp_path / "again").mkdir()
    approve_all(tmp_path / "again", monkeypatch)
    _mutate_approval(real_card_equivalence={"card_sha256": "e" * 64, "result": "PASS"})(tmp_path / "again" / "approved")
    with pytest.raises(service.SpecError, match="not the card the equivalence"):
        rollback(release=RELEASE)
    assert [x["spec"] for x in service_list() if x["status"] == "ACTIVE"] == ["ESSENTIAL-1.0"]


def test_rollback_revalidates_and_refuses_a_tampered_specification(api):
    load_spec(spec_version(1))
    load_spec(spec_version(2))
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.execute(
            sa.select(EstimatorCustomerSpec).where(EstimatorCustomerSpec.spec_code == "SYNTHETIC-ESSENTIAL-1.0")
        ).scalar_one()
        tampered = copy.deepcopy(row.document)
        tampered["summary"] = "Tampered after approval."
        row.document = tampered
    with pytest.raises(service.SpecError, match="does not match its SHA-256"):
        rollback(APPROVAL)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        row = s.execute(
            sa.select(EstimatorCustomerSpec).where(EstimatorCustomerSpec.spec_code == "SYNTHETIC-ESSENTIAL-1.0")
        ).scalar_one()
        invalid = copy.deepcopy(row.document)
        invalid["categories"][0]["details"] = ["Laminate within ₹1,200 per sheet"]
        row.document, row.document_sha256 = invalid, service._sha(invalid)
    with pytest.raises(service.SpecError, match="invalid customer specification"):
        rollback(APPROVAL)


def test_cli_activation_check_and_refusal_of_an_external_matrix(api, tmp_path, capsys, monkeypatch):
    from veda.cli.main import main

    load_card()
    f10, f11 = tmp_path / "s10.json", tmp_path / "s11.json"
    write(f10, ESSENTIAL_10)
    write(f11, ESSENTIAL_11)
    monkeypatch.setattr(activation, "repository_blockers", lambda paths: [])
    assert main(["estimator", "activation-check", str(f10)]) == 3  # L2: never "ready" for 1.0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ready"] is False and "no room promises" in out["blockers"][0]
    assert main(["estimator", "activation-check", str(f11)]) == 3
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["environment"] == "staging" and len(out["sha256"]) == 64
    assert (
        len(out["digests"]["promise_matrix_sha256"]) == 64
        and "the owner approval record is PENDING, not APPROVED" in out["blockers"]
    )
    m = tmp_path / "matrix.json"
    write(m, promise_matrix.load("ESSENTIAL-1.1"))
    assert main(["estimator", "activation-check", str(f11), "--matrix", str(m)]) == 2
    assert (
        main(
            ["estimator", "activate-spec", "--spec", "ESSENTIAL-1.1", "--approval", OWNER_APPROVAL, "--matrix", str(m)]
        )
        == 2
    )
    assert "externally supplied matrix is not accepted" in capsys.readouterr().err
    approve_all(tmp_path, monkeypatch)
    assert main(["estimator", "activation-check", str(f11), "--approval", OWNER_APPROVAL]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["ready"] is True and out["blockers"] == [] and out["active_now"] == []
    assert service_list() == [], "a check never loads or activates anything"


def test_repository_checks_refuse_untracked_modified_or_outside_records(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    approved = repo / "api/veda/modules/estimator/approved"
    approved.mkdir(parents=True)
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("config", "user.email", "t@example.invalid")
    run("config", "user.name", "t")
    tracked, untracked = approved / "a.json", approved / "b.json"
    tracked.write_text("{}")
    run("add", ".")
    run("commit", "-qm", "x")
    untracked.write_text("{}")
    monkeypatch.setattr(activation, "REPO", repo)
    assert activation.repository_blockers([tracked]) == []
    assert "is not tracked" in activation.repository_blockers([untracked])[0]
    tracked.write_text('{"edited": true}')
    assert "differs from the committed version" in activation.repository_blockers([tracked])[0]
    assert "outside the approved repository path" in activation.repository_blockers([tmp_path / "elsewhere.json"])[0]


@ON
def test_only_registered_runtime_text_reaches_v2(api):
    """M3: V2's block keeps the registered disclaimer, exclusions and client scope, and drops anything else."""
    card = copy.deepcopy(CARD_DOC)
    card["version"] = "SYNTHETIC-UNREGISTERED"
    card["exclusions"] = [*card["exclusions"], "Free modular upgrade for every room"]
    load_card(card)
    load_11(activate=True)
    r = post(api)
    assert r.status == 201, r
    v2 = r.data["v2_copy"]
    assert v2["approved"] is True and v2["matrix"]["spec_code"] == "ESSENTIAL-1.1"
    assert "Free modular upgrade for every room" in r.data["exclusions"], "V1 keeps its existing response"
    assert "Free modular upgrade for every room" not in v2["exclusions"] and v2["suppressed"] >= 1
    assert v2["disclaimer"] == r.data["disclaimer"] and v2["client_scope"] == r.data["client_scope"]
    assert all(v2["assumptions"][d["room"]] == d["assumptions"] for d in r.data["room_details"])


@ON
def test_without_a_registered_matrix_v2_gets_no_runtime_text(api):
    load_card()
    load_spec(spec_version(1))  # the synthetic specification has no packaged matrix
    r = post(api)
    assert r.status == 201 and r.data["v2_copy"] == {"approved": False}


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
