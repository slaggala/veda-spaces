"""Customer Promise endpoints (staff only). Every route answers 404, before authentication, unless
VEDA_CUSTOMER_PROMISE_ADMIN_ENABLED is on (off by default; production refuses it). There is no public route: customers
see a pack only as frozen in an issued quotation.

Route permissions are the first gate; the service checks the section-specific capability, the version's state,
four-eyes and the content again, so hiding a control in the page is never the authorisation.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import Field

from veda.config import settings
from veda.kernel.dto import Closed, Id, Query, optional_text, text
from veda.kernel.errors import ApiError
from veda.kernel.http import Api, Req, ok, problem_response, request_reaches
from veda.modules.mtq_commercial import customer_pack as CP

from . import present, service
from . import sections as SEC

api = Api("customer_promise", "/api/v1", tags=("customer-promise",))
GATED_PREFIXES = ("/api/v1/customer-promise",)
EDIT_CODES = ("customer_promise.edit", "customer_promise.contacts.edit", "customer_promise.warranty.edit",
              "customer_promise.payment_safety.edit")  # fmt: skip
REVIEW_CODES = ("customer_promise.review", "customer_promise.review.sensitive")


@api.blueprint.before_app_request
def _enabled():
    if not settings().customer_promise_admin_enabled and request_reaches(("customer_promise",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


class DraftIn(Closed):
    based_on_pack_id: Id | None = None  # an earlier published version to roll back to; default: the published one
    change_summary: Annotated[str | None, optional_text(500)] = None


class SummaryIn(Closed):
    change_summary: Annotated[str | None, optional_text(500)] = None


class SectionIn(Closed):
    value: dict[str, Any] = Field(max_length=3)  # exactly the section's fields; checked by the service


class ReviewIn(Closed):
    decision: Literal["APPROVED", "CHANGES_REQUESTED"]
    comment: Annotated[str | None, optional_text(1000)] = None


class NoteIn(Closed):
    note: Annotated[str | None, optional_text(1000)] = None


class ReasonIn(Closed):
    reason: Annotated[str, text(1000, min_len=5)]


def _detail(req: Req, p) -> Any:
    req.session.flush()
    return ok(present.detail(req.session, req.ctx, p))


def _write(req: Req, pack_id: str):
    p = service.get(req.session, pack_id)
    req.require_version(p.version)
    return p


@api.route("GET", "/customer-promise", permission="customer_promise.view", write=False, requirement="CPA-001",
           summary="The Customer Promise landing page: published and open versions, completeness, OI-MTQ-18 state")  # fmt: skip
def landing(req: Req):
    return ok(present.landing(req.session, req.ctx))


@api.route("GET", "/customer-promise/vocabulary", permission="customer_promise.view", write=False,
           requirement="CPA-001", summary="Sections, categories and states the editor offers (structure only)")  # fmt: skip
def vocabulary(req: Req):
    return ok({
        "sections": [{"code": s.code, "title": s.title, "keys": list(s.keys), "sensitive": s.sensitive,
                      "edit_permission": s.edit, "review_permission": s.review} for s in SEC.SECTIONS],
        "areas": [{"code": a.code, "title": a.title, "section": a.section} for a in SEC.AREAS],
        "contact_kinds": list(get_args(CP.Contact.model_fields["kind"].annotation)),
        "responsibility_categories": list(get_args(CP.ResponsibilityCategory)),
        "responsibility_statuses": list(CP.RESPONSIBILITY_STATUSES),
        "readiness_categories": list(get_args(CP.ReadinessCategory)),
        "readiness_statuses": list(CP.READINESS_STATUSES),
        "site_work_categories": list(get_args(CP.SiteWorkCategory)),
        "handover_categories": list(get_args(CP.HandoverCategory)),
        "care_categories": list(get_args(CP.CareCategory)),
        "stages": list(CP.STAGES),
        "limits": {"copy": 600, "label": 80, "duration": 80, "summary": 500},
    })  # fmt: skip


@api.route("GET", "/customer-promise/versions", permission="customer_promise.view", write=False,
           requirement="CPA-001", summary="Every version, newest first: status, people, dates and quotation counts")  # fmt: skip
def list_versions(req: Req):
    return ok(present.history(req.session))


@api.route("POST", "/customer-promise/versions", permission="customer_promise.draft.create", body=DraftIn,
           status=201, idempotent_create=True, requirement="CPA-002",
           summary="Start a draft from the published version, or from an earlier one (rollback by a new version)")  # fmt: skip
def create_version(req: Req):
    body = req.body or DraftIn()
    p = service.create_draft(req.session, req.ctx, body.based_on_pack_id, body.change_summary)
    req.session.flush()
    return ok(present.detail(req.session, req.ctx, p), status=201)


@api.route("GET", "/customer-promise/versions/<pack_id>", permission="customer_promise.view", write=False,
           requirement="CPA-001", summary="One version: sections, changes, reviews, problems, permitted actions")  # fmt: skip
def get_version(req: Req, pack_id: str):
    return ok(present.detail(req.session, req.ctx, service.get(req.session, pack_id)))


@api.route("PATCH", "/customer-promise/versions/<pack_id>", permission="customer_promise.draft.create",
           body=SummaryIn, if_match=True, requirement="CPA-002", summary="Change a draft's change summary")  # fmt: skip
def patch_version(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.set_summary(req.session, req.ctx, p, req.body.change_summary))


@api.route("PUT", "/customer-promise/versions/<pack_id>/sections/<section_code>", any_of=EDIT_CODES, body=SectionIn,
           if_match=True, requirement="CPA-003", summary="Save one section of a draft (every content rule applies)")  # fmt: skip
def save_section(req: Req, pack_id: str, section_code: str):
    p = _write(req, pack_id)
    return _detail(req, service.save_section(req.session, req.ctx, p, section_code, req.body.value))


@api.route("POST", "/customer-promise/versions/<pack_id>/submit", permission="customer_promise.submit",
           if_match=True, requirement="CPA-007", summary="Submit a draft for review")  # fmt: skip
def submit(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.submit(req.session, req.ctx, p))


@api.route("POST", "/customer-promise/versions/<pack_id>/sections/<section_code>/review", any_of=REVIEW_CODES,
           body=ReviewIn, if_match=True, requirement="CPA-008",
           summary="Approve a changed section, or request changes (returns the version to draft)")  # fmt: skip
def review(req: Req, pack_id: str, section_code: str):
    p = _write(req, pack_id)
    return _detail(req, service.review(req.session, req.ctx, p, section_code, req.body.decision, req.body.comment))


@api.route("POST", "/customer-promise/versions/<pack_id>/approve", permission="customer_promise.approve",
           body=NoteIn, if_match=True, requirement="CPA-010",
           summary="Approve a fully reviewed version for publication (four-eyes)")  # fmt: skip
def approve(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.approve(req.session, req.ctx, p, (req.body or NoteIn()).note))


@api.route("POST", "/customer-promise/versions/<pack_id>/return", any_of=("customer_promise.submit",
           "customer_promise.approve"), body=ReasonIn, if_match=True, requirement="CPA-007",
           summary="Return a version in review or approved to draft, with a reason")  # fmt: skip
def return_to_draft(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.return_to_draft(req.session, req.ctx, p, req.body.reason))


@api.route("POST", "/customer-promise/versions/<pack_id>/discard", permission="customer_promise.draft.create",
           body=ReasonIn, if_match=True, requirement="CPA-002", summary="Discard an unwanted draft (kept, never deleted)")  # fmt: skip
def discard(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.discard(req.session, req.ctx, p, req.body.reason))


@api.route("POST", "/customer-promise/versions/<pack_id>/publish", permission="customer_promise.publish",
           if_match=True, requirement="CPA-011",
           summary="Publish an approved version; the published one is superseded, in one transaction")  # fmt: skip
def publish(req: Req, pack_id: str):
    p = _write(req, pack_id)
    return _detail(req, service.publish(req.session, req.ctx, p))


@api.route("GET", "/customer-promise/versions/<pack_id>/preview", permission="customer_promise.preview", write=True,
           requirement="CPA-012", summary="The version as customers would see it (PREVIEW / NOT PUBLISHED); recorded")  # fmt: skip
def preview(req: Req, pack_id: str):
    return ok(service.preview(req.session, req.ctx, service.get(req.session, pack_id)))


class DiffQuery(Query):
    against: Id | None = None


@api.route("GET", "/customer-promise/versions/<pack_id>/changes", permission="customer_promise.view", write=False,
           query=DiffQuery, requirement="CPA-001",
           summary="What changed, in words: against the published version (or a chosen version)")  # fmt: skip
def changes(req: Req, pack_id: str):
    against = req.query.against if req.query else None
    return ok(service.comparison(req.session, service.get(req.session, pack_id), against))
