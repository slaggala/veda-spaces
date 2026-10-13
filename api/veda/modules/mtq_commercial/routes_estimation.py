"""MTQ B2/B3 endpoints: requirements, scope, BOQ (and, in B3, the internal estimate). Staff only, scoped by lead.

Every route answers 404, before authentication, unless VEDA_MTQ_ESTIMATION_ENABLED is on (off by default; production
refuses it; it needs the B1 flag). Nothing here is customer-facing.
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import Api, Req, no_content, ok, problem_response, request_reaches
from veda.modules.mtq.models import Property

from . import access, boqs, discounts, estimates, journey, lineage, policy, requirements, rules, scopes
from . import schemas as S
from .models import Boq, BoqLine, CostEstimate, CostEstimateAdjustment, Requirement, Scope, ScopeItem

api = Api("mtq_estimation", "/api/v1", tags=("mtq-commercial",))

GATED_PREFIXES = (
    "/api/v1/requirements",
    "/api/v1/scopes",
    "/api/v1/scope-items",
    "/api/v1/boqs",
    "/api/v1/boq-lines",
    "/api/v1/cost-estimates",
    "/api/v1/cost-estimate-lines",
    "/api/v1/estimate-adjustments",
    "/api/v1/mtq/scope-rules",
    "/api/v1/mtq/commercial-policy",
)


@api.blueprint.before_app_request
def _estimation_enabled():
    """Same gate as B1 (MC-3, B1-PE-09): every method and every routed spelling of a gated path answers 404."""
    if not settings().mtq_estimation_enabled and request_reaches(("mtq_estimation",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


# --- ruleset and journey ----------------------------------------------------------------------------------------------
@api.route("GET", "/mtq/scope-rules", permission="scope.read", write=False, requirement="SCOPE-001",
           summary="The versioned scope ruleset (item types, catalogue mapping, derivations, rules) and its status")  # fmt: skip
def get_rules(req: Req):
    return ok(rules.public_view())


@api.route("GET", "/properties/<property_id>/commercial", permission="scope.read", write=False,
           requirement="SCOPE-001",
           summary="Measurement-to-quotation lineage of a property: every revision, its upstream pins and staleness")  # fmt: skip
def get_journey(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    return ok(journey.view(req.session, req.ctx, prop))


# --- requirements -----------------------------------------------------------------------------------------------------
@api.route("GET", "/properties/<property_id>/requirements", permission="scope.read", write=False,
           requirement="SCOPE-001", summary="Requirements of a property with their provenance and decisions")  # fmt: skip
def list_requirements(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    spaces = requirements.spaces_of(req.session, prop)
    return ok([requirements.present(r, spaces) for r in requirements.for_property(req.session, prop)])


@api.route("POST", "/properties/<property_id>/requirements/seed", permission="scope.edit", idempotent_create=True,
           requirement="SCOPE-002",
           summary="Propose requirements from the ruleset and the current verified measurement set (idempotent)")  # fmt: skip
def seed_requirements(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    access.for_write(req.session, req.ctx, prop.lead_id, prop.id, "scope.edit")
    result = requirements.seed(req.session, req.ctx, prop)
    req.session.flush()
    return ok(result)


@api.route("POST", "/properties/<property_id>/requirements", permission="scope.edit", body=S.RequirementCreateIn,
           status=201, idempotent_create=True, requirement="SCOPE-002",
           summary="Add a staff-selected, customer-requested or manual requirement (accepted by being added)")  # fmt: skip
def add_requirement(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    access.for_write(req.session, req.ctx, prop.lead_id, prop.id, "scope.edit")
    r = requirements.add(req.session, req.ctx, prop, req.body)
    return ok(requirements.present(r, requirements.spaces_of(req.session, prop)), status=201)


def _requirement(req: Req, requirement_id: str) -> tuple[Requirement, Property]:
    r = access.row_visible(req.session, req.ctx, Requirement, requirement_id, "scope.read")
    prop = access.property_visible(req.session, req.ctx, r.property_id, "scope.read")
    access.for_write(req.session, req.ctx, r.lead_id, r.property_id, "scope.edit", r)
    req.require_version(r.version)
    return r, prop


@api.route("PATCH", "/requirements/<requirement_id>", permission="scope.edit", body=S.RequirementPatchIn,
           if_match=True, requirement="SCOPE-002", summary="Edit a requirement's preferences and notes")  # fmt: skip
def patch_requirement(req: Req, requirement_id: str):
    r, prop = _requirement(req, requirement_id)
    requirements.update(req.session, req.ctx, r, req.body)
    req.session.flush()
    return ok(requirements.present(r, requirements.spaces_of(req.session, prop)))


@api.route("POST", "/requirements/<requirement_id>/decision", permission="scope.edit", body=S.RequirementDecisionIn,
           if_match=True, idempotent_create=True, requirement="SCOPE-002",
           summary="Accept, exclude or mark not applicable (a mandatory exclusion needs a reason)")  # fmt: skip
def decide_requirement(req: Req, requirement_id: str):
    r, prop = _requirement(req, requirement_id)
    requirements.decide(req.session, req.ctx, r, req.body)
    req.session.flush()
    return ok(requirements.present(r, requirements.spaces_of(req.session, prop)))


# --- scope ------------------------------------------------------------------------------------------------------------
@api.route("GET", "/properties/<property_id>/scopes", permission="scope.read", write=False, requirement="SCOPE-001",
           summary="Every scope revision of a property, with staleness")  # fmt: skip
def list_scopes(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    rows = req.session.execute(
        sa.select(Scope).where(Scope.property_id == prop.id).order_by(Scope.revision_no.desc())
    ).scalars()
    return ok([scopes.present(req.session, sc, full=False, state=lineage.scope_state(req.session, sc)) for sc in rows])


@api.route("POST", "/properties/<property_id>/scopes", permission="scope.edit", body=S.ScopeCreateIn, status=201,
           idempotent_create=True, requirement="SCOPE-002",
           summary="Draft a scope revision from the accepted requirements and the current verified measurements")  # fmt: skip
def create_scope(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "scope.read")
    access.for_write(req.session, req.ctx, prop.lead_id, prop.id, "scope.edit")
    sc = scopes.create(req.session, req.ctx, prop, req.body or S.ScopeCreateIn())
    return ok(scopes.present(req.session, sc, state=lineage.scope_state(req.session, sc)), status=201)


def _scope(req: Req, scope_id: str, permission: str = "scope.read") -> Scope:
    return access.row_visible(req.session, req.ctx, Scope, scope_id, permission)


@api.route("GET", "/scopes/<scope_id>", permission="scope.read", write=False, requirement="SCOPE-001",
           summary="One scope revision with its items, inputs and provenance")  # fmt: skip
def get_scope(req: Req, scope_id: str):
    sc = _scope(req, scope_id)
    return ok(scopes.present(req.session, sc, state=lineage.scope_state(req.session, sc)))


@api.route("POST", "/scopes/<scope_id>/refresh", permission="scope.edit", if_match=True, requirement="SCOPE-002",
           summary="Rebuild a draft from the accepted requirements and current measurements, keeping its edits")  # fmt: skip
def refresh_scope(req: Req, scope_id: str):
    sc = _scope(req, scope_id)
    prop = access.property_visible(req.session, req.ctx, sc.property_id, "scope.read")
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "scope.edit", sc)
    req.require_version(sc.version)
    scopes.refresh(req.session, req.ctx, sc, prop)
    req.session.flush()
    return ok(scopes.present(req.session, sc, state=lineage.scope_state(req.session, sc)))


@api.route("POST", "/scopes/<scope_id>/items", permission="scope.edit", body=S.ScopeItemCreateIn, status=201,
           requirement="SCOPE-002",
           summary="Add a manual or customer-requested item to a draft (recorded as an accepted requirement)")  # fmt: skip
def add_scope_item(req: Req, scope_id: str):
    sc = _scope(req, scope_id)
    prop = access.property_visible(req.session, req.ctx, sc.property_id, "scope.read")
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "scope.edit", sc)
    scopes.require_draft(sc)
    requirements.add(req.session, req.ctx, prop, req.body)
    req.session.flush()
    scopes.refresh(req.session, req.ctx, sc, prop)
    req.session.flush()
    return ok(scopes.present(req.session, sc, state=lineage.scope_state(req.session, sc)), status=201)


@api.route("PATCH", "/scope-items/<item_id>", permission="scope.edit", body=S.ScopeItemPatchIn, if_match=True,
           requirement="SCOPE-002",
           summary="Modify a draft item: options, finish, inclusion, dimension overrides (with a reason)")  # fmt: skip
def patch_scope_item(req: Req, item_id: str):
    item = req.session.get(ScopeItem, item_id)
    if item is None or item.is_deleted:
        raise not_found()
    sc = _scope(req, item.scope_id)
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "scope.edit", sc, item)
    req.require_version(item.version)
    scopes.update_item(req.session, req.ctx, item, sc, req.body)
    req.session.flush()
    r = req.session.get(Requirement, item.requirement_id)
    prop = access.property_visible(req.session, req.ctx, sc.property_id, "scope.read")
    return ok(scopes.present_item(item, r, requirements.spaces_of(req.session, prop)))


@api.route("POST", "/scopes/<scope_id>/confirm", permission="scope.confirm", if_match=True, idempotent_create=True,
           requirement="SCOPE-003",
           summary="Confirm a draft: every requirement decided, measurements still current; seals the revision")  # fmt: skip
def confirm_scope(req: Req, scope_id: str):
    sc = _scope(req, scope_id)
    prop = access.property_visible(req.session, req.ctx, sc.property_id, "scope.read")
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "scope.confirm", sc)
    req.require_version(sc.version)
    scopes.confirm(req.session, req.ctx, sc, prop)
    req.session.flush()
    return ok(scopes.present(req.session, sc, state=lineage.scope_state(req.session, sc)))


@api.route("DELETE", "/scopes/<scope_id>", permission="scope.edit", if_match=True, requirement="SCOPE-002",
           summary="Discard a draft scope revision (confirmed revisions are history and stay)")  # fmt: skip
def discard_scope(req: Req, scope_id: str):
    from veda.kernel import audit_hook

    sc = _scope(req, scope_id)
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "scope.edit", sc)
    req.require_version(sc.version)
    scopes.require_draft(sc)
    for item in scopes.items(req.session, sc):
        audit_hook.soft_delete(item)
    audit_hook.soft_delete(sc)
    req.session.flush()
    return no_content()


# --- BOQ --------------------------------------------------------------------------------------------------------------
@api.route("POST", "/scopes/<scope_id>/boqs", permission="boq.generate", status=201, idempotent_create=True,
           requirement="BOQ-002",
           summary="Generate a BOQ revision from a confirmed scope (supersedes the open one, if any)")  # fmt: skip
def generate_boq(req: Req, scope_id: str):
    sc = _scope(req, scope_id)
    prop = access.property_visible(req.session, req.ctx, sc.property_id, "scope.read")
    access.for_write(req.session, req.ctx, sc.lead_id, sc.property_id, "boq.generate", sc)
    b = boqs.generate(req.session, req.ctx, sc, prop)
    req.session.flush()
    return ok(boqs.present(req.session, b), status=201)


@api.route("GET", "/properties/<property_id>/boqs", permission="boq.read", write=False, requirement="BOQ-001",
           summary="Every BOQ revision of a property, with staleness")  # fmt: skip
def list_boqs(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "boq.read")
    rows = req.session.execute(sa.select(Boq).where(Boq.property_id == prop.id).order_by(Boq.revision_no.desc()))
    return ok([boqs.present(req.session, b, full=False) for b in rows.scalars()])


def _boq(req: Req, boq_id: str) -> Boq:
    return access.row_visible(req.session, req.ctx, Boq, boq_id, "boq.read")


@api.route("GET", "/boqs/<boq_id>", permission="boq.read", write=False, requirement="BOQ-001",
           summary="One BOQ revision: room-wise lines, project summary, derivations, issues")  # fmt: skip
def get_boq(req: Req, boq_id: str):
    return ok(boqs.present(req.session, _boq(req, boq_id)))


@api.route("GET", "/boqs/<boq_id>/diff/<other_id>", permission="boq.read", write=False, requirement="BOQ-001",
           summary="Line differences between two BOQ revisions of a property")  # fmt: skip
def diff_boqs(req: Req, boq_id: str, other_id: str):
    return ok(boqs.diff(req.session, _boq(req, boq_id), _boq(req, other_id)))


def _line(req: Req, line_id: str) -> tuple[BoqLine, Boq]:
    line = req.session.get(BoqLine, line_id)
    if line is None or line.is_deleted:
        raise not_found()
    b = _boq(req, line.boq_id)
    access.for_write(req.session, req.ctx, b.lead_id, b.property_id, "boq.override", b, line)
    req.require_version(line.version)
    return line, b


@api.route("POST", "/boq-lines/<line_id>/override", permission="boq.override", body=S.BoqOverrideIn, if_match=True,
           requirement="BOQ-003", summary="Override a line's quantity (the calculated value is kept; reason required)")  # fmt: skip
def override_line(req: Req, line_id: str):
    line, b = _line(req, line_id)
    boqs.override(req.session, req.ctx, line, b, req.body.quantity_centi, req.body.reason)
    req.session.flush()
    return ok(boqs.present(req.session, b))


@api.route("DELETE", "/boq-lines/<line_id>/override", permission="boq.override", if_match=True,
           requirement="BOQ-003", summary="Return a line to its calculated quantity")  # fmt: skip
def clear_override(req: Req, line_id: str):
    line, b = _line(req, line_id)
    boqs.clear_override(req.session, req.ctx, line, b)
    req.session.flush()
    return ok(boqs.present(req.session, b))


@api.route("POST", "/boqs/<boq_id>/review", permission="boq.review", if_match=True, idempotent_create=True,
           requirement="BOQ-004", summary="Review a BOQ: no blocking issue, lineage current; seals it for pricing")  # fmt: skip
def review_boq(req: Req, boq_id: str):
    b = _boq(req, boq_id)
    access.for_write(req.session, req.ctx, b.lead_id, b.property_id, "boq.review", b)
    req.require_version(b.version)
    boqs.review(req.session, req.ctx, b)
    req.session.flush()
    return ok(boqs.present(req.session, b))


# --- B3 estimates -----------------------------------------------------------------------------------------------------
@api.route("GET", "/mtq/commercial-policy", permission="scope.read", write=False, requirement="CEST-001",
           summary="Which owner commercial decisions are recorded (OI-MTQ-03…15); undecided ones block or disable")  # fmt: skip
def get_policy(req: Req):
    return ok(policy.public_view())


@api.route("POST", "/boqs/<boq_id>/cost-estimates", permission="cost_estimate.create", body=S.EstimateCreateIn,
           status=201, idempotent_create=True, requirement="CEST-003",
           summary="Price a reviewed BOQ with the active rate card (supersedes the open draft)")  # fmt: skip
def create_estimate(req: Req, boq_id: str):
    b = _boq(req, boq_id)
    prop = access.property_visible(req.session, req.ctx, b.property_id, "boq.read")
    access.for_write(req.session, req.ctx, b.lead_id, b.property_id, "cost_estimate.create", b)
    est = estimates.create(req.session, req.ctx, b, prop, req.body or S.EstimateCreateIn())
    req.session.flush()
    return ok(estimates.present(req.session, est, req.ctx), status=201)


@api.route("GET", "/properties/<property_id>/cost-estimates", permission="cost_estimate.read", write=False,
           requirement="CEST-001", summary="Every estimate revision of a property, with staleness and blockers")  # fmt: skip
def list_estimates(req: Req, property_id: str):
    prop = access.property_visible(req.session, req.ctx, property_id, "cost_estimate.read")
    rows = req.session.execute(
        sa.select(CostEstimate).where(CostEstimate.property_id == prop.id).order_by(CostEstimate.revision_no.desc())
    ).scalars()
    return ok([estimates.present(req.session, e, req.ctx, full=False) for e in rows])


def _estimate(req: Req, estimate_id: str) -> CostEstimate:
    return access.row_visible(req.session, req.ctx, CostEstimate, estimate_id, "cost_estimate.read")


@api.route("GET", "/cost-estimates/<estimate_id>", permission="cost_estimate.read", write=False,
           requirement="CEST-001",
           summary="One estimate: room-wise, category-wise and project views; rates only with rate.view")  # fmt: skip
def get_estimate(req: Req, estimate_id: str):
    return ok(estimates.present(req.session, _estimate(req, estimate_id), req.ctx))


@api.route("GET", "/cost-estimates/<estimate_id>/compare/<other_id>", permission="cost_estimate.read", write=False,
           requirement="CEST-001", summary="Differences between two estimate revisions (quantity, rate, discount)")  # fmt: skip
def compare_estimates(req: Req, estimate_id: str, other_id: str):
    return ok(estimates.compare(req.session, _estimate(req, estimate_id), _estimate(req, other_id)))


@api.route("GET", "/cost-estimates/<estimate_id>/reproduce", permission="cost_estimate.rate.view", write=False,
           requirement="CEST-002", summary="Recompute the estimate from its pinned rate card and compare")  # fmt: skip
def reproduce_estimate(req: Req, estimate_id: str):
    return ok(estimates.reproduce(req.session, _estimate(req, estimate_id)))


@api.route("POST", "/cost-estimates/<estimate_id>/approve", permission="cost_estimate.approve", if_match=True,
           idempotent_create=True, requirement="CEST-004",
           summary="Approve a draft estimate: lineage current, no data issue, no pending discount; seals it")  # fmt: skip
def approve_estimate(req: Req, estimate_id: str):
    est = _estimate(req, estimate_id)
    access.for_write(req.session, req.ctx, est.lead_id, est.property_id, "cost_estimate.approve", est)
    req.require_version(est.version)
    estimates.approve(req.session, req.ctx, est)
    req.session.flush()
    return ok(estimates.present(req.session, est, req.ctx))


@api.route("POST", "/cost-estimates/<estimate_id>/adjustments", permission="cost_estimate.discount.apply",
           body=S.AdjustmentIn, status=201, idempotent_create=True, requirement="CEST-005",
           summary="Propose a line, category or project discount (refused while OI-MTQ-06 is undecided)")  # fmt: skip
def propose_discount(req: Req, estimate_id: str):
    est = _estimate(req, estimate_id)
    access.for_write(req.session, req.ctx, est.lead_id, est.property_id, "cost_estimate.discount.apply", est)
    discounts.propose(req.session, req.ctx, est, req.body)
    req.session.flush()
    return ok(estimates.present(req.session, est, req.ctx), status=201)


def _adjustment(req: Req, adjustment_id: str, permission: str) -> tuple[CostEstimateAdjustment, CostEstimate]:
    adj = req.session.get(CostEstimateAdjustment, adjustment_id)
    if adj is None or adj.is_deleted:
        raise not_found()
    est = _estimate(req, adj.estimate_id)
    access.for_write(req.session, req.ctx, est.lead_id, est.property_id, permission, est, adj)
    req.require_version(adj.version)
    return adj, est


@api.route("POST", "/estimate-adjustments/<adjustment_id>/decision", permission="cost_estimate.discount.approve",
           body=S.AdjustmentDecisionIn, if_match=True, idempotent_create=True, requirement="CEST-006",
           summary="Approve or reject a proposed discount (never one's own)")  # fmt: skip
def decide_discount(req: Req, adjustment_id: str):
    adj, est = _adjustment(req, adjustment_id, "cost_estimate.discount.approve")
    discounts.decide(req.session, req.ctx, est, adj, req.body)
    req.session.flush()
    return ok(estimates.present(req.session, est, req.ctx))


@api.route("POST", "/estimate-adjustments/<adjustment_id>/withdraw", permission="cost_estimate.discount.apply",
           if_match=True, requirement="CEST-005", summary="Withdraw a live discount from a draft estimate")  # fmt: skip
def withdraw_discount(req: Req, adjustment_id: str):
    adj, est = _adjustment(req, adjustment_id, "cost_estimate.discount.apply")
    discounts.withdraw(req.session, req.ctx, est, adj)
    req.session.flush()
    return ok(estimates.present(req.session, est, req.ctx))


def _journey_estimates(s, ctx, prop):
    if ctx.scope("cost_estimate.read") is None:
        return "cost_estimates", None
    rows = s.execute(
        sa.select(CostEstimate).where(CostEstimate.property_id == prop.id).order_by(CostEstimate.revision_no.desc())
    ).scalars()
    return "cost_estimates", [estimates.present(s, e, ctx, full=False) for e in rows]


journey.SECTIONS.append(_journey_estimates)
