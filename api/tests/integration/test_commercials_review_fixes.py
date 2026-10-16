"""Project Commercials: regression tests for the independent review's findings (M1-M4, LOW 1-7). SYNTHETIC data only."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercial import ok, step
from tests.support.commercials import BASE, ON, SYNTHETIC_POLICY, Commercials, invoice_policy  # noqa: F401
from veda.kernel import clock
from veda.modules.commercials import policy
from veda.modules.commercials.models import CommercialPayment

pytestmark = ON


def test_m1_one_commercial_record_per_property(api, factory):
    t = Commercials(api, factory)
    prop, est, q1 = t.accepted()
    acc = t.open(q1)
    q2 = ok(t.c.as_(t.c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    step(t.c, q2, "submit", t.c.estimator)
    step(t.c, q2, "approve", t.c.manager)
    q2 = ok(step(t.c, q2, "issue", t.c.manager))
    q2 = ok(step(t.c, q2, "decision", t.c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}))
    assert q2["quotation_number"] != q1["quotation_number"]
    assert q2["id"] not in {c["quotation_id"] for c in ok(t.call("GET", f"{BASE}/candidates"))}
    r = t.open(q2, status=409)
    assert r.code == "PROPERTY_HAS_COMMERCIAL_RECORD" and r.json["account_id"] == acc["id"]


def test_m2_nothing_is_asked_or_invoiced_while_the_schedule_needs_revision(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    customer = t.invite(prop["lead_id"], "m2@example.test")
    line = acc["schedule"]["lines"][1]
    t.request(acc, line["id"])
    assert [a["kind"] for a in customer.property(prop["id"]).data["attention"]].count("PAYMENT_DUE") == 1
    t.accept_variation(t.variation(q, prop))
    after = t.get(acc)
    assert (
        after["position"]["schedule_state"] == "REVISION_REQUIRED" and after["position"]["next_instalment_id"] is None
    )
    assert t.request(acc, line["id"], status=409).code == "SCHEDULE_REVISION_REQUIRED"
    assert t.draft(acc, line["id"], status=409).code == "SCHEDULE_REVISION_REQUIRED"
    view = customer.property(prop["id"]).data
    assert not [a for a in view["attention"] if a["kind"] == "PAYMENT_DUE"]
    assert view["commercials"]["summary"]["next_payment"] is None
    assert [n["code"] for n in view["commercials"]["notices"]] == ["SCHEDULE_UPDATING"]
    assert t.pay(acc, 1000)["position"]["paid_minor"] == 1000  # money received is still recorded


def test_m3_dates_are_india_dates(api, factory):
    clock.set_clock(lambda: datetime(2026, 10, 16, 20, 30, tzinfo=UTC))  # 02:00 IST on 17 October
    try:
        t = Commercials(api, factory)
        _, _, acc = t.opened()
        out = t.pay(acc, 1000, received_on="2026-10-17", method_code="UPI")
        assert out["position"]["as_of"] == "2026-10-17"
        assert t.pay(acc, 1000, received_on="2026-10-18", status=422).code == "VALIDATION_FAILED"
    finally:
        clock.reset()


def test_m4_a_tax_invoice_title_is_refused_until_the_form_supports_it(app):
    doc = {
        **SYNTHETIC_POLICY,
        "decisions": {"PCM-D01": {**SYNTHETIC_POLICY["decisions"]["PCM-D01"], "document_title": "Tax invoice"}},
    }
    with pytest.raises(Exception):  # noqa: B017  (pydantic refuses the literal)
        policy.install_for_tests(doc)
    policy.install_for_tests(None)


def test_low1_low2_an_issued_invoice_owns_its_due_date_and_cancelling_drops_it(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    line = acc["schedule"]["lines"][0]
    inv = t.issued_invoice(acc, 1, due_on="2999-01-31")
    assert t.request(acc, line["id"], status=409).code == "INVOICE_FIXES_DUE_DATE"
    assert t.request(acc, line["id"], "2999-01-31")["schedule"]["lines"][0]["due_on"] == "2999-01-31"
    t.invoice_action(inv["id"], "cancel", {"reason": "Wrong instalment"})
    first = t.get(acc)["schedule"]["lines"][0]
    assert first["due_on"] is None and first["requested_on"] and first["state"] == "DUE"


def test_low3_the_invoiced_one_of_two_identical_instalments_is_carried(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    v = acc["position"]["value_minor"]
    half = v // 3
    acc = t.revise(acc, [{"label": "Part", "when": "Now", "amount_minor": half},
                         {"label": "Part", "when": "Now", "amount_minor": half},
                         {"label": "Rest", "when": "Later", "amount_minor": v - 2 * half}], reason="Equal parts")  # fmt: skip
    inv = t.issued_invoice(acc, 2)
    kept = t.revise(acc, [{"label": "Part", "when": "Now", "amount_minor": half},
                          {"label": "Rest", "when": "Later", "amount_minor": v - half}], reason="Merge two parts")  # fmt: skip
    assert kept["schedule"]["lines"][0]["invoice"]["id"] == inv["id"]


def test_low4_one_reference_is_one_payment_whatever_the_method(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    t.pay(acc, 1000, external_reference="UTR998877", method_code="BANK_TRANSFER")
    assert (
        t.pay(acc, 1000, external_reference="utr 998877", method_code="UPI", status=409).code
        == "DUPLICATE_PAYMENT_REFERENCE"
    )


def test_low7_erasure_replaces_the_request_digest_of_erased_text(api, factory):
    from tests.integration.test_commercials_erasure import _erase

    t = Commercials(api, factory)
    prop, _, acc = t.opened()
    out = t.pay(acc, 1000, external_reference="name@okbank")
    before = dbh.get(CommercialPayment, out["payment_id"]).request_sha256
    _erase(prop["lead_id"])
    row = dbh.get(CommercialPayment, out["payment_id"])
    assert row.request_sha256 != before and row.external_reference == "[erased]"
    assert len(dbh.rows(sa.select(CommercialPayment.id))) == 1
