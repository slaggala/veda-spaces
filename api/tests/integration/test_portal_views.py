"""Customer Project Portal views (CPP-004 … CPP-010): what the customer sees, from authoritative data only, in
customer terms, with nothing internal. SYNTHETIC data only."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok, step
from tests.support.portal import ON, Portal, keys
from tests.support.project import BASE as PROJECTS
from tests.support.project import install, synthetic_policy

pytestmark = ON
# Never in a customer response: internal economics, lineage, digests, internal states and staff fields.
FORBIDDEN = {"rate", "unit_cost", "cost", "margin", "markup", "cost_estimate_id", "estimate_id", "boq_id", "scope_id",
             "measurement_set_id", "estimate_snapshot_sha256", "snapshot_sha256", "accepted_baseline_sha256",
             "baseline_sha256", "policy_sha256", "created_by", "updated_by", "lead_id", "assigned_to", "blockers",
             "base_total_minor", "total_minor", "tier_code", "decision_note", "notes", "internal", "evaluation",
             "token", "token_sha256", "email_normalized", "phone_raw"}  # fmt: skip


def _steps(view: dict) -> dict[str, str]:
    return {s["key"]: s["state"] for s in view["journey"]}


def test_before_any_quotation_the_journey_shows_only_what_is_true(api, factory):
    t = Portal(api, factory)
    prop = t.c.site("2BHK")  # measured and verified; no scope, no quotation
    me = t.invite(prop["lead_id"], "early@example.test")
    view = ok(me.property(prop["id"]))
    steps = _steps(view)
    assert steps["consultation"] == "COMPLETED" and steps["site_measurement"] == "COMPLETED"
    assert steps["quotation"] == "UPCOMING" and steps["approval"] == "UPCOMING"
    assert [steps[k] for k in ("execution", "quality", "handover")] == ["NOT_YET_AVAILABLE"] * 3
    assert view["quotation"] is None and view["quotations"] == [] and view["documents"] == []
    assert view["commitments"] is None and view["included"] is None and view["attention"] == []
    assert view["project_tracking"] is False
    assert view["contact"] is None or view["contact"]["source"] == "CONSULTANT"


def test_an_issued_quotation_needs_the_customers_decision(api, factory):
    t = Portal(api, factory)
    prop, _, q = t.issued()
    me = t.invite(prop["lead_id"], "open@example.test")
    home = ok(me.home())
    card = home["enquiries"][0]["properties"][0]
    assert card["attention_count"] == 1 and card["headline"] == "We are waiting for your decision."
    assert card["next_step"]["key"] == "approval" and card["next_step"]["state"] == "ACTION_REQUIRED"
    view = ok(me.property(prop["id"]))
    assert _steps(view)["quotation"] == "COMPLETED" and _steps(view)["approval"] == "ACTION_REQUIRED"
    action = view["attention"][0]
    assert action["kind"] == "QUOTATION_DECISION" and action["status"] == "ACTION_REQUIRED"
    assert action["quotation_id"] == q["id"] and "secure proposal link" in action["text"]
    summary = view["quotation"]
    assert summary["state"] == "OPEN" and summary["status_label"] == "Awaiting your decision" and summary["total"]
    assert view["documents"][0]["id"] == q["id"] and view["included"]  # room by room, from the issued document
    page = ok(me.quotation(q["id"]))
    assert page["capabilities"] == {"interaction": False, "acceptance": False} and page["actions"] == []
    assert any(n["code"] == "DECIDE_BY_LINK" for n in page["notices"])
    from veda.kernel import db
    from veda.modules.customer_proposal import projection as cqx
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work(write=False) as s:
        assert page["proposal"] == cqx.build(s, s.get(Quotation, q["id"]))  # exactly the CQX customer projection


def test_after_acceptance_the_approval_is_complete_and_nothing_is_asked(api, factory):
    t = Portal(api, factory)
    prop, _, q = t.accepted()
    me = t.invite(prop["lead_id"], "won@example.test")
    view = ok(me.property(prop["id"]))
    assert _steps(view)["approval"] == "COMPLETED" and view["attention"] == []
    assert view["quotation"]["state"] == "ACCEPTED" and view["quotation"]["status"] == "COMPLETED"
    assert view["headline"] == "You have approved your quotation."
    assert [s["state"] for s in view["journey"][-3:]] == ["NOT_YET_AVAILABLE"] * 3  # Project Lifecycle is off


def test_no_internal_field_reaches_the_customer(api, factory):
    t = Portal(api, factory)
    prop, _, q = t.issued()
    me = t.invite(prop["lead_id"], "fields@example.test")
    for r, allowed in ((me.home(), set()), (me.property(prop["id"]), set()),
                       # the CQX projection carries the frozen document's digest (its acceptance binding)
                       (me.quotation(q["id"]), {"snapshot_sha256"})):  # fmt: skip
        body = ok(r)
        leaked = keys(body) & (FORBIDDEN - allowed)
        assert not leaked, leaked
        text = str(body)
        for staff in (t.c.sales, t.c.estimator, t.manager):
            assert staff.email not in text
        assert "fields@example.test" not in text  # not even the customer's own address is echoed


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                      customer_portal_enabled=True, project_lifecycle_enabled=True)  # fmt: skip
def test_with_the_project_lifecycle_on_progress_and_customer_actions_come_from_the_project(api, factory):
    t = Portal(api, factory)
    prop, _, q = t.accepted()
    me = t.invite(prop["lead_id"], "project@example.test")
    assert ok(me.property(prop["id"]))["project_tracking"] is False  # no project booked yet
    p = t.book(q, prop)
    t.staff(p)
    t.as_(t.ops).post(f"{PROJECTS}/{p['id']}/blockers", {"category": "CUSTOMER_DECISION", "impact": "GATING",
                      "title": "Appliance models (staff wording)", "description": "Internal note for the team",
                      "customer_action": "Please share your appliance models", "responsible_party": "CUSTOMER",
                      "blocks_stage_code": "DESIGN_FINALISATION"})  # fmt: skip
    view = ok(me.property(prop["id"]))
    assert view["project_tracking"] is True
    assert _steps(view)["execution"] == "IN_PROGRESS" and _steps(view)["handover"] == "UPCOMING"
    actions = [a for a in view["attention"] if a["kind"] == "PROJECT_ACTION"]
    assert [a["text"] for a in actions] == ["Please share your appliance models"]
    text = str(view)
    assert "staff wording" not in text
    assert "Internal note" not in text
    assert p["id"] not in text  # the project is described in customer terms, never by its internal record
    install(None)


def test_the_portal_never_changes_the_project_lifecycle_or_its_owner_policy(api, factory):
    from veda.config import settings
    from veda.modules.project import policy

    t = Portal(api, factory)
    prop, _, q = t.accepted()
    me = t.invite(prop["lead_id"], "flag@example.test")
    ok(me.home()), ok(me.property(prop["id"])), ok(me.quotation(q["id"]))
    assert settings().project_lifecycle_enabled is False
    assert all(v is None for v in policy.current().decisions.values())
    assert me.get("/api/v1/projects").status == 404
    assert me.call("POST", "/api/v1/projects", {"quotation_id": q["id"], "property_id": prop["id"]}).status == 404
    assert synthetic_policy is not None and step is not None  # harness imports used by sibling tests
