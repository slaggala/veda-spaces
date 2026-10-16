"""Project Commercials: recorded payments, receipts and reversals (PCM-009 … PCM-013). SYNTHETIC data only.

A payment is staff's record of money received outside the system; it is applied to the schedule in order, can never
exceed the outstanding balance, is never recorded twice (database idempotency, duplicate references) and is never
rewritten: a correction is a reversal, by someone else, and the history shows both.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercials import BASE, ON, Commercials, key
from veda.kernel import clock, db
from veda.modules.commercials import documents
from veda.modules.commercials.models import (
    CommercialBaseline,
    CommercialEvent,
    CommercialPayment,
    CommercialReceipt,
)
from veda.platform.notifications.models import OutboxEvent

pytestmark = ON


def _lines(acc):
    return [(x["state"], x["applied_minor"], x["remaining_minor"]) for x in acc["schedule"]["lines"]]


def test_partial_and_full_payments_are_applied_in_order_and_the_balance_follows(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    a1, a2, a3 = (x["amount_minor"] for x in acc["schedule"]["lines"])
    value = acc["position"]["value_minor"]
    one = t.pay(acc, a1 - 100, external_reference="UTR 0001 synthetic")
    assert (
        _lines(one)[0] == ("PARTIALLY_PAID", a1 - 100, 100) and one["position"]["outstanding_minor"] == value - a1 + 100
    )
    two = t.pay(acc, 100 + a2 // 2, method_code="UPI")
    assert _lines(two)[:2] == [("PAID", a1, 0), ("PARTIALLY_PAID", a2 // 2, a2 - a2 // 2)]
    rest = value - two["position"]["paid_minor"]
    done = t.pay(acc, rest, method_code="CHEQUE", external_reference="CHQ 123456")
    assert [s for s, _, _ in _lines(done)] == ["PAID", "PAID", "PAID"]
    assert done["position"]["outstanding_minor"] == 0 and done["position"]["paid_minor"] == value
    assert done["position"]["next_instalment_id"] is None
    assert [p["status"] for p in done["payments"]] == ["RECORDED"] * 3
    # nothing more can be recorded: the balance never goes below zero by a payment
    r = t.pay(acc, 1, status=409)
    assert r.code == "OVERPAYMENT" and r.json["outstanding_minor"] == 0


def test_overpayment_is_refused_and_the_exact_balance_is_accepted(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    value = acc["position"]["value_minor"]
    assert t.pay(acc, value + 1, status=409).code == "OVERPAYMENT"
    assert t.pay(acc, value)["position"]["outstanding_minor"] == 0


def test_every_payment_issues_one_frozen_receipt_derived_from_it(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    a1 = acc["schedule"]["lines"][0]["amount_minor"]
    out = t.pay(
        acc, a1 + 500, external_reference="UTR-SYN-1", customer_note="Booking amount", internal_note="Staff only"
    )
    rc = dbh.get(CommercialReceipt, out["receipt_id"])
    year = clock.now().astimezone(__import__("zoneinfo").ZoneInfo("Asia/Kolkata")).year
    assert rc.receipt_number == f"VS-R-{year}-00001" and rc.amount_minor == a1 + 500
    assert documents.integrity(rc)
    doc = rc.snapshot
    assert doc["payment"]["amount"] == documents.text(a1 + 500) and doc["payment"]["reference"] == "UTR-SYN-1"
    assert doc["payment"]["method"] == "Bank transfer" and doc["payment"]["note"] == "Booking amount"
    assert [a["label"] for a in doc["applied_to"]] == ["Booking", "Production"]
    assert doc["position"]["outstanding"] == documents.text(out["position"]["outstanding_minor"])
    assert "Staff only" not in str(doc) and "Staff only" not in rc.document_html
    assert "does not collect payments" in doc["statement"]
    staff = t.call("GET", f"/api/v1/commercial-receipts/{rc.id}").data
    assert staff["status"] == "VALID" and staff["document"] == doc and staff["filename"] == f"{rc.receipt_number}.html"
    second = t.pay(acc, 100)
    assert dbh.get(CommercialReceipt, second["receipt_id"]).receipt_number == f"VS-R-{year}-00002"


def test_the_same_request_twice_records_one_payment_one_receipt_one_email(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    k = key()
    first = t.pay(acc, 5000, idem=k)
    again = t.pay(acc, 5000, idem=k, status=200)
    assert again["replayed"] is True and again["payment_id"] == first["payment_id"]
    assert again["receipt_id"] == first["receipt_id"] and again["position"]["paid_minor"] == 5000
    assert len(dbh.rows(sa.select(CommercialPayment.id))) == 1
    assert len(dbh.rows(sa.select(CommercialReceipt.id))) == 1
    assert len(dbh.rows(sa.select(OutboxEvent.id).where(OutboxEvent.event_type == "commercials.receipt_issued"))) == 1
    # the same key with a different request is refused, never applied
    r = t.pay(acc, 6000, idem=k, status=422)
    assert r.code == "IDEMPOTENCY_KEY_REUSED"
    # no key at all is refused: a financial write is always replay-safe
    from veda.kernel import clock as c

    body = {"amount_minor": 100, "received_on": c.now().date().isoformat(), "method_code": "CASH"}
    assert t.call("POST", f"{BASE}/{acc['id']}/payments", body).status == 422


def test_one_transfer_recorded_twice_by_two_people_is_refused(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    t.pay(acc, 1000, external_reference="UTR 7788 99")
    r = t.pay(acc, 1000, external_reference="utr778899", user=t.second_manager, status=409)
    assert r.code == "DUPLICATE_PAYMENT_REFERENCE"


def test_bad_amounts_and_dates_are_refused(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    tomorrow = (clock.now() + timedelta(days=2)).date().isoformat()
    assert t.pay(acc, 100, received_on=tomorrow, status=422).code == "VALIDATION_FAILED"
    for bad in (10.5, "100", True, 0, -1):
        body = {"amount_minor": bad, "received_on": clock.now().date().isoformat(), "method_code": "CASH"}
        r = t.call("POST", f"{BASE}/{acc['id']}/payments", body, headers={"Idempotency-Key": key()})
        assert r.status == 422, bad
    body = {"amount_minor": 100, "received_on": clock.now().date().isoformat(), "method_code": "CARD_GATEWAY"}
    assert t.call("POST", f"{BASE}/{acc['id']}/payments", body, headers={"Idempotency-Key": key()}).status == 422


def test_a_reversal_corrects_without_rewriting_and_needs_a_second_person(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    out = t.pay(acc, 9000, customer_note="Booking")
    pid = out["payment_id"]
    before = dbh.get(CommercialPayment, pid)
    snap = (before.amount_minor, before.received_on, before.method_code, before.version, before.record_sha256)
    r = t.reverse(acc, pid, user=t.manager, status=409)
    assert r.code == "FOUR_EYES_REQUIRED"
    assert t.reverse(acc, pid, "OTHER", status=422).code == "VALIDATION_FAILED"  # OTHER needs a note
    after = t.reverse(acc, pid, "DUPLICATE")
    assert (
        after["position"]["paid_minor"] == 0
        and after["position"]["outstanding_minor"] == acc["position"]["value_minor"]
    )
    (p,) = after["payments"]
    assert p["status"] == "REVERSED" and p["reversal"]["reason_code"] == "DUPLICATE" and p["amount_minor"] == 9000
    row = dbh.get(CommercialPayment, pid)  # the payment row itself never changed
    assert (row.amount_minor, row.received_on, row.method_code, row.version, row.record_sha256) == snap
    rc = t.call("GET", f"/api/v1/commercial-receipts/{p['receipt']['id']}").data
    assert rc["status"] == "CANCELLED" and rc["document"]["payment"]["amount"] == documents.text(9000)
    assert t.reverse(acc, pid, status=409).code == "ALREADY_REVERSED"
    codes = dbh.rows(sa.select(CommercialEvent.event_code))
    assert {"PAYMENT_RECORDED", "RECEIPT_ISSUED", "PAYMENT_REVERSED"} <= set(codes)
    # after the correction the right payment is recorded normally
    assert t.pay(acc, 9000)["position"]["paid_minor"] == 9000


def test_history_is_immutable_at_the_database(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    t.pay(acc, 100)
    from veda.kernel.context import actor, system_context

    for model in (CommercialEvent, CommercialBaseline):
        with pytest.raises(Exception), actor(system_context("CLI")), db.unit_of_work(write=True) as s:  # noqa: B017
            row = s.execute(sa.select(model).limit(1)).scalar_one()
            s.execute(sa.delete(model.__table__).where(model.__table__.c.id == row.id))
        with pytest.raises(Exception), actor(system_context("CLI")), db.unit_of_work(write=True) as s:  # noqa: B017
            row = s.execute(sa.select(model).limit(1)).scalar_one()
            s.execute(sa.update(model.__table__).where(model.__table__.c.id == row.id).values(updated_on=clock.now()))
    # no route edits or deletes a payment
    pid = t.get(acc)["payments"][0]["id"]
    for method in ("PUT", "PATCH", "DELETE"):
        assert t.call(method, f"{BASE}/{acc['id']}/payments/{pid}", {}).status in (404, 405)


def test_a_tampered_payment_or_baseline_stops_new_records(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    out = t.pay(acc, 100)
    from veda.kernel.context import actor, system_context

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        p = s.get(CommercialPayment, out["payment_id"])
        s.execute(sa.update(CommercialPayment.__table__).where(CommercialPayment.__table__.c.id == p.id)
                  .values(amount_minor=1))  # fmt: skip
    view = t.get(acc)
    assert [x["code"] for x in view["problems"]] == ["PAYMENT_TAMPERED"] and view["capabilities"]["writable"] is False
    r = t.pay(acc, 100, status=409)
    assert r.code == "COMMERCIAL_INTEGRITY_FAILED"
