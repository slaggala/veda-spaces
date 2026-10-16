"""Project Commercials: lead erasure and customer notifications (PCM-030, PCM-031, PCM-050). SYNTHETIC data only.

Erasure follows the repository's policy for commercial records: personal free text is erased and frozen documents are
redacted and re-sealed; amounts, dates, numbers and digests stay; nothing is deleted; the record is closed to writes.
Customers are emailed only that a document is in their portal, once per financial event, never with an amount.
"""

from __future__ import annotations

import sqlalchemy as sa

from tests.support import dbh
from tests.support.commercials import ON, Commercials, invoice_policy  # noqa: F401  (fixture)
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.commercials import documents
from veda.modules.commercials.models import (
    CommercialEvent,
    CommercialInvoice,
    CommercialPayment,
    CommercialPaymentReversal,
    CommercialReceipt,
)
from veda.platform.notifications import worker
from veda.platform.notifications.email import CaptureEmailProvider

pytestmark = ON


def _erase(lead_id: str) -> None:
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, lead_id), legal_basis="SYNTHETIC erasure test", request_ref=None)


def test_erasure_redacts_personal_text_keeps_the_financial_record_and_closes_it(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, acc = t.opened()
    p1 = t.pay(acc, 4000, external_reference="name@okbank", customer_note="From Mrs Synthetic",
               internal_note="Called Mrs Synthetic")  # fmt: skip
    p2 = t.pay(acc, 1000)
    t.reverse(acc, p2["payment_id"], "OTHER", note="Mrs Synthetic asked to redo it")
    inv = t.issued_invoice(acc, 2, customer_note="For Mrs Synthetic")
    counts = {m: len(dbh.rows(sa.select(m.id))) for m in (CommercialPayment, CommercialReceipt, CommercialInvoice,
                                                         CommercialPaymentReversal)}  # fmt: skip
    _erase(prop["lead_id"])
    assert {m: len(dbh.rows(sa.select(m.id))) for m in counts} == counts  # nothing deleted
    pay = dbh.get(CommercialPayment, p1["payment_id"])
    assert pay.amount_minor == 4000 and pay.method_code == "BANK_TRANSFER"
    assert (pay.external_reference, pay.customer_note, pay.internal_note) == ("[erased]",) * 3
    assert dbh.rows(sa.select(CommercialPaymentReversal.note)) == ["[erased]"]
    rc = dbh.get(CommercialReceipt, p1["receipt_id"])
    assert documents.integrity(rc) and rc.snapshot["customer"]["name"] == "[erased]"
    assert rc.snapshot["payment"]["reference"] == "[erased]" and rc.snapshot["payment"]["amount"] == documents.text(
        4000
    )
    assert "Mrs Synthetic" not in rc.document_html and "name@okbank" not in rc.document_html
    iv = dbh.get(CommercialInvoice, inv["id"])
    assert documents.integrity(iv) and iv.invoice_number == inv["number"] and iv.snapshot["note"] == "[erased]"
    assert iv.snapshot["amounts"] == inv["document"]["amounts"]
    assert "DOCUMENT_REDACTED" in dbh.rows(sa.select(CommercialEvent.event_code))
    view = t.get(acc)
    assert view["lead"]["erased"] is True and view["capabilities"]["writable"] is False
    assert [x["code"] for x in view["problems"]] == ["BASELINE_ERASED"]
    assert t.pay(acc, 100, status=409).code == "INVALID_STATE"


def test_documents_are_emailed_once_without_amounts_to_the_primary_customer(api, factory, invoice_policy):  # noqa: F811
    t = Commercials(api, factory)
    prop, _, acc = t.opened()
    t.invite(prop["lead_id"], "primary@example.test")
    t.grant(prop["lead_id"], "family@example.test", relationship="FAMILY_MEMBER")
    worker.drain_all()
    CaptureEmailProvider.clear()
    k = "pcm-email-key-0000001"
    t.pay(acc, 12345, idem=k)
    t.pay(acc, 12345, idem=k, status=200)  # a retry: no second email
    inv = t.issued_invoice(acc, 2)
    worker.drain_all()
    sent = [m for m in CaptureEmailProvider.sent if "project portal" in m.subject.lower()]
    assert sorted(m.to[0] for m in sent) == ["primary@example.test", "primary@example.test"]
    receipt_mail = next(m for m in sent if "receipt" in m.subject.lower())
    invoice_mail = next(m for m in sent if "invoice" in m.subject.lower())
    assert inv["number"] in invoice_mail.text and "/portal/properties/" in invoice_mail.text
    for m in sent:
        assert "123.45" not in m.text and "12,345" not in m.text and "INR" not in m.text
    assert receipt_mail.text.count("VS-R-") == 1


def test_no_email_for_a_payment_reversed_before_the_worker_ran(api, factory):
    t = Commercials(api, factory)
    prop, _, acc = t.opened()
    t.invite(prop["lead_id"], "p2@example.test")
    worker.drain_all()
    CaptureEmailProvider.clear()
    out = t.pay(acc, 500)
    t.reverse(acc, out["payment_id"])  # reversed before the worker ran: nothing is sent
    worker.drain_all()
    assert not [m for m in CaptureEmailProvider.sent if "receipt" in m.subject.lower()]
