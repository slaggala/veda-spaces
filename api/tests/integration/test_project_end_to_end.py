"""PLB-47 and PLB-48: one synthetic project from an accepted quotation to handover, through every gate the instruction
names, with the commercial baseline B1 -> V1 -> B2 kept reproducible and untouched by operational work.

SYNTHETIC data and a SYNTHETIC lifecycle policy only (the shipped policy record stays undecided). The scenario follows
the instruction's order step by step; each refusal is asserted with its exact blocker codes.
"""

from __future__ import annotations

import hashlib

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok
from tests.support.mtq import photo
from tests.support.project import BASE, ON, Projects, install, synthetic_policy
from veda.kernel import db
from veda.kernel.jcs import canonical_bytes
from veda.modules.mtq_commercial.models import Quotation, QuotationLine
from veda.modules.project import baseline as project_baseline
from veda.modules.project.models import ProjectBaseline, ProjectEvent, ProjectTransition

pytestmark = ON


def _blockers(r: dict) -> set[str]:
    return {b["code"] for b in r["transition"]["blockers"]}


def _commercial_state(number: str) -> list[tuple]:
    """Every version of the chain, as stored: status, amounts, digests and line amounts."""
    with db.unit_of_work(write=False) as s:
        out = []
        for q in s.execute(sa.select(Quotation).where(Quotation.quotation_number == number)
                           .order_by(Quotation.variation_no, Quotation.version_no)).scalars():  # fmt: skip
            lines = s.execute(sa.select(QuotationLine.amount_minor).where(QuotationLine.quotation_id == q.id)
                              .order_by(QuotationLine.position)).scalars().all()  # fmt: skip
            out.append((q.id, q.status, q.total_minor, q.accepted_total_minor, q.snapshot_sha256,
                        q.accepted_baseline_sha256, tuple(lines)))  # fmt: skip
        return out


def test_plb_47_48_synthetic_project_from_acceptance_to_handover(api, factory):
    t = Projects(api, factory)
    install(synthetic_policy())  # four-eyes on SNAGGING>READY_FOR_HANDOVER
    try:
        _scenario(t)
    finally:
        install(None)


def _scenario(t: Projects) -> None:
    # --- accepted synthetic quotation Q1 -> project P1 ------------------------------------------------------------------
    prop, _, q1 = t.accepted()
    b1_quotation = _commercial_state(q1["quotation_number"])
    p = t.book(q1, prop)
    assert p["stage"]["code"] == "BOOKED" and p["lifecycle"]["status"] == "APPROVED"  # the synthetic PLB-OD-01
    b1 = p["baseline"]["lineage"][0]
    assert b1["kind"] == "ORIGINAL" and b1["quotation_id"] == q1["id"]

    # --- owners assigned; BOOKED -> DESIGN_FINALISATION ------------------------------------------------------------------
    p = t.staff(p)
    assert {m["responsibility"] for m in p["team"] if m["active"]} == {"PROJECT", "SITE", "QUALITY", "HANDOVER",
                                                                       "DESIGN", "MEMBER", "COMMERCIAL"}  # fmt: skip
    p = t.advance(p, "DESIGN_FINALISATION")

    # --- try the next move early: refused with the exact missing gate -----------------------------------------------------
    r = t.transition(p, "SCOPE_FROZEN")
    assert r["outcome"] == "REFUSED" and _blockers(r) == {"CHECKLIST_ITEM_OPEN"}
    assert len(r["transition"]["blockers"]) == 3  # the three design-finalisation items, named
    t.checklist(p, user=t.designer)  # the design owner completes the synthetic checklist
    p = t.transition(p, "SCOPE_FROZEN")["project"]
    assert p["stage"]["code"] == "SCOPE_FROZEN"

    # --- a site-readiness issue: SITE_READINESS blocked, progression refused -----------------------------------------------
    p = t.advance(p, "SITE_READINESS")
    d = ok(t.as_(t.surveyor).post(f"{BASE}/{p['id']}/site-readiness", {"kind": "RESPONSIBILITY",
                                  "category": "APPLIANCE_MODEL", "label": "Hob and chimney models"}), 201)  # fmt: skip
    item = d["site_readiness"][0]
    d = ok(t.as_(t.surveyor).patch(f"{BASE}/{p['id']}/site-readiness/{item['id']}", {
        "status": "CUSTOMER_ACTION_REQUIRED", "action": "Customer to confirm appliance models",
        "customer_action": "Please share the hob and chimney models"}, if_match=item["version"]))  # fmt: skip
    assert d["site_readiness_state"] == "BLOCKED"
    t.checklist(p)
    r = t.transition(p, "PRODUCTION_READINESS")
    assert r["outcome"] == "REFUSED" and _blockers(r) == {"SITE_CUSTOMER_ACTION_REQUIRED"}
    assert r["transition"]["blockers"][0]["responsible_party"] == "CUSTOMER"
    # the customer acts; the Veda team records it
    item = t.get(p)["site_readiness"][0]
    ok(t.as_(t.surveyor).patch(f"{BASE}/{p['id']}/site-readiness/{item['id']}", {"status": "READY",
                               "note": "Models received"}, if_match=item["version"]))  # fmt: skip
    p = t.transition(p, "PRODUCTION_READINESS")["project"]
    assert p["stage"]["code"] == "PRODUCTION_READINESS"

    # --- an unresolved variation stops the production release -------------------------------------------------------------
    v1 = t.variation(q1, prop)
    t.checklist(p)
    r = t.transition(p, "IN_PRODUCTION")
    assert r["outcome"] == "REFUSED" and _blockers(r) == {"VARIATION_OPEN"}
    before_v1 = [e for e in t.get(p)["timeline"]]
    v1 = t.accept_variation(v1)  # through the existing commercial route (B4 decision service)
    p = t.get(p)
    lineage = p["baseline"]["lineage"]
    assert [(x["kind"], x["quotation_id"]) for x in lineage] == [("ORIGINAL", q1["id"]), ("VARIATION", v1["id"])]
    assert lineage[1]["current"] is True and p["baseline"]["current_seq"] == 2 and p["baseline"]["verified"]
    assert p["timeline"][: len(before_v1)] == before_v1  # history before V1 is not rewritten
    assert p["timeline"][len(before_v1)]["code"] == "VARIATION_ACCEPTED"
    p = t.transition(p, "IN_PRODUCTION")["project"]
    p = t.advance(p, "READY_FOR_INSTALLATION")

    # --- a gating site blocker stops installation -------------------------------------------------------------------------
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers", {"category": "ACCESS", "impact": "GATING",
                         "title": "Society has not approved working hours", "responsible_party": "THIRD_PARTY",
                         "blocks_stage_code": "INSTALLATION"}), 201)  # fmt: skip
    t.checklist(p)
    r = t.transition(p, "INSTALLATION")
    assert r["outcome"] == "REFUSED" and _blockers(r) == {"GATING_BLOCKER_OPEN"}
    b = t.get(p)["blockers"][0]
    ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/blockers/{b['id']}/resolve", {"resolution": "Approval letter received"},
                         if_match=b["version"]))  # fmt: skip
    p = t.transition(p, "INSTALLATION")["project"]
    p = t.advance(p, "QUALITY_CHECK")

    # --- a QC failure: handover readiness refused; a snag fixed and rechecked ---------------------------------------------
    api = t.as_(t.ops)
    d = ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "FAIL",
                                                   "observation": "Laminate scratch on the kitchen tall unit"}), 201)  # fmt: skip
    failed = d["qc"]["history"][0]
    ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "DIMENSIONS_AND_ALIGNMENT", "result": "PASS"}), 201)
    p = t.advance(p, "SNAGGING")
    t.checklist(p)
    r = t.transition(p, "READY_FOR_HANDOVER")
    assert r["outcome"] == "REFUSED" and _blockers(r) == {"QC_FAILED"}
    d = ok(api.post(f"{BASE}/{p['id']}/snags", {"category": "FINISH", "customer_title": "Scratch on the tall unit",
                                               "qc_check_id": failed["id"], "owner_user_id": t.ops.id}), 201)  # fmt: skip
    snag = d["snags"][0]
    assert {b["code"] for b in t.transition(p, "READY_FOR_HANDOVER")["transition"]["blockers"]} == {"QC_FAILED",
                                                                                                  "SNAG_OPEN"}  # fmt: skip
    url = f"{BASE}/{p['id']}/snags/{snag['id']}"
    for status, note in (("IN_PROGRESS", None), ("READY_FOR_RECHECK", None), ("RESOLVED", "Panel replaced; rechecked")):
        cur = next(x for x in t.get(p)["snags"] if x["id"] == snag["id"])
        ok(api.post(f"{url}/status", {"status": status, **({"note": note} if note else {})}, if_match=cur["version"]))
    ok(api.post(f"{BASE}/{p['id']}/qc-checks", {"category": "FINISH_AND_SURFACES", "result": "PASS",
                                               "recheck_of_id": failed["id"]}), 201)  # fmt: skip
    r = t.transition(p, "READY_FOR_HANDOVER")  # HIGH risk with four-eyes in the synthetic policy
    assert r["outcome"] == "AWAITING_APPROVAL"
    tr = r["transition"]
    assert (
        t.as_(t.ops).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/approve", {}, if_match=tr["version"]).status == 403
    )
    p = ok(t.as_(t.approver).post(f"{BASE}/{p['id']}/transitions/{tr['id']}/approve", {}, if_match=tr["version"]))[
        "project"
    ]
    assert p["stage"]["code"] == "READY_FOR_HANDOVER" and p["handover_readiness"]["ready"] is True

    # --- duplicate / concurrent handover: only one succeeds ----------------------------------------------------------------
    t.checklist(p)
    att = photo(t.as_(t.founder), "property", prop["id"])
    body = {"handover_on": "2026-10-15", "acknowledgement_reference": "SYNTHETIC-HS-1", "evidence_attachment_id": att["id"],
            "observations": "Customer noted a spare hinge to be delivered"}  # fmt: skip
    version = t.get(p)["version"]
    first = t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=version)
    second = t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=version)
    assert first.status == 201 and first.data["outcome"] == "COMPLETED"
    assert second.status == 409 and second.code in ("PROJECT_HANDED_OVER", "VERSION_CONFLICT")
    p = t.get(p)
    assert p["status"] == "HANDED_OVER"

    # --- immutable timeline and project history -----------------------------------------------------------------------------
    codes = [e["code"] for e in p["timeline"]]
    assert codes[0] == "PROJECT_CREATED" and codes[-1] == "HANDED_OVER" and codes.count("HANDED_OVER") == 1
    entered = [e["stage_code"] for e in p["timeline"] if e["code"] == "STAGE_ENTERED"]
    assert entered == ["DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS", "PRODUCTION_READINESS",
                       "IN_PRODUCTION", "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK", "SNAGGING",
                       "READY_FOR_HANDOVER", "HANDED_OVER"]  # fmt: skip
    refused = {e["detail"]["transition_id"] for e in p["timeline"] if e["code"] == "TRANSITION_REFUSED"}
    assert len(refused) >= 5 and all(t_["outcome"] == "REFUSED" for t_ in p["transitions"] if t_["id"] in refused)
    rows = dbh.rows(sa.select(ProjectTransition))
    assert all(hashlib.sha256(canonical_bytes(r.evaluation)).hexdigest() == r.evaluation_sha256 for r in rows)
    events = dbh.rows(sa.select(ProjectEvent))
    assert all(e.version == 1 and not e.is_deleted for e in events)

    # --- PLB-48: B1 -> V1 -> B2, reproducible; no operational step changed a price ----------------------------------------
    after = _commercial_state(q1["quotation_number"])
    assert after[: len(b1_quotation)] == b1_quotation  # the original accepted quotation is exactly as accepted
    with db.unit_of_work(write=False) as s:
        chain = s.execute(sa.select(ProjectBaseline).order_by(ProjectBaseline.sequence_no)).scalars().all()
        assert [r.kind for r in chain] == ["ORIGINAL", "VARIATION"]
        previous = None
        for r in chain:  # each reference reproduces its digest from what is stored, chained to the previous one
            assert project_baseline.digest(r, previous) == r.baseline_sha256
            q = s.get(Quotation, r.quotation_id)
            assert q.status == "ACCEPTED" and q.snapshot_sha256 == r.snapshot_sha256
            assert hashlib.sha256(canonical_bytes(q.accepted_baseline)).hexdigest() == r.accepted_baseline_sha256
            previous = r.baseline_sha256
        assert chain[1].cumulative_value_minor == chain[0].accepted_total_minor + chain[1].accepted_total_minor
    assert p["baseline"]["verified"] is True and p["baseline"]["current_seq"] == 2
    handed = next(e for e in p["timeline"] if e["code"] == "HANDED_OVER")
    assert handed["detail"]["baseline_seq"] == 2  # handed over against the effective baseline B2
    v1_after = next(x for x in after if x[0] == v1["id"])
    assert v1_after[1] == "ACCEPTED" and v1_after[3] == v1["decision"]["accepted_total_minor"]
