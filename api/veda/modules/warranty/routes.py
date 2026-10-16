"""Warranty and after-sales service endpoints (staff). Every route answers 404, before authentication, unless
VEDA_WARRANTY_SERVICE_ENABLED and VEDA_PROJECT_LIFECYCLE_ENABLED are on (off by default; production refuses the first).
The customer routes are the portal's (``portal.routes``).

Route permissions are the first gate; the services check the capability again in the request's scope (ALL, or OWN:
the owner or the project's team), the state, the coverage rules and separation of duties. Writes to an existing row
need the version the user saw (If-Match); a new row needs an Idempotency-Key.
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import Api, Req, ok, problem_response, request_reaches

from . import access, entitlement, present, requests
from . import schemas as S
from .models import WarrantyEntitlement

api = Api("warranty", "/api/v1", tags=("warranty",))
GATED_PREFIXES = ("/api/v1/warranty", "/api/v1/service-requests")


@api.blueprint.before_app_request
def _enabled():
    if not access.staff_enabled() and request_reaches(("warranty",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


def _detail(req: Req, r, status: int = 200):
    req.session.flush()
    req.session.refresh(r)
    return ok(present.detail(req.session, req.ctx, r), status=status)


def _req(req: Req, request_id: str, code: str = "warranty.service.view"):
    return access.visible_request(req.session, req.ctx, request_id, code)


# --- entitlements ------------------------------------------------------------------------------------------------------
@api.route("GET", "/warranty/projects/<project_id>", permission="warranty.view", write=False, requirement="WSV-001",
           summary="A project's warranty entitlement (frozen at handover) and its coverage status today")  # fmt: skip
def get_entitlement(req: Req, project_id: str):
    from veda.modules.project.models import Project

    s, ctx = req.session, req.ctx
    p = s.get(Project, project_id)
    if p is None:
        raise not_found()
    visible = s.execute(sa.select(Project.id).where(Project.id == p.id, sa.or_(
        sa.true() if ctx.scope("warranty.view") == "ALL" else sa.false(),
        Project.id.in_(access._team(ctx.user.id)) if ctx.scope("warranty.view") == "OWN" else sa.false()))).first()  # fmt: skip
    if visible is None:
        raise not_found()
    e = entitlement.for_project(s, p.id)
    out = present.entitlement_view(s, e, project_id=p.id)
    out["project"] = {"id": p.id, "project_number": p.project_number, "status": p.status}
    out["can_register"] = e is None and p.status == "HANDED_OVER" and ctx.scope("warranty.manage") is not None
    return ok(out)


@api.route("POST", "/warranty/entitlements", permission="warranty.manage", body=S.WarrantyRegisterIn, status=201,
           idempotent_create=True, requirement="WSV-002",
           summary="Register a handed-over project's warranty from its handover record (idempotent)")  # fmt: skip
def register(req: Req):
    from veda.modules.project import access as paccess
    from veda.modules.project.models import Project

    s, ctx = req.session, req.ctx
    p = s.get(Project, req.body.project_id)
    if p is None or (ctx.scope("warranty.manage") == "OWN" and not paccess.is_member(s, p.id, ctx.user.id)):
        raise not_found()
    paccess.lock(s, p)
    e, created = entitlement.register(s, p, "STAFF")
    s.flush()
    return ok(present.entitlement_view(s, e, project_id=p.id), status=201 if created else 200)


@api.route("GET", "/warranty/entitlements/<entitlement_id>", permission="warranty.view", write=False,
           requirement="WSV-001", summary="One warranty entitlement")  # fmt: skip
def get_entitlement_by_id(req: Req, entitlement_id: str):
    s = req.session
    e = s.execute(sa.select(WarrantyEntitlement).where(WarrantyEntitlement.id == entitlement_id,
                                                       access.entitlement_condition(req.ctx, "warranty.view"))
                  ).scalar_one_or_none()  # fmt: skip
    if e is None:
        raise not_found()
    return ok(present.entitlement_view(s, e))


# --- requests ----------------------------------------------------------------------------------------------------------
@api.route("GET", "/service-requests", permission="warranty.service.view", write=False, query=S.ServiceListQuery,
           requirement="WSV-010", summary="Service requests in scope (open, mine, waiting, closed)")  # fmt: skip
def list_requests(req: Req):
    return ok(present.listing(req.session, req.ctx, req.query or S.ServiceListQuery()))


@api.route("GET", "/service-requests/vocabulary", permission="warranty.service.view", write=False,
           requirement="WSV-010", summary="The codes the service pages offer")  # fmt: skip
def vocabulary(req: Req):
    return ok(present.vocabulary())


@api.route("POST", "/service-requests", permission="warranty.service.triage", body=S.ServiceStaffRequestIn, status=201,
           idempotent_create=True, requirement="WSV-011",
           summary="Record a problem a customer reported by phone or in person, in their words")  # fmt: skip
def create_request(req: Req):
    from veda.modules.project.models import Project

    s, ctx = req.session, req.ctx
    p = s.get(Project, req.body.project_id)
    if p is None:
        raise not_found()
    if ctx.scope("warranty.service.triage") == "OWN":
        from veda.modules.project.access import is_member

        if not is_member(s, p.id, ctx.user.id):
            raise not_found()
    r, _ = requests.submit(s, property_id=req.body.property_id, project_id=p.id, body=req.body, channel="STAFF")
    return _detail(req, r, status=201)


@api.route("GET", "/service-requests/<request_id>", permission="warranty.service.view", write=False,
           requirement="WSV-010", summary="One service request: the customer's words, decisions, visits, history")  # fmt: skip
def get_request(req: Req, request_id: str):
    return ok(present.detail(req.session, req.ctx, _req(req, request_id)))


@api.route("POST", "/service-requests/<request_id>/information-requests", permission="warranty.service.triage",
           body=S.ServiceInformationRequestIn, if_match=True, requirement="WSV-011",
           summary="Ask the customer for information (they read the question)")  # fmt: skip
def ask(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.request_information(req.session, req.ctx, r, req.body.question, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/information", permission="warranty.service.triage",
           body=S.ServiceInformationIn, if_match=True, requirement="WSV-011",
           summary="Record the customer's answer given by phone or in person")  # fmt: skip
def answer(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.add_information(req.session, r, req.body.text, ctx=req.ctx, if_match=req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/triage", permission="warranty.service.triage", body=S.ServiceTriageIn,
           if_match=True, requirement="WSV-011", summary="Triage a reported request")  # fmt: skip
def triage(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.triage(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/assessments", permission="warranty.service.assess",
           body=S.ServiceAssessIn, if_match=True, requirement="WSV-012",
           summary="Decide coverage with its basis, a customer explanation and an internal reason")  # fmt: skip
def assess(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.assess(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/assign", permission="warranty.service.assign", body=S.ServiceAssignIn,
           if_match=True, requirement="WSV-013", summary="Assign the request's owner")  # fmt: skip
def assign(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.assign(req.session, req.ctx, r, req.body.owner_user_id, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/visits", permission="warranty.service.resolve", body=S.ServiceVisitIn,
           if_match=True, status=201, requirement="WSV-014", summary="Plan an inspection or service visit")  # fmt: skip
def plan_visit(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.plan_visit(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r, status=201)


@api.route("POST", "/service-requests/<request_id>/visits/<visit_id>/done", permission="warranty.service.resolve",
           body=S.ServiceVisitDoneIn, if_match=True, requirement="WSV-014", summary="Record a visit as done, with evidence")  # fmt: skip
def visit_done(req: Req, request_id: str, visit_id: str):
    r = _req(req, request_id)
    requests.record_visit(req.session, req.ctx, r, visit_id, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/visits/<visit_id>/cancel", permission="warranty.service.resolve",
           body=S.ServiceReasonIn, if_match=True, requirement="WSV-014", summary="Cancel a planned visit, with a reason")  # fmt: skip
def visit_cancel(req: Req, request_id: str, visit_id: str):
    r = _req(req, request_id)
    requests.cancel_visit(req.session, req.ctx, r, visit_id, req.body.reason, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/evidence", permission="warranty.service.resolve",
           body=S.ServiceEvidenceIn, if_match=True, requirement="WSV-014",
           summary="Cite an available attachment as evidence (shown to the customer only when marked so)")  # fmt: skip
def evidence(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.add_evidence(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/resolve", permission="warranty.service.resolve", body=S.ServiceResolveIn,
           if_match=True, requirement="WSV-014", summary="Record the resolution of a covered request")  # fmt: skip
def resolve(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.resolve(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/verify", permission="warranty.service.verify", if_match=True,
           requirement="WSV-015", summary="Verify a resolution (never your own) and close the request")  # fmt: skip
def verify(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.verify(req.session, req.ctx, r, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/close", permission="warranty.service.assess", body=S.ServiceCloseIn,
           if_match=True, requirement="WSV-012", summary="Close a request without service, with its reason")  # fmt: skip
def close(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.close(req.session, req.ctx, r, req.body, req.if_match)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/withdraw", permission="warranty.service.triage",
           body=S.ServiceWithdrawIn, if_match=True, requirement="WSV-011",
           summary="Withdraw a request at the customer's wish")  # fmt: skip
def withdraw(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.withdraw(req.session, r, ctx=req.ctx, if_match=req.if_match, reason=req.body.reason)
    return _detail(req, r)


@api.route("POST", "/service-requests/<request_id>/reopen", permission="warranty.service.verify", body=S.ServiceReasonIn,
           if_match=True, requirement="WSV-015", summary="Reopen a closed request, with a reason (new cycle)")  # fmt: skip
def reopen(req: Req, request_id: str):
    r = _req(req, request_id)
    requests.reopen(req.session, req.ctx, r, req.body.reason, req.if_match)
    return _detail(req, r)
