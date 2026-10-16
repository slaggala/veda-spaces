"""Project Commercials in the Customer Project Portal (PCM-014 … PCM-017). SYNTHETIC data only.

The customer sees the value, what is paid and outstanding, the next payment, the schedule, their payment history with
receipts and their issued invoices, and an Action Required item for a requested instalment, all from the one position
calculation and never with a staff note, an actor, an internal state or a way to pay. Customer A never reaches
customer B's commercial records, by any identifier, and a draft invoice is never a customer document.
"""

from __future__ import annotations

import pytest

from tests.support.commercials import ON, Commercials, invoice_policy  # noqa: F401  (fixture)
from tests.support.portal import PUBLIC, keys
from veda.modules.commercials import documents

pytestmark = ON
# Keys a customer view must never carry (staff notes, actors, internal states and economics).
INTERNAL_KEYS = {"internal_note", "recorded_by", "reversed_by", "requested_by", "issued_by", "cancelled_by",
                 "cancel_reason", "drafted_by", "created_by", "client_key_sha256", "request_sha256", "record_sha256",
                 "baseline_sha256", "reason_code", "applied_minor", "amount_minor", "value_minor", "rate_minor",
                 "margin", "cost", "internal_state", "lead_id", "account_id", "payment_id", "instalment_id"}  # fmt: skip


def _setup(t: Commercials, key: str = "2BHK", email: str = "a@example.test"):
    prop, q, acc = t.opened(key)
    customer = t.invite(prop["lead_id"], email)
    return prop, q, acc, customer


def test_the_customer_sees_the_position_schedule_history_and_documents(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, acc, customer = _setup(t)
    first, second, _ = acc["schedule"]["lines"]
    t.pay(acc, first["amount_minor"], external_reference="UTR-CUST-1", customer_note="Booking, thank you",
          internal_note="Customer was late; chased twice")  # fmt: skip
    t.request(t.get(acc), second["id"], "2999-03-31")
    inv = t.issued_invoice(acc, 2)
    view = customer.property(prop["id"]).data
    c = view["commercials"]
    pos = t.get(acc)["position"]
    assert c["available"] is True
    assert c["summary"]["total_value"] == pos["value"] and c["summary"]["paid"] == pos["paid"]
    assert c["summary"]["outstanding"] == pos["outstanding"]
    assert (
        c["summary"]["next_payment"]["label"] == "Production" and c["summary"]["next_payment"]["due_on"] == "2999-03-31"
    )
    assert [x["state"] for x in c["schedule"]] == ["PAID", "DUE", "UPCOMING"]
    assert [x["state_label"] for x in c["schedule"]] == ["Paid", "Due", "Upcoming"]
    (p,) = c["payments"]
    assert p["amount"] == documents.text(first["amount_minor"]) and p["method"] == "Bank transfer"
    assert (
        p["reference"] == "UTR-CUST-1"
        and p["note"] == "Booking, thank you"
        and p["receipt"]["number"].startswith("VS-R-")
    )
    assert [i["number"] for i in c["invoices"]] == [inv["number"]] and c["invoices"][0]["status"] == "DUE"
    # Action Required: the requested instalment, with no way to pay here
    due = [a for a in view["attention"] if a["kind"] == "PAYMENT_DUE"]
    assert len(due) == 1 and due[0]["status"] == "ACTION_REQUIRED" and due[0]["invoice_id"] == inv["id"]
    assert "Pay using the payment details" in due[0]["text"] and view["attention_count"] >= 1
    assert "pay_url" not in str(view).lower() and "checkout" not in str(view).lower()
    # documents: invoices and receipts next to the quotation
    kinds = [d["kind"] for d in view["documents"]]
    assert kinds[:2] == ["INVOICE", "RECEIPT"] and "QUOTATION" in kinds
    # nothing internal
    assert not (keys(c) & INTERNAL_KEYS), keys(c) & INTERNAL_KEYS
    assert "Customer was late" not in str(view)
    # the home card carries the outstanding amount and the next payment
    card = customer.home().data["enquiries"][0]["properties"][0]
    assert (
        card["payments"]["outstanding"] == pos["outstanding"]
        and card["payments"]["next_payment"]["label"] == "Production"
    )


def test_the_customer_opens_their_invoice_and_receipt_documents(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, acc, customer = _setup(t)
    paid = t.pay(acc, 2500, internal_note="staff only text")
    inv = t.issued_invoice(acc, 1)
    page = customer.get(f"{PUBLIC}/invoices/{inv['id']}").data
    assert page["kind"] == "INVOICE" and page["number"] == inv["number"] and page["document"] == inv["document"]
    assert page["html"].startswith("<!doctype html>") and page["filename"] == f"{inv['number']}.html"
    rec = customer.get(f"{PUBLIC}/receipts/{paid['receipt_id']}").data
    assert rec["kind"] == "RECEIPT" and rec["status"] == "VALID" and "staff only text" not in str(rec)
    # a reversed payment's receipt is shown as cancelled, in customer words
    t.reverse(acc, paid["payment_id"], "PAYMENT_RETURNED")
    rec = customer.get(f"{PUBLIC}/receipts/{paid['receipt_id']}").data
    assert rec["status"] == "CANCELLED" and "did not reach Veda Spaces" in rec["notices"][0]["message"]
    view = customer.property(prop["id"]).data["commercials"]
    assert view["payments"][0]["status"] == "CORRECTED" and view["payments"][0]["correction"]
    r = customer.get(f"{PUBLIC}/invoices/{inv['id']}")
    assert r.headers["Cache-Control"].startswith("no-store")


def test_customer_a_never_reaches_customer_b(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop_a, _, acc_a, a = _setup(t, "2BHK", "a@example.test")
    prop_b, _, acc_b, b = _setup(t, "3BHK", "b@example.test")
    pay_b = t.pay(acc_b, 1000)
    inv_b = t.issued_invoice(acc_b, 1)
    draft_a = t.draft(acc_a, acc_a["schedule"]["lines"][0]["id"])
    for r in (a.get(f"{PUBLIC}/invoices/{inv_b['id']}"), a.get(f"{PUBLIC}/receipts/{pay_b['receipt_id']}"),
              a.get(f"{PUBLIC}/invoices/{draft_a['id']}"),  # a draft is never a customer document, even one's own
              a.property(prop_b["id"])):  # fmt: skip
        assert r.status == 404 and r.code == "NOT_FOUND", r
    for guessed in ("00000000000070008000000000000001", acc_b["id"], pay_b["payment_id"], prop_b["id"]):
        assert a.get(f"{PUBLIC}/invoices/{guessed}").status == 404
        assert a.get(f"{PUBLIC}/receipts/{guessed}").status == 404
    for malformed in ("x" * 32, "1 OR 1=1"):
        assert a.get(f"{PUBLIC}/invoices/{malformed}").status in (404, 422)
    home = str(a.home().data) + str(a.property(prop_a["id"]).data)
    for secret in (inv_b["number"], inv_b["id"], pay_b["receipt_id"], acc_b["id"]):
        assert secret not in home
    # unauthenticated
    for path in (f"{PUBLIC}/invoices/{inv_b['id']}", f"{PUBLIC}/receipts/{pay_b['receipt_id']}"):
        r = api.get(path, anonymous=True)
        assert r.status == 401 and r.code == "PORTAL_SESSION_INVALID"
    # a staff token is never a portal session
    assert api.get(f"{PUBLIC}/invoices/{inv_b['id']}", token=t.tok(t.manager)).status == 401
    assert b.get(f"{PUBLIC}/invoices/{inv_b['id']}").status == 200


def test_revoked_access_closes_the_documents_at_once(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, acc, customer = _setup(t)
    inv = t.issued_invoice(acc, 1)
    assert customer.get(f"{PUBLIC}/invoices/{inv['id']}").status == 200
    (row,) = [x for x in t.access(prop["lead_id"]) if x["status"] == "ACTIVE"]
    assert t.as_(t.manager).post(f"/api/v1/portal-access/{row['id']}/revoke", {}, if_match=row["version"]).status == 200
    assert customer.get(f"{PUBLIC}/invoices/{inv['id']}").status in (401, 404)


def test_without_a_commercial_record_the_portal_says_so_and_invents_nothing(api, factory):
    t = Commercials(api, factory)
    prop, _, _ = t.accepted()
    customer = t.invite(prop["lead_id"], "c@example.test")
    view = customer.property(prop["id"]).data
    assert view["commercials"] is None and view["payments"] is None
    assert not [a for a in view["attention"] if a["kind"] == "PAYMENT_DUE"]


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                      customer_portal_enabled=True, project_commercials_enabled=False)  # fmt: skip
def test_with_the_feature_off_the_portal_shows_no_commercial_data(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, _ = t.accepted()
    customer = t.invite(prop["lead_id"], "d@example.test")
    view = customer.property(prop["id"]).data
    assert view["commercials"] is None and view["payments"] is None
    assert customer.get(f"{PUBLIC}/invoices/00000000000070008000000000000001").status == 404
    assert api.get("/api/v1/commercials", token=t.tok(t.manager)).status == 404


def test_an_unverifiable_record_is_not_shown_to_the_customer(api, factory):
    import sqlalchemy as sa

    from veda.kernel import db
    from veda.kernel.context import actor, system_context
    from veda.modules.commercials.models import CommercialPayment

    t = Commercials(api, factory)
    prop, _, acc, customer = _setup(t)
    out = t.pay(acc, 1000)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.execute(sa.update(CommercialPayment.__table__).where(CommercialPayment.__table__.c.id == out["payment_id"])
                  .values(amount_minor=999))  # fmt: skip
    c = customer.property(prop["id"]).data["commercials"]
    assert c == {"available": False, "message": c["message"]} and "not available" in c["message"]
    assert customer.get(f"{PUBLIC}/receipts/{out['receipt_id']}").status == 404
