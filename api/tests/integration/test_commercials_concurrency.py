"""Project Commercials concurrency (PCM-040): financial writes on one account run one after the other and each decides
on committed state, on SQLite and PostgreSQL. Each race holds the first request right after its permission check
(before the account lock) while the second runs, through the paused-request harness: no fixed waits, no retries.
SYNTHETIC data only."""

from __future__ import annotations

import sqlalchemy as sa

from tests.support import dbh
from tests.support.api import ApiClient
from tests.support.commercials import BASE, ON, Commercials, invoice_policy, key  # noqa: F401  (fixture)
from tests.support.project import race
from veda.kernel import clock
from veda.modules.commercials import access
from veda.modules.commercials.models import CommercialInvoice, CommercialPayment, CommercialReceipt

pytestmark = ON


def _body(amount: int) -> dict:
    return {"amount_minor": amount, "received_on": clock.now().date().isoformat(), "method_code": "BANK_TRANSFER"}


def test_the_same_payment_submitted_twice_at_once_is_recorded_once(api, app, factory, monkeypatch):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    k = key()
    path = f"{BASE}/{acc['id']}/payments"
    other = ApiClient(app.test_client())
    tok = t.tok(t.accountant)
    first, second = race(app, monkeypatch, tok, lambda c: c.post(path, _body(7000), headers={"Idempotency-Key": k}),
                         lambda: other.post(path, _body(7000), token=tok, headers={"Idempotency-Key": k}),
                         module=access, name="require")  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 201], (first, second)
    assert first.data["payment_id"] == second.data["payment_id"]
    assert len(dbh.rows(sa.select(CommercialPayment.id))) == 1 and len(dbh.rows(sa.select(CommercialReceipt.id))) == 1
    assert t.get(acc)["position"]["paid_minor"] == 7000


def test_two_payments_that_together_exceed_the_balance_cannot_both_be_recorded(api, app, factory, monkeypatch):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    share = acc["position"]["outstanding_minor"] * 6 // 10
    path = f"{BASE}/{acc['id']}/payments"
    other = ApiClient(app.test_client())
    tok, tok2 = t.tok(t.accountant), t.tok(t.second_accountant)
    first, second = race(app, monkeypatch, tok, lambda c: c.post(path, _body(share), headers={"Idempotency-Key": key()}),
                         lambda: other.post(path, _body(share), token=tok2, headers={"Idempotency-Key": key()}),
                         module=access, name="require")  # fmt: skip
    assert sorted((first.status, second.status)) == [201, 409], (first, second)
    assert (first if first.status == 409 else second).code == "OVERPAYMENT"
    after = t.get(acc)["position"]
    assert after["paid_minor"] == share and after["outstanding_minor"] == acc["position"]["value_minor"] - share


def test_two_invoices_issued_at_once_get_distinct_consecutive_numbers(api, app, factory, monkeypatch, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    l1, l2 = acc["schedule"]["lines"][:2]
    d1, d2 = t.draft(acc, l1["id"]), t.draft(acc, l2["id"])
    other = ApiClient(app.test_client())
    tok = t.tok(t.accountant)
    first, second = race(
        app, monkeypatch, tok,
        lambda c: c.post(f"/api/v1/commercial-invoices/{d1['id']}/issue", {}, if_match=d1["version"]),
        lambda: other.post(f"/api/v1/commercial-invoices/{d2['id']}/issue", {}, token=tok, if_match=d2["version"]),
        module=access, name="require",
    )  # fmt: skip
    assert first.status == second.status == 200, (first, second)
    numbers = sorted(dbh.rows(sa.select(CommercialInvoice.invoice_number)))
    assert len(set(numbers)) == 2 and [int(n[-5:]) for n in numbers] == [1, 2]


def test_one_invoice_issued_twice_at_once_is_issued_once(api, app, factory, monkeypatch, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    d = t.draft(acc, acc["schedule"]["lines"][0]["id"])
    other = ApiClient(app.test_client())
    tok = t.tok(t.accountant)
    path = f"/api/v1/commercial-invoices/{d['id']}/issue"
    first, second = race(app, monkeypatch, tok, lambda c: c.post(path, {}, if_match=d["version"]),
                         lambda: other.post(path, {}, token=tok, if_match=d["version"]),
                         module=access, name="require")  # fmt: skip
    assert sorted((first.status, second.status)) == [200, 409], (first, second)
    assert len([n for n in dbh.rows(sa.select(CommercialInvoice.invoice_number)) if n]) == 1
