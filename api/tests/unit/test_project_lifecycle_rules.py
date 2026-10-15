"""Project lifecycle rules that need no database: the versioned definition, the undecided owner policy, the
customer-safe classification, the timeline's no-free-text rule, the vocabularies against their columns, the
capability matrix and the erasure boundary (PLB-04, PLB-05, PLB-32, PLB-35, PLB-42, PLB-51)."""

from __future__ import annotations

import json
import re

import pytest
import sqlalchemy as sa

import veda.models as models
from veda.kernel.audit_registry import policy_for
from veda.modules.project import classification, erasure, events, lifecycle, permissions, policy
from veda.modules.project import vocab as V
from veda.modules.project.models import TABLES

# A published definition is never edited: a change is a new version (PLB-05). This pin fails on any edit to it.
PINNED = {
    "PLB-2026.10.1": "11fa05902eb0f5dafd1e5d65b3a277d52b9a95ed64d1e6b8d6ff3293e9710c00",  # pragma: allowlist secret (SHA-256)
}


def test_every_definition_is_structurally_sound_and_published_versions_never_change():
    assert lifecycle.validate() == []
    for version, digest in PINNED.items():
        assert lifecycle.DEFINITIONS[version].sha256 == digest, f"{version} was edited: add a new version instead"
    assert lifecycle.CURRENT in lifecycle.DEFINITIONS


def test_the_definition_is_linear_forward_only_and_names_the_high_risk_moves():
    d = lifecycle.current()
    assert [s.code for s in d.stages][0] == "BOOKED" and d.stages[-1].code == "HANDED_OVER" and d.stages[-1].terminal
    assert {t.key for t in d.transitions if t.risk == "HIGH"} == {
        "DESIGN_FINALISATION>SCOPE_FROZEN", "PRODUCTION_READINESS>IN_PRODUCTION", "READY_FOR_INSTALLATION>INSTALLATION",
        "SNAGGING>READY_FOR_HANDOVER", "READY_FOR_HANDOVER>HANDED_OVER"}  # fmt: skip
    assert [t.command for t in d.transitions].count("HANDOVER") == 1 and d.transitions[-1].command == "HANDOVER"
    for t in d.transitions:
        assert "CHECKLIST_COMPLETE" in t.default_gates and "MILESTONES_COMPLETE" in t.default_gates
    assert "SITE_READY" in d.transition("SITE_READINESS", "PRODUCTION_READINESS").default_gates
    assert {"QC_PASSED", "SNAGS_RESOLVED"} <= set(d.transition("SNAGGING", "READY_FOR_HANDOVER").default_gates)
    assert "HANDOVER_EVIDENCE" in d.transition("READY_FOR_HANDOVER", "HANDED_OVER").default_gates


def test_the_shipped_policy_record_decides_nothing():
    doc = json.loads(policy.FIXTURE.read_text())
    assert doc["status"] == "UNDECIDED" and set(doc["decisions"]) == set(policy.SHAPES)
    assert all(v is None for v in doc["decisions"].values())
    view = policy.public_view()
    assert not any(d["decided"] for d in view["decisions"].values())
    assert {c for c, d in view["decisions"].items() if d["read_by_engine"]} == set(policy.CONSUMED)


def test_policy_shapes_refuse_what_the_definition_does_not_have():
    d = lifecycle.current()
    base = {"schema": "veda.project.lifecycle-policy/1", "version": "X", "status": "SYNTHETIC_TEST_ONLY", "note": "",
            "decisions": dict.fromkeys(policy.SHAPES)}  # fmt: skip
    ok = {**base, "decisions": {**base["decisions"], "PLB-OD-01": {"lifecycle_version": d.version,
                                                                  "lifecycle_sha256": d.sha256, "reference": "R"}}}  # fmt: skip
    policy.Policy.model_validate(ok)
    for code, value in (
        ("PLB-OD-01", {"lifecycle_version": d.version, "lifecycle_sha256": "0" * 64, "reference": "R"}),
        ("PLB-OD-02", {"lifecycle_version": d.version, "transitions": {"BOOKED>INSTALLATION": []}}),
        ("PLB-OD-02", {"lifecycle_version": d.version, "transitions": {"BOOKED>DESIGN_FINALISATION": ["MAGIC"]}}),
        ("PLB-OD-03", {"lifecycle_version": "PLB-0", "transitions": []}),
        ("PLB-OD-07", {"lifecycle_version": d.version, "items": {"BOOKED": ["NOT_AN_ITEM"]}}),
        ("PLB-OD-08", {"required_categories": ["NOT_A_CATEGORY"]}),
    ):
        with pytest.raises(ValueError):
            policy.Policy.model_validate({**base, "decisions": {**base["decisions"], code: value}})


def test_a_synthetic_policy_is_refused_outside_tests(monkeypatch):
    from veda.config import settings

    class _Prod:
        env = "production"

    monkeypatch.setattr("veda.modules.project.policy.settings", lambda: _Prod())
    with pytest.raises(RuntimeError):
        policy.install_for_tests({"status": "SYNTHETIC_TEST_ONLY"})
    assert settings  # the real settings object is untouched


def test_every_column_of_every_project_table_is_classified_and_nothing_is_published():
    assert set(classification.tables()) == set(TABLES)
    for table in TABLES:
        cols = [c.name for c in models.metadata.tables[table].columns]
        listed = classification.listed()[table]
        assert set(listed) <= set(cols), f"{table}: classification names a column that does not exist"
        classes = classification.classify(table, cols)
        assert set(classes) == set(cols) and set(classes.values()) <= set(classification.CLASSES)
        for c in ("id", "created_by", "updated_by", "lead_id", "project_id", "version"):
            if c in classes:
                assert classes[c] == classification.INTERNAL
    customer_actions = {(t, c) for t, cols in classification.listed().items() for c, k in cols.items()
                        if k == classification.CUSTOMER_ACTION}  # fmt: skip
    assert customer_actions == {("project_blocker", "customer_action"), ("project_site_readiness", "customer_action")}
    for internal in (("project_blocker", "description"), ("project_blocker", "title"), ("project_snag", "description"),
                     ("project_transition", "evaluation"), ("project_baseline", "accepted_total_minor"),
                     ("project_site_readiness", "note"), ("project_qc_check", "observation")):  # fmt: skip
        assert classification.column_class(*internal) == classification.INTERNAL
    assert classification.public_view()["published"] is False


@pytest.mark.parametrize("value", ["Mrs Rao called", "a" * 81, "x;DROP", {"nested": "x"}, ["ok", "not ok"]])
def test_the_timeline_refuses_free_text(value):
    with pytest.raises(ValueError):
        events._check(value, "detail")


@pytest.mark.parametrize(
    "value", ["CHECKLIST_ITEM_OPEN", "0" * 64, "2026-10-15", "SNAGGING>READY_FOR_HANDOVER", 3, True, None, ["A", "B"]]
)
def test_the_timeline_accepts_codes_ids_digests_and_dates(value):
    events._check(value, "detail")


def test_every_vocabulary_value_fits_its_column():
    pattern = re.compile(r"^(\w+) IN \((.*)\)$")
    for table in TABLES:
        t = models.metadata.tables[table]
        for ck in t.constraints:
            if not isinstance(ck, sa.CheckConstraint):
                continue
            text = str(ck.sqltext).replace(" IS NULL OR ", "|").split("|")[-1]
            m = pattern.match(text.strip())
            if not m or m.group(1) not in t.columns:
                continue
            length = getattr(t.columns[m.group(1)].type, "length", None)
            for value in re.findall(r"'([^']*)'", m.group(2)):
                assert length is None or len(value) <= length, f"{table}.{m.group(1)}: {value} > {length}"


def test_the_capability_matrix_is_scoped_least_privilege_and_keeps_admin_able_to_administer():
    m = permissions.MATRIX
    assert set(m) == set(permissions.CODES) and all(p.supports_scope for p in permissions.PERMISSIONS)
    assert all(not p.is_sensitive for p in permissions.PERMISSIONS)
    assert all(g.get("FOUNDER") == "A" for g in m.values())
    working = {"SALES", "DESIGNER", "SURVEYOR", "ESTIMATOR"}
    for code, grants in m.items():
        assert all(grants[r] == "O" for r in working & set(grants)), f"{code}: working roles act on member projects"
        if working & set(grants):
            assert grants.get("ADMIN") == "A", f"{code}: ADMIN must hold what the accounts it manages hold"
    for code in ("project.create_from_acceptance", "project.manage_stage", "project.approve_transition",
                 "project.complete_handover", "project.assign_team", "project.checklist.not_applicable"):  # fmt: skip
        assert "ADMIN" not in m[code] and not (working & set(m[code])), f"{code} is not a default working grant"
    assert set(permissions.RESPONSIBILITY_CAPABILITY) == set(V.RESPONSIBILITIES)
    assert set(permissions.RESPONSIBILITY_CAPABILITY.values()) <= set(permissions.CODES)


def test_erasure_covers_every_personal_field_the_audit_registry_names():
    erased = {model.__tablename__: set(fields) for model, fields in erasure.TEXT_FIELDS}
    for table in TABLES:
        pii = set(policy_for(table).pii) if policy_for(table) else set()
        assert pii <= erased.get(table, set()), f"{table}: {pii - erased.get(table, set())} not erased with the lead"


def test_owner_decisions_that_say_who_may_act_name_a_real_project_capability():
    base = {"schema": "veda.project.lifecycle-policy/1", "version": "X", "status": "SYNTHETIC_TEST_ONLY", "note": "",
            "decisions": dict.fromkeys(policy.SHAPES)}  # fmt: skip
    good = {"PLB-OD-06": {"snag_reclassification_capability": "project.manage_snag", "reference": "R"},
            "PLB-OD-08": {"required_categories": ["FINISH_AND_SURFACES"], "not_applicable_capability": "project.manage_qc"},
            "PLB-OD-13": {"capability": "project.manage_milestone", "reference": "R"}}  # fmt: skip
    policy.Policy.model_validate({**base, "decisions": {**base["decisions"], **good}})
    for code, value in (("PLB-OD-06", {"snag_reclassification_capability": "lead.read", "reference": "R"}),
                        ("PLB-OD-08", {"required_categories": [], "not_applicable_capability": "anything"}),
                        ("PLB-OD-13", {"capability": "SALES_MANAGER", "reference": "R"})):  # fmt: skip
        with pytest.raises(ValueError):
            policy.Policy.model_validate({**base, "decisions": {**base["decisions"], code: value}})
    assert {"PLB-OD-06", "PLB-OD-08", "PLB-OD-13"} <= set(policy.CONSUMED)
