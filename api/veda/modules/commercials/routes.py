"""Project Commercials staff endpoints. Every route answers 404, before authentication, unless
VEDA_PROJECT_COMMERCIALS_ENABLED is on (off by default; production refuses it). The customer routes are the portal's
(``veda.modules.portal.routes``, RBX-010), reading ``commercials.customer``.

The route permission is the first gate; the services check it again **in the account's scope** (the lead's), take the
account lock, re-read, and check the state, so hiding a control in the page is never the authorisation. A change to an
existing row needs the version the user saw (If-Match). A payment needs an ``Idempotency-Key`` (stored with it: a retry
returns the payment already recorded).
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.kernel.errors import ApiError, field_error, not_found
from veda.kernel.http import IDEMPOTENCY_KEY_RE, Api, Req, ok, problem_response, request_reaches
from veda.modules.mtq import scope as lead_scope
from veda.modules.mtq_commercial.models import Quotation

from . import access, baseline, invoices, payments, present, schedule
from . import schemas as S
from .models import CommercialAccount, CommercialInvoice, CommercialPayment, CommercialReceipt, PaymentInstalment

api = Api("commercials", "/api/v1", tags=("project-commercials",))
GATED_PREFIXES = ("/api/v1/commercials", "/api/v1/commercial-invoices", "/api/v1/commercial-receipts")


@api.blueprint.before_app_request
def _enabled():
    if not settings().project_commercials_enabled and request_reaches(("commercials",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


def _account(req: Req, account_id: str, permission: str = "commercials.view") -> CommercialAccount:
    return access.visible(req.session, req.ctx, account_id, permission)


def _detail(req: Req, account: CommercialAccount, status: int = 200, **extra):
    req.session.flush()
    body = present.detail(req.session, req.ctx, account)
    return ok({**body, **extra} if extra else body, status=status)


# --- accounts ---------------------------------------------------------------------------------------------------------
@api.route("GET", "/commercials", permission="commercials.view", write=False, requirement="PCM-020",
           summary="Commercial records within scope, with their position")  # fmt: skip
def list_accounts(req: Req):
    rows = req.session.execute(sa.select(CommercialAccount).where(CommercialAccount.is_deleted == sa.false(),
                                                                  access.condition(req.ctx, "commercials.view"))
                               .order_by(CommercialAccount.created_on.desc()).limit(200)).scalars()  # fmt: skip
    return ok([present.summary(req.session, a) for a in rows])


@api.route("GET", "/commercials/candidates", permission="commercials.schedule.manage", write=False,
           requirement="PCM-001", summary="Accepted quotations within scope that have no commercial record yet")  # fmt: skip
def candidates(req: Req):
    cond = lead_scope.condition(req.ctx, "commercials.schedule.manage", Quotation.lead_id)
    return ok([present.candidate(req.session, q) for q in baseline.candidates(req.session, cond)])


@api.route("POST", "/commercials", permission="commercials.schedule.manage", body=S.OpenIn, status=201,
           idempotent_create=True, requirement="PCM-001",
           summary="Open the commercial record of an accepted quotation (its baseline and first payment schedule)")  # fmt: skip
def open_account(req: Req):
    q = req.session.get(Quotation, req.body.quotation_id)
    if q is None or q.is_deleted:
        raise ApiError(422, "VALIDATION_FAILED", "Choose an accepted quotation.",
                       errors=[field_error("quotation_id", "UNKNOWN_QUOTATION", "Not a quotation.")])  # fmt: skip
    lead_scope.require_lead(req.session, req.ctx, q.lead_id, "commercials.schedule.manage")
    if req.session.get_bind().dialect.name == "postgresql":  # serialise openings of one chain
        req.session.execute(sa.select(Quotation.id).where(Quotation.id == q.id).with_for_update())
        req.session.refresh(q)
    account = baseline.open_account(req.session, q)
    schedule.initial(req.session, account, q)
    return _detail(req, account, status=201)


@api.route("GET", "/commercials/<account_id>", permission="commercials.view", write=False, requirement="PCM-020",
           summary="One commercial record: baseline, position, schedule, payments, invoices and receipts")  # fmt: skip
def get_account(req: Req, account_id: str):
    return _detail(req, _account(req, account_id))


@api.route("GET", "/commercials/<account_id>/history", permission="commercials.audit.view", write=False,
           requirement="PCM-025", summary="The commercial history: who did what, when")  # fmt: skip
def get_history(req: Req, account_id: str):
    account = _account(req, account_id, "commercials.audit.view")
    return ok(present.history(req.session, account))


# --- schedule ---------------------------------------------------------------------------------------------------------
@api.route("POST", "/commercials/<account_id>/schedule", permission="commercials.schedule.manage", body=S.ScheduleIn,
           if_match=True, requirement="PCM-006",
           summary="Revise (or create) the payment schedule; instalments must add up to the project value")  # fmt: skip
def revise_schedule(req: Req, account_id: str):
    account = _account(req, account_id)
    access.for_write(req.session, req.ctx, account, "commercials.schedule.manage", if_match=req.if_match)
    baseline.sync(req.session, account)
    payments.require_sound(req.session, account)
    schedule.revise(req.session, req.ctx, account, req.body)
    access.touch(req.session, account)
    return _detail(req, account)


@api.route("POST", "/commercials/<account_id>/instalments/<instalment_id>/request",
           permission="commercials.schedule.manage", body=S.RequestIn, if_match=True, requirement="PCM-007",
           summary="Ask the customer for an instalment, optionally by a due date")  # fmt: skip
def request_instalment(req: Req, account_id: str, instalment_id: str):
    account = _account(req, account_id)
    inst = req.session.get(PaymentInstalment, instalment_id)
    if inst is None or inst.is_deleted or inst.account_id != account.id:
        raise not_found()
    access.for_write(req.session, req.ctx, account, "commercials.schedule.manage", inst, if_match=req.if_match)
    schedule.request(req.session, req.ctx, account, inst, req.body.due_on)
    access.touch(req.session, account)
    return _detail(req, account)


# --- payments ---------------------------------------------------------------------------------------------------------
@api.route("POST", "/commercials/<account_id>/payments", permission="commercials.payment.record", body=S.PaymentIn,
           status=201, requirement="PCM-009",
           summary="Record a payment received outside the system (needs Idempotency-Key); issues its receipt")  # fmt: skip
def record_payment(req: Req, account_id: str):
    key = req.headers.get("Idempotency-Key") if req.headers is not None else None
    if not key or not IDEMPOTENCY_KEY_RE.match(key):
        raise ApiError(422, "VALIDATION_FAILED", "Send an Idempotency-Key with every payment.",
                       errors=[field_error("Idempotency-Key", "REQUIRED", "16–64 characters [A-Za-z0-9_-].")])  # fmt: skip
    account = _account(req, account_id)
    access.for_write(req.session, req.ctx, account, "commercials.payment.record", precondition=False)
    payment, created = payments.record(req.session, req.ctx, account, req.body, key)
    if created:
        access.touch(req.session, account)
    receipt = payments.receipt_of(req.session, payment.id)
    return _detail(req, account, status=201 if created else 200, payment_id=payment.id,
                   receipt_id=receipt.id if receipt else None, replayed=not created)  # fmt: skip


@api.route("POST", "/commercials/<account_id>/payments/<payment_id>/reverse", permission="commercials.payment.reverse",
           body=S.ReverseIn, if_match=True, requirement="PCM-011",
           summary="Reverse a recorded payment with a reason (never one you recorded)")  # fmt: skip
def reverse_payment(req: Req, account_id: str, payment_id: str):
    account = _account(req, account_id)
    p = req.session.get(CommercialPayment, payment_id)
    if p is None or p.is_deleted or p.account_id != account.id:
        raise not_found()
    access.for_write(req.session, req.ctx, account, "commercials.payment.reverse", if_match=req.if_match)
    payments.reverse(req.session, req.ctx, account, p, req.body)
    access.touch(req.session, account)
    return _detail(req, account)


# --- invoices ---------------------------------------------------------------------------------------------------------
def _invoice(
    req: Req, invoice_id: str, permission: str = "commercials.view"
) -> tuple[CommercialAccount, CommercialInvoice]:
    inv = req.session.get(CommercialInvoice, invoice_id)
    if inv is None or inv.is_deleted:
        raise not_found()
    return _account(req, inv.account_id, permission), inv


def _invoice_view(req: Req, account: CommercialAccount, inv: CommercialInvoice) -> dict:
    from . import documents

    req.session.flush()
    people = present.People(req.session)
    out = present._invoice(inv, people)
    if inv.status == "DRAFT":
        out["preview"] = invoices.preview(req.session, account, inv)
    else:
        out["document"] = documents.verified(inv, "invoice")
        out["html"], out["filename"] = inv.document_html, f"{inv.invoice_number}.html"
    out["account_id"], out["account_version"] = account.id, account.version
    return out


@api.route("POST", "/commercials/<account_id>/invoices", permission="commercials.invoice.issue", body=S.InvoiceIn,
           status=201, idempotent_create=True, requirement="PCM-012",
           summary="Draft an invoice for an instalment of the current schedule (staff only until issued)")  # fmt: skip
def draft_invoice(req: Req, account_id: str):
    account = _account(req, account_id)
    access.for_write(req.session, req.ctx, account, "commercials.invoice.issue", precondition=False)
    inv = invoices.draft(req.session, req.ctx, account, req.body)
    access.touch(req.session, account)
    return ok(_invoice_view(req, account, inv), status=201)


@api.route("GET", "/commercial-invoices/<invoice_id>", permission="commercials.view", write=False,
           requirement="PCM-012", summary="One invoice: a draft's preview, or the issued frozen document")  # fmt: skip
def get_invoice(req: Req, invoice_id: str):
    account, inv = _invoice(req, invoice_id)
    return ok(_invoice_view(req, account, inv))


@api.route("POST", "/commercial-invoices/<invoice_id>/issue", permission="commercials.invoice.issue", if_match=True,
           requirement="PCM-012", summary="Issue a draft invoice: number, frozen document, customer notified")  # fmt: skip
def issue_invoice(req: Req, invoice_id: str):
    account, inv = _invoice(req, invoice_id)
    access.for_write(req.session, req.ctx, account, "commercials.invoice.issue", inv, if_match=req.if_match, match=inv)
    baseline.sync(req.session, account)
    invoices.issue(req.session, req.ctx, account, inv)
    access.touch(req.session, account)
    return ok(_invoice_view(req, account, inv))


@api.route("POST", "/commercial-invoices/<invoice_id>/cancel", permission="commercials.invoice.issue", body=S.CancelIn,
           if_match=True, requirement="PCM-012", summary="Cancel an issued invoice with a reason (the document stays)")  # fmt: skip
def cancel_invoice(req: Req, invoice_id: str):
    account, inv = _invoice(req, invoice_id)
    access.for_write(req.session, req.ctx, account, "commercials.invoice.issue", inv, if_match=req.if_match, match=inv)
    invoices.cancel(req.session, req.ctx, account, inv, req.body.reason)
    access.touch(req.session, account)
    return ok(_invoice_view(req, account, inv))


@api.route("POST", "/commercial-invoices/<invoice_id>/discard", permission="commercials.invoice.issue", if_match=True,
           requirement="PCM-012", summary="Discard a draft invoice (never an issued one)")  # fmt: skip
def discard_invoice(req: Req, invoice_id: str):
    account, inv = _invoice(req, invoice_id)
    access.for_write(req.session, req.ctx, account, "commercials.invoice.issue", inv, if_match=req.if_match, match=inv)
    invoices.discard(req.session, req.ctx, account, inv)
    access.touch(req.session, account)
    return _detail(req, account)


# --- receipts ---------------------------------------------------------------------------------------------------------
@api.route("GET", "/commercial-receipts/<receipt_id>", permission="commercials.view", write=False,
           requirement="PCM-013", summary="One receipt: the frozen document, and whether its payment was reversed")  # fmt: skip
def get_receipt(req: Req, receipt_id: str):
    from . import documents

    r = req.session.get(CommercialReceipt, receipt_id)
    if r is None or r.is_deleted:
        raise not_found()
    account = _account(req, r.account_id)
    rev = payments.reversal_of(req.session, r.payment_id)
    return ok({"id": r.id, "number": r.receipt_number, "payment_id": r.payment_id, "account_id": account.id,
               "status": "CANCELLED" if rev else "VALID", "document": documents.verified(r, "receipt"),
               "html": r.document_html, "filename": f"{r.receipt_number}.html"})  # fmt: skip
