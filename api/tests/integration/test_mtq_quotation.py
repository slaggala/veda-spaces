"""MTQ B4 quotations: model, lifecycle, customer document, numbering, lineage, issuance blockers.

SYNTHETIC: synthetic sites, the synthetic rate card and, where a test needs decided owner policy to reach issue, the
SYNTHETIC test policy (refused outside tests). Results are SYNTHETIC_VALIDATED only."""

from __future__ import annotations

import re
import threading
from datetime import timedelta

import sqlalchemy as sa

from tests.support.commercial import (
    ALL_ON,
    Commercial,
    approved_estimate,
    install_full_policy,
    load_card,
    ok,
    step,
)
from veda.kernel import clock, db, sequences
from veda.kernel.context import actor, system_context

pytestmark = ALL_ON
INTERNAL_MARKERS = ("SYNTHETIC-2", "rate_card", "rate_minor", "derivation", "provenance", "card basis", "OI-MTQ",
                    "approved_by", "self_limit", "margin_bp", "cost_minor", "WARDROBE.BODY")  # fmt: skip


def _create(c: Commercial, est: dict, user=None):
    return c.as_(user or c.estimator).post(
        f"/api/v1/cost-estimates/{est['id']}/quotations", {"cover_note": "Thank you"}
    )


def test_drafted_but_never_issued_while_owner_decisions_are_missing(api, factory):
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, "3BHK")
    q = ok(_create(c, est), 201)
    assert q["status"] == "DRAFT" and q["version_no"] == 1 and q["quotation_number"].startswith("VS-Q-")
    assert (
        q["lineage"]["cost_estimate_id"] == est["id"]
        and q["lineage"]["measurement_set_id"] == est["measurement_set_id"]
    )
    assert q["lineage"]["boq_revision_no"] == est["boq_revision_no"] and q["lineage"]["scope_revision_no"] >= 1
    titles = [sec["title"] for sec in q["sections"]]
    assert "Kitchen" in titles and "Project-wide" in titles and titles[-1] == "Optional items"
    codes = {(b["code"], b.get("decision")) for b in q["blockers"]}
    assert ("GST_POLICY_REQUIRED", "OI-MTQ-07") in codes and ("RULESET_NOT_APPROVED", "OI-MTQ-03") in codes
    for code in ("OI-MTQ-08", "OI-MTQ-09", "OI-MTQ-11"):
        assert ("OWNER_DECISION_REQUIRED", code) in codes
    assert q["customer_issuable"] is False and q["total_minor"] is None
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    r = step(c, q, "issue", c.manager, code=409)
    assert r.code == "NOT_CUSTOMER_ISSUABLE"
    doc = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    assert doc["document"]["draft"]["watermark"].startswith("DRAFT") and "GST" in doc["html"]
    assert (
        doc["document"]["summary"]["gst"]["status"] == "To be confirmed" and doc["document"]["summary"]["total"] is None
    )
    customer_part = re.sub(r"<div class='draft'.*?</div>", "", doc["html"], flags=re.S)  # the staff-only draft note
    for marker in INTERNAL_MARKERS:
        assert marker not in customer_part, marker


def test_issue_freeze_accept_with_optional_items(api, factory):
    install_full_policy()  # SYNTHETIC decisions only
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, "2BHK")
    q = ok(_create(c, est), 201)
    assert q["blockers"] == [] and q["customer_issuable"] is True and q["total_minor"] > 0
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    q = ok(step(c, q, "issue", c.sales))
    assert q["status"] == "ISSUED" and q["snapshot_verified"] is True and len(q["snapshot_sha256"]) == 64
    assert q["valid_until"] == (clock.now().date() + timedelta(days=30)).isoformat()
    lead = ok(c.as_(c.sales).get(f"/api/v1/leads/{prop['lead_id']}"))
    assert lead["status"] == "QUOTATION_SENT"
    from tests.support import dbh
    from veda.modules.crm.leads.models import Lead

    assert dbh.get(Lead, prop["lead_id"]).quoted_amount_minor == q["total_minor"]
    # frozen: no edit, the document is the stored snapshot
    r = c.as_(c.estimator).patch(f"/api/v1/quotations/{q['id']}", {"title": "Changed"}, if_match=q["version"])
    assert r.status == 409 and r.code == "QUOTATION_FROZEN"
    rendered = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))
    doc = rendered["document"]
    assert rendered["snapshot_verified"] is True and rendered["template_version"] == "mtq-quotation-html/1"
    assert "draft" not in doc and doc["payment_schedule"] and doc["customer"]["name"]  # identity frozen at issue
    assert doc["summary"]["gst"]["status"] == "Included"
    html = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/document"))["html"]
    for marker in INTERNAL_MARKERS:
        assert marker not in html and marker not in str(doc), marker
    optional = [x for sec in q["sections"] for x in sec["lines"] if x["is_optional"] and x["is_priced"]]
    assert optional
    base_total = q["total_minor"]
    pick = optional[0]
    q = ok(step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY",
                                            "selected_optional_line_ids": [pick["id"]]}))  # fmt: skip
    extra = pick["amount_minor"] - pick["discount_minor"] + pick["tax_minor"]
    assert q["status"] == "ACCEPTED" and q["total_minor"] == base_total  # optional items never move the base total
    assert q["decision"]["accepted_total_minor"] == base_total + extra
    events = [e["event_code"] for e in q["events"]]
    assert events == ["CREATED", "SUBMITTED_FOR_REVIEW", "APPROVED", "ISSUED", "ACCEPTED"]


def test_revision_supersedes_and_history_stays_stable_after_a_rate_change(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, "2BHK")
    q1 = ok(_create(c, est), 201)
    step(c, q1, "submit", c.estimator)
    step(c, q1, "approve", c.manager)
    q1 = ok(step(c, q1, "issue", c.manager))

    def dearer(d):
        for p in d["products"]:
            for line in p["lines"]:
                line["rates"] = {k: v * 12 // 10 for k, v in line["rates"].items()}

    load_card(version="SYNTHETIC-4", mutate=dearer)
    again = ok(c.as_(c.manager).get(f"/api/v1/quotations/{q1['id']}"))
    assert again["snapshot_sha256"] == q1["snapshot_sha256"] and again["total_minor"] == q1["total_minor"]
    assert again["snapshot_verified"] is True
    # a new version needs a re-priced, approved estimate; the old one is stale against the new card
    r = step(c, q1, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=409)
    assert r.code == "ESTIMATE_STALE"
    # ... and the BOQ is rebuilt against the card now in force before it is re-priced (never mixed card contexts)
    r = c.as_(c.estimator).post(f"/api/v1/boqs/{est['boq_id']}/cost-estimates", {"tier_code": "ESSENTIAL"})
    assert r.status == 409 and r.code == "BOQ_STALE"
    boq2 = ok(c.review(c.boq(ok(c.as_(c.estimator).get(f"/api/v1/scopes/{est['scope_id']}")))))
    est2 = ok(c.as_(c.estimator).post(f"/api/v1/boqs/{boq2['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    est2 = ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est2['id']}/approve", if_match=est2["version"]))
    q2 = ok(step(c, q1, "versions", c.estimator, {"cost_estimate_id": est2["id"]}, code=201))
    assert (
        q2["version_no"] == 2
        and q2["quotation_number"] == q1["quotation_number"]
        and q2["total_minor"] > q1["total_minor"]
    )
    assert ok(c.as_(c.manager).get(f"/api/v1/quotations/{q1['id']}"))["status"] == "ISSUED"
    step(c, q2, "submit", c.estimator)
    step(c, q2, "approve", c.manager)
    ok(step(c, q2, "issue", c.manager))
    old = ok(c.as_(c.manager).get(f"/api/v1/quotations/{q1['id']}"))
    assert old["status"] == "SUPERSEDED" and old["snapshot_sha256"] == q1["snapshot_sha256"]
    r = step(c, old, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}, code=409)
    assert r.code in ("QUOTATION_FROZEN", "QUOTATION_SUPERSEDED")


def test_expired_quotation_cannot_be_accepted(api, factory):
    from veda.modules.mtq_commercial import quotations

    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est = approved_estimate(c, "2BHK")
    q = ok(_create(c, est), 201)
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    ok(step(c, q, "issue", c.manager))
    clock.advance(timedelta(days=31))
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        assert quotations.expire_due(s) == 1
    from veda.platform import maintenance

    assert maintenance.mtq_quotation_expiry() == {"expired": 0}  # the maintenance job runs the same rule, idempotently
    q = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}"))
    assert q["status"] == "EXPIRED"
    r = step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}, code=409)
    assert r.code == "QUOTATION_FROZEN"


def test_quotation_line_traces_back_to_the_measured_wall(api, factory):
    load_card()
    c = Commercial(api, factory)
    _, est = approved_estimate(c, "2BHK")
    q = ok(_create(c, est), 201)
    wardrobe = next(x for sec in q["sections"] for x in sec["lines"] if x["line_key"].endswith(":WARDROBE:BODY"))
    t = ok(c.as_(c.estimator).get(f"/api/v1/quotation-lines/{wardrobe['id']}/trace"))
    assert t["estimate_line"]["rate_card_version"] == "SYNTHETIC-2"
    assert t["boq_line"]["formula_kind"] == "CARD_AREA" and "W2" in t["boq_line"]["derivation"]
    assert t["scope_item"]["item_type_code"] == "WARDROBE" and t["requirement"]["source_code"] == "MEASUREMENT_RULE"
    assert t["measurement"]["measurement_set_id"] == est["measurement_set_id"]
    assert t["measurement"]["inputs"]["WIDTH"]["wall_index"] == 2 and t["measurement"]["inputs"]["WIDTH"]["wall_id"]


def test_least_privilege_and_four_eyes(api, factory):
    install_full_policy()
    load_card()
    c = Commercial(api, factory)
    _, est = approved_estimate(c, "2BHK")
    assert _create(c, est, user=c.designer).status == 403
    q = ok(_create(c, est, user=c.sales), 201)  # the sales owner of the lead prepares it
    step(c, q, "submit", c.sales)
    step(c, q, "approve", c.sales, code=403)
    step(c, q, "approve", c.estimator, code=403)
    ok(step(c, q, "approve", c.manager))
    assert c.as_(c.designer).get(f"/api/v1/quotations/{q['id']}").status == 403
    assert c.as_(c.ten.lead_surveyor).get(f"/api/v1/quotations/{q['id']}").status == 403


def test_concurrent_quotation_numbers_are_unique(app):
    numbers: list[str] = []
    errors: list[BaseException] = []

    def take():
        try:
            with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
                numbers.append(sequences.next_number(s, "QUOTATION"))
        except BaseException as err:  # noqa: BLE001  (reported below)
            errors.append(err)

    threads = [threading.Thread(target=take) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors and len(numbers) == 12 and len(set(numbers)) == 12
    assert all(n.startswith(f"VS-Q-{clock.now().year}-") for n in numbers)
    with db.engine().connect() as conn:
        assert (
            conn.execute(sa.text("SELECT count(*) FROM number_sequence WHERE sequence_key = 'QUOTATION'")).scalar() == 1
        )
