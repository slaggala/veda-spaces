"""Project Commercials: the authoritative baseline and the payment schedule (PCM-001 … PCM-008). SYNTHETIC data only.

The record starts only from an accepted base quotation, references its frozen digests, never changes when pricing
changes, and its first schedule splits the accepted value (optional items included) by the frozen milestone shares so
that it always adds up exactly. An accepted variation is appended in the acceptance transaction; the schedule then
asks for revision, and a revision must add up to the new value.
"""

from __future__ import annotations

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok, step
from tests.support.commercials import BASE, ON, Commercials, amounts
from veda.modules.commercials import money
from veda.modules.commercials.models import CommercialBaseline, PaymentSchedule
from veda.modules.mtq_commercial.models import Quotation

pytestmark = ON


def test_opening_from_an_accepted_quotation_references_its_frozen_commitment(api, factory):
    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    frozen = dbh.get(Quotation, q["id"])
    assert acc["quotation_number"] == q["quotation_number"] and acc["base_quotation"]["id"] == q["id"]
    assert acc["position"]["value_minor"] == frozen.accepted_total_minor
    assert acc["position"]["outstanding_minor"] == frozen.accepted_total_minor and acc["position"]["paid_minor"] == 0
    assert acc["position"]["tax_minor"] == frozen.tax_minor  # the frozen GST, never recomputed
    (b,) = acc["baseline"]
    assert b["kind"] == "ORIGINAL" and b["snapshot_sha256"] == frozen.snapshot_sha256
    assert acc["problems"] == [] and acc["capabilities"]["writable"] is True
    # revision 1 from the frozen milestones: 10 / 50 / 40 of the accepted value, adding up exactly
    lines = acc["schedule"]["lines"]
    assert [x["label"] for x in lines] == ["Booking", "Production", "Handover"]
    assert [x["when"] for x in lines] == [m["trigger"] for m in frozen.terms["payment_milestones"]]
    assert amounts(acc) == money.by_shares(frozen.accepted_total_minor, [1000, 5000, 4000])
    assert sum(amounts(acc)) == acc["position"]["value_minor"] and acc["position"]["schedule_state"] == "IN_BALANCE"
    assert sum(x["gst_included"] is not None for x in lines) == 3
    assert sum(int(money.parse_rupees(x["gst_included"])) for x in lines) == frozen.tax_minor
    assert all(x["state"] == "UPCOMING" and x["due_on"] is None for x in lines)  # no due date is invented
    # it is listed, and the quotation is no longer a candidate
    assert [a["id"] for a in ok(t.call("GET", BASE))] == [acc["id"]]
    assert q["id"] not in {c["quotation_id"] for c in ok(t.call("GET", f"{BASE}/candidates"))}


def test_only_an_accepted_base_quotation_opens_and_only_once(api, factory):
    t = Commercials(api, factory)
    _, _, draft = t.quotation()
    r = t.open(draft, status=409)
    assert r.code == "QUOTATION_NOT_ACCEPTED"
    _, _, issued = t.issued("3BHK")
    assert t.open(issued, status=409).code == "QUOTATION_NOT_ACCEPTED"
    prop, q, acc = t.opened("4BHK")
    again = t.open(q, status=409)
    assert again.code == "ALREADY_OPEN" and again.json["account_id"] == acc["id"]
    assert len(dbh.rows(sa.select(CommercialBaseline).where(CommercialBaseline.account_id == acc["id"]))) == 1
    r = t.call("POST", BASE, {"quotation_id": "0" * 32})
    assert r.status == 422


def test_optional_items_the_customer_chose_are_part_of_the_value_and_the_schedule(api, factory):
    t = Commercials(api, factory)
    prop, _, q = t.quotation("2BHK", optional="ACCEPTED")
    step(t.c, q, "submit", t.c.estimator)
    step(t.c, q, "approve", t.c.manager)
    q = ok(step(t.c, q, "issue", t.c.manager))
    opt = [x for sec in q["sections"] for x in sec["lines"] if x["is_optional"] and x["is_priced"]]
    assert opt, "the synthetic site offers a priced optional item"
    q = ok(step(t.c, q, "decision", t.c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY",
                                                "selected_optional_line_ids": [opt[0]["id"]]}))  # fmt: skip
    acc = t.open(q)
    accepted = q["decision"]["accepted_total_minor"]
    assert accepted > q["total_minor"] and acc["position"]["value_minor"] == accepted
    assert acc["position"]["tax_minor"] == q["tax_minor"] + opt[0]["tax_minor"]
    assert sum(amounts(acc)) == accepted  # the shares split the accepted value, not the printed milestone amounts


def test_the_baseline_never_follows_later_pricing(api, factory):
    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    value = acc["position"]["value_minor"]
    # a new estimate for the same property (pricing moved on): the accepted commitment does not change
    t.changed_estimate(prop)
    again = t.get(acc)
    assert again["position"]["value_minor"] == value and again["baseline"] == acc["baseline"]
    assert amounts(again) == amounts(acc)


def test_an_accepted_variation_becomes_the_next_baseline_and_the_schedule_must_be_revised(api, factory):
    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    v = t.accept_variation(t.variation(q, prop))
    after = t.get(acc)
    delta = v["decision"]["accepted_total_minor"]
    assert [b["kind"] for b in after["baseline"]] == ["ORIGINAL", "VARIATION"]
    assert after["position"]["value_minor"] == acc["position"]["value_minor"] + delta
    assert after["position"]["schedule_state"] == "REVISION_REQUIRED" and after["position"]["unscheduled_minor"] == delta
    assert after["problems"] == []
    # a revision must add up exactly to the new value
    lines = [{"label": x["label"], "when": x["when"], "amount_minor": x["amount_minor"]} for x in after["schedule"]["lines"]]
    r = t.revise(acc, lines, status=422)
    assert r.code == "VALIDATION_FAILED" and r.json["errors"][0]["code"] == "TOTAL_MISMATCH"
    revised = t.revise(acc, lines + [{"label": "Variation 1", "when": "On approval of the variation (synthetic)",
                                      "amount_minor": delta}], reason="Add the accepted variation")  # fmt: skip
    assert revised["position"]["schedule_state"] == "IN_BALANCE"
    assert sum(amounts(revised)) == revised["position"]["value_minor"]
    assert [r_["revision_no"] for r_ in revised["revisions"]] == [2, 1]
    assert dbh.rows(sa.select(PaymentSchedule.status).order_by(PaymentSchedule.revision_no)) == ["SUPERSEDED", "CURRENT"]


def test_a_schedule_revision_needs_a_reason_the_current_version_and_whole_paise(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    total = acc["position"]["value_minor"]
    cur = t.get(acc)
    body = {"reason": "Two equal parts", "instalments": [{"label": "A", "when": "Now", "amount_minor": total - total // 2},
                                                          {"label": "B", "when": "Later", "amount_minor": total // 2}]}
    assert t.call("POST", f"{BASE}/{acc['id']}/schedule", body).status == 428  # no If-Match
    assert t.call("POST", f"{BASE}/{acc['id']}/schedule", body, if_match=cur["version"] + 7).status == 409
    for bad in (1.5, "100", True, 0, -5):
        wrong = {**body, "instalments": [{"label": "A", "when": "Now", "amount_minor": bad}]}
        assert t.call("POST", f"{BASE}/{acc['id']}/schedule", wrong, if_match=cur["version"]).status == 422, bad
    assert t.call("POST", f"{BASE}/{acc['id']}/schedule", {**body, "reason": ""}, if_match=cur["version"]).status == 422
    ok_ = t.revise(acc, body["instalments"], reason="Two equal parts")
    assert amounts(ok_) == [total - total // 2, total // 2]


def test_a_payment_request_sets_due_and_a_past_due_date_is_refused(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    first = acc["schedule"]["lines"][0]
    assert t.request(acc, first["id"], "2000-01-01", status=422).code == "VALIDATION_FAILED"
    after = t.request(acc, first["id"])
    line = after["schedule"]["lines"][0]
    assert line["state"] == "DUE" and line["requested_on"] and line["due_on"] is None
    later = t.request(acc, first["id"], "2999-12-31")
    assert later["schedule"]["lines"][0]["due_on"] == "2999-12-31"


def test_commercials_work_with_the_project_lifecycle_off(api, factory, app):
    from veda.config import settings

    assert settings().project_lifecycle_enabled is False
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    assert t.pay(acc, 1000)["position"]["paid_minor"] == 1000
    assert api.get("/api/v1/projects", token=t.tok(t.founder)).status == 404  # still off
