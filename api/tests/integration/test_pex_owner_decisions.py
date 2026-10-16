"""Owner decisions of 2026-10-16 (decision log 46): the committed delivery record says PEX-D01 YES and PEX-D02
COMMERCIAL_OBLIGATION_SATISFIED, and the handover gate takes the obligation from Project Commercials only: the record
must verify, accepted variations, reversals and credit count as Project Commercials counts them, and there is no
override. SYNTHETIC data only, both engines."""

from __future__ import annotations

import json

import pytest

from tests.support.commercial import ok
from tests.support.commercials import Commercials, install_policy
from tests.support.project import BASE, delivery, install, no_four_eyes

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True, customer_portal_enabled=True,
             project_lifecycle_enabled=True, project_commercials_enabled=True)  # fmt: skip
pytestmark = pytest.mark.settings(**FLAGS)
GATE = "COMMERCIAL_CONDITION"


@pytest.fixture
def policy(app):
    install(no_four_eyes())
    yield
    install(None)


def test_the_committed_record_carries_the_owner_decisions():
    from veda.modules.project import delivery_policy

    raw = json.loads(delivery_policy.FIXTURE.read_text())
    assert raw["status"] == "DECIDED" and raw["version"] == "PEX-POLICY-1"
    policy, _sha = delivery_policy._fixture()
    d01, d02 = policy.get("PEX-D01"), policy.get("PEX-D02")
    assert (d01.issue_reports, d01.handover_acknowledgement) == (True, True)
    assert d02.condition == "COMMERCIAL_OBLIGATION_SATISFIED"
    assert "decision log 46" in d01.reference and "decision log 46" in d02.reference


def _codes(t: Commercials, pid: str) -> set[str]:
    d = ok(t.api.get(f"{BASE}/{pid}", token=t.tok(t.founder)))
    return {b["code"] for b in d["handover_readiness"]["blockers"] if b["gate"] == GATE}


def test_the_obligation_gate_reads_project_commercials_and_counts_reversals(api, factory, policy):
    t = Commercials(api, factory)
    install_policy()
    prop, q, acc = t.opened()
    p = t.book(q, prop)
    prop2, _, q2 = t.accepted("3BHK")
    p2 = t.book(q2, prop2)
    delivery(pex_d02="COMMERCIAL_OBLIGATION_SATISFIED")
    assert _codes(t, p2["id"]) == {"COMMERCIAL_RECORD_MISSING"}  # this project's own chain, never another record
    assert _codes(t, p["id"]) == {"COMMERCIAL_OBLIGATION_OUTSTANDING"}
    total = t.get(acc)["position"]["value_minor"]
    t.pay(acc, total - 1)
    assert _codes(t, p["id"]) == {"COMMERCIAL_OBLIGATION_OUTSTANDING"}  # nearly paid is not paid
    last = t.pay(acc, 1)
    assert _codes(t, p["id"]) == set()
    assert last["position"]["outstanding_minor"] == 0
    t.reverse(acc, last["payments"][-1]["id"])
    assert _codes(t, p["id"]) == {"COMMERCIAL_OBLIGATION_OUTSTANDING"}  # a reversed payment no longer counts


def test_credit_satisfies_and_an_unsound_record_never_does(api, factory, policy, monkeypatch):
    from veda.modules.commercials import baseline as cbase
    from veda.modules.commercials import position as cpos

    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    p = t.book(q, prop)
    delivery(pex_d02="COMMERCIAL_OBLIGATION_SATISFIED")
    real = cpos.compute

    def credit(s, account, **kw):  # a variation reduced the value below what was paid (Project Commercials' credit)
        x = real(s, account, **kw)
        x.paid_minor, x.outstanding_minor, x.credit_minor = x.value_minor + 500, 0, 500
        return x

    monkeypatch.setattr(cpos, "compute", credit)
    assert _codes(t, p["id"]) == set()
    monkeypatch.setattr(cbase, "problems", lambda s, account: [{"code": "DIGEST_MISMATCH", "message": "SYNTHETIC"}])
    assert _codes(t, p["id"]) == {"COMMERCIAL_RECORD_UNSOUND"}  # never satisfied by a record that does not verify


@pytest.mark.settings(**{**FLAGS, "project_commercials_enabled": False})
def test_without_project_commercials_the_obligation_cannot_be_confirmed(api, factory, policy):
    from tests.support.project import Projects

    t = Projects(api, factory)
    prop, _, q = t.accepted()
    p = t.book(q, prop)
    delivery(pex_d02="COMMERCIAL_OBLIGATION_SATISFIED")
    codes = {b["code"] for b in t.get(p)["handover_readiness"]["blockers"] if b["gate"] == GATE}
    assert codes == {"COMMERCIAL_POSITION_UNAVAILABLE"}
