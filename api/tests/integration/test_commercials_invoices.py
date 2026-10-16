"""Project Commercials: invoices (PCM-012). SYNTHETIC data only.

Draft (staff only) → issued (numbered, frozen, the instalment requested) → cancelled (the document stays). Issuing waits
for owner decision PCM-D01; one live invoice per instalment; an issued invoice never changes, and a schedule revision
cannot drop the instalment it requests.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercials import ON, Commercials, invoice_policy  # noqa: F401  (fixture)
from veda.kernel import clock, db
from veda.modules.commercials import documents
from veda.modules.commercials.models import CommercialInvoice
from veda.platform.notifications.models import OutboxEvent

pytestmark = ON
YEAR = clock.now().astimezone(ZoneInfo("Asia/Kolkata")).year


def test_without_the_owner_decision_an_invoice_is_drafted_and_previewed_but_never_issued(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    line = acc["schedule"]["lines"][0]
    assert acc["capabilities"]["invoice_issuable"] is False
    inv = t.draft(acc, line["id"], customer_note="First instalment")
    assert inv["status"] == "DRAFT" and inv["number"] is None and inv["preview"]["available"] is True
    assert inv["preview"]["document"]["issuer"] is None and inv["preview"]["document"]["number"] is None
    r = t.invoice_action(inv["id"], "issue", status=409)
    assert r.code == "OWNER_DECISION_REQUIRED" and r.json["decision"] == "PCM-D01"
    assert dbh.get(CommercialInvoice, inv["id"]).status == "DRAFT"


def test_issuing_numbers_freezes_and_requests_the_instalment(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    line = acc["schedule"]["lines"][0]
    t.pay(acc, 1000)
    inv = t.draft(acc, line["id"], due_on="2999-01-31", customer_note="Booking instalment")
    issued = t.invoice_action(inv["id"], "issue")
    assert issued["status"] == "ISSUED" and issued["number"] == f"VS-I-{YEAR}-00001"
    doc = issued["document"]
    assert doc["title"] == "Tax invoice" and doc["issuer"]["gstin"] == "00AAAAA0000A0Z0"
    assert doc["instalment"] == {"label": "Booking", "when": line["when"], "position": 1, "of": 3}
    assert doc["amounts"]["instalment"] == line["amount"] and doc["amounts"]["gst_included"] == line["gst_included"]
    assert doc["amounts"]["paid_towards"] == documents.text(1000)
    assert doc["amounts"]["due"] == documents.text(line["amount_minor"] - 1000) and doc["due_on"] == "2999-01-31"
    row = dbh.get(CommercialInvoice, inv["id"])
    assert documents.integrity(row) and issued["html"] == row.document_html
    after = t.get(acc)
    first = after["schedule"]["lines"][0]
    assert first["state"] == "PARTIALLY_PAID" and first["due_on"] == "2999-01-31" and first["requested_on"]
    assert first["invoice"]["number"] == issued["number"]
    assert len(dbh.rows(sa.select(OutboxEvent.id).where(OutboxEvent.event_type == "commercials.invoice_issued"))) == 1
    # an issued invoice does not change the balance, and is never issued twice
    assert after["position"]["paid_minor"] == 1000
    assert t.invoice_action(inv["id"], "issue", status=409).code == "INVALID_STATE"
    assert len(dbh.rows(sa.select(OutboxEvent.id).where(OutboxEvent.event_type == "commercials.invoice_issued"))) == 1
    # payments after issue never alter the frozen document
    t.pay(acc, 2000)
    assert t.invoice(inv["id"])["document"] == doc


def test_one_live_invoice_per_instalment_and_a_paid_instalment_is_not_invoiced(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    first, second = acc["schedule"]["lines"][:2]
    inv = t.draft(acc, first["id"])
    assert t.draft(acc, first["id"], status=409).code == "INVOICE_EXISTS"
    t.invoice_action(inv["id"], "abandon")
    assert dbh.rows(sa.select(CommercialInvoice.is_deleted).where(CommercialInvoice.id == inv["id"])) == [True]
    t.pay(acc, first["amount_minor"])
    assert t.draft(acc, first["id"], status=409).code == "INSTALMENT_PAID"
    assert t.draft(acc, second["id"], due_on="2000-01-01", status=422).code == "VALIDATION_FAILED"
    issued = t.issued_invoice(acc, 2)
    assert t.draft(acc, second["id"], status=409).code == "INVOICE_EXISTS"
    assert t.invoice_action(issued["id"], "abandon", status=409).code == "INVALID_STATE"  # never an issued one


def test_cancelling_keeps_the_document_and_frees_the_instalment(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    issued = t.issued_invoice(acc, 1)
    frozen = issued["document"]
    assert t.invoice_action(issued["id"], "cancel", {"reason": ""}, status=422).code == "VALIDATION_FAILED"
    gone = t.invoice_action(issued["id"], "cancel", {"reason": "Issued for the wrong instalment"})
    assert gone["status"] == "CANCELLED" and gone["document"] == frozen and gone["cancel_reason"]
    assert t.invoice_action(issued["id"], "cancel", {"reason": "again please"}, status=409).code == "INVALID_STATE"
    again = t.issued_invoice(acc, 1)
    assert again["number"] == f"VS-I-{YEAR}-00002"  # numbers are never reused


def test_a_revision_keeps_an_invoiced_instalment_or_is_refused(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, q, acc = t.opened()
    issued = t.issued_invoice(acc, 1)
    lines = [
        {"label": x["label"], "when": x["when"], "amount_minor": x["amount_minor"]} for x in acc["schedule"]["lines"]
    ]
    merged = [
        lines[0],
        {"label": "Rest", "when": "Later", "amount_minor": lines[1]["amount_minor"] + lines[2]["amount_minor"]},
    ]
    kept = t.revise(acc, merged, reason="Merge the later instalments")
    first = kept["schedule"]["lines"][0]
    assert first["invoice"]["id"] == issued["id"] and first["requested_on"]  # carried with its request
    assert dbh.get(CommercialInvoice, issued["id"]).instalment_id == first["id"]
    changed = [{**merged[0], "amount_minor": merged[0]["amount_minor"] - 100},
               {**merged[1], "amount_minor": merged[1]["amount_minor"] + 100}]  # fmt: skip
    r = t.revise(acc, changed, reason="Change the booking amount", status=409)
    assert r.code == "INVOICE_BLOCKS_REVISION" and r.json["invoices"] == [issued["number"]]
    t.invoice_action(issued["id"], "cancel", {"reason": "Booking amount renegotiated"})
    assert t.revise(acc, changed, reason="Change the booking amount")["position"]["schedule_state"] == "IN_BALANCE"


def test_a_tampered_invoice_is_never_served(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    issued = t.issued_invoice(acc, 1)
    from veda.kernel.context import actor, system_context

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        s.execute(sa.update(CommercialInvoice.__table__).where(CommercialInvoice.__table__.c.id == issued["id"])
                  .values(document_html="<p>changed</p>"))  # fmt: skip
    r = t.call("GET", f"/api/v1/commercial-invoices/{issued['id']}")
    assert r.status == 409 and r.code == "DOCUMENT_INTEGRITY_FAILED"
