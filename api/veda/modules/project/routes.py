"""Project lifecycle endpoints (staff only). Every route answers 404, before authentication, unless
VEDA_PROJECT_LIFECYCLE_ENABLED is on (off by default; production refuses it). There is no customer route.

Route permissions are the first gate; the services check the capability again **in the project's scope** (ALL, or OWN
while on the project's team), the state, the gates and four-eyes, so hiding a control in the page is never the
authorisation. Writes to an existing row need the version the user saw (If-Match); a new row needs an Idempotency-Key.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from veda.config import settings
from veda.kernel import clock
from veda.kernel.errors import ApiError
from veda.kernel.http import Api, Req, ok, problem_response, request_reaches
from veda.platform.audit.models import AuditLog

from . import access, creation, gates, present, service
from . import schemas as S
from .models import (
    ProjectBlocker,
    ProjectChecklistItem,
    ProjectMember,
    ProjectMilestone,
    ProjectSiteReadiness,
    ProjectSnag,
    ProjectTransition,
)

api = Api("project", "/api/v1", tags=("project",))
GATED_PREFIXES = ("/api/v1/projects",)


@api.blueprint.before_app_request
def _enabled():
    if not settings().project_lifecycle_enabled and request_reaches(("project",), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


def _project(req: Req, project_id: str):
    return access.visible(req.session, req.ctx, project_id)


def _detail(req: Req, p, status: int = 200, **extra: Any):
    req.session.flush()
    body = present.detail(req.session, req.ctx, p)
    return ok({**body, **extra} if extra else body, status=status)


def _transition_result(req: Req, p, t: ProjectTransition, status: int = 201):
    req.session.flush()
    people = present.People(req.session)
    audit = access.can(req.session, req.ctx, p, "project.view_audit")
    return ok({"transition": present._transition(t, people, audit), "outcome": t.outcome,
               "project": present.detail(req.session, req.ctx, p)}, status=status)  # fmt: skip


# --- reads -------------------------------------------------------------------------------------------------------------
@api.route("GET", "/projects", permission="project.view", write=False, query=S.ListQuery, requirement="PLB-010",
           summary="Authorised projects (views and filters): stage, owner, next milestone, readiness, blockers")  # fmt: skip
def list_projects(req: Req):
    return ok(present.dashboard(req.session, req.ctx, req.query or S.ListQuery()))


@api.route("GET", "/projects/vocabulary", permission="project.view", write=False, requirement="PLB-005",
           summary="The lifecycle definition in force and the codes the pages offer")  # fmt: skip
def vocabulary(req: Req):
    return ok(present.vocabulary())


@api.route("POST", "/projects", permission="project.create_from_acceptance", body=S.CreateIn, status=201,
           idempotent_create=True, requirement="PLB-001",
           summary="Book an accepted quotation as a project (refused for any other commercial state)")  # fmt: skip
def create_project(req: Req):
    p = creation.create(req.session, req.ctx, req.body.quotation_id, req.body.property_id)
    return _detail(req, p, status=201)


@api.route("GET", "/projects/<project_id>", permission="project.view", write=False, requirement="PLB-011",
           summary="One project: overview, attention, next actions, stages, checklists, blockers, baseline, timeline")  # fmt: skip
def get_project(req: Req, project_id: str):
    return ok(present.detail(req.session, req.ctx, _project(req, project_id)))


@api.route("GET", "/projects/<project_id>/readiness", permission="project.view", write=False, query=S.EvaluateQuery,
           requirement="PLB-007", summary="Evaluate the gates of a move to the next (or a named) stage; read-only")  # fmt: skip
def readiness(req: Req, project_id: str):
    p = _project(req, project_id)
    to = req.query.to_stage if req.query else None
    command = "HANDOVER" if to == "HANDED_OVER" else "STAGE"
    if to is None:
        return ok(
            {"evaluation": gates.next_evaluation(req.session, p), "handover": gates.handover_readiness(req.session, p)}
        )
    return ok({"evaluation": gates.evaluate(req.session, p, to, command=command),
               "handover": gates.handover_readiness(req.session, p)})  # fmt: skip


@api.route("GET", "/projects/<project_id>/history", permission="project.view_audit", write=False,
           requirement="PLB-035", summary="Audit history of the project's records: who changed what, when (names of "
           "fields, never their values)")  # fmt: skip
def history(req: Req, project_id: str):
    p = _project(req, project_id)
    access.require(req.session, req.ctx, p, "project.view_audit")
    people = present.People(req.session)
    rows = req.session.execute(sa.select(AuditLog).where(sa.or_(AuditLog.entity_id == p.id,
                                                                AuditLog.parent_entity_id == p.id))
                               .order_by(AuditLog.performed_on.desc()).limit(500)).scalars()  # fmt: skip
    return ok([{"entity_type": a.entity_type, "entity_id": a.entity_id, "action": a.action,
                "changed_fields": a.changed_fields or [], "by": people(a.performed_by),
                "on": clock.to_rfc3339(a.performed_on), "via": a.performed_via} for a in rows])  # fmt: skip


# --- team --------------------------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/team", permission="project.assign_team", body=S.MemberIn, if_match=True,
           requirement="PLB-008", summary="Assign an owner (one per responsibility) or a team member")  # fmt: skip
def assign(req: Req, project_id: str):
    p = _project(req, project_id)
    service.assign(req.session, req.ctx, p, req.body, req.if_match)
    return _detail(req, p)


@api.route("GET", "/projects/<project_id>/team/candidates", permission="project.assign_team", write=False,
           requirement="PLB-008", summary="People who may hold each responsibility on this project (names only)")  # fmt: skip
def team_candidates(req: Req, project_id: str):
    p = _project(req, project_id)
    access.require(req.session, req.ctx, p, "project.assign_team")
    return ok(present.candidates(req.session, p))


@api.route("POST", "/projects/<project_id>/team/<member_id>/remove", permission="project.assign_team",
           body=S.RemoveIn, if_match=True, requirement="PLB-009", summary="End an assignment, with a reason")  # fmt: skip
def remove_member(req: Req, project_id: str, member_id: str):
    p = _project(req, project_id)
    m = service.child(req.session, ProjectMember, p, member_id)
    service.remove(req.session, req.ctx, p, m, req.body.reason, req.if_match)
    return _detail(req, p)


# --- transitions and handover ------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/transitions", permission="project.manage_stage", body=S.TransitionIn,
           if_match=True, status=201, requirement="PLB-006",
           summary="Request the move to the next stage; recorded as REFUSED (with blockers), AWAITING_APPROVAL or "
           "COMPLETED")  # fmt: skip
def request_transition(req: Req, project_id: str):
    p = _project(req, project_id)
    t = service.request_transition(req.session, req.ctx, p, req.body.to_stage, req.body.reason, req.if_match)
    return _transition_result(req, p, t)


@api.route("POST", "/projects/<project_id>/handover", permission="project.complete_handover", body=S.HandoverIn,
           if_match=True, status=201, requirement="PLB-029",
           summary="Complete the handover with its evidence, through the handover gates")  # fmt: skip
def handover(req: Req, project_id: str):
    p = _project(req, project_id)
    t = service.complete_handover(req.session, req.ctx, p, req.body, req.if_match)
    return _transition_result(req, p, t)


def _pending(req: Req, project_id: str, transition_id: str):
    p = _project(req, project_id)
    return p, service.child(req.session, ProjectTransition, p, transition_id)


@api.route("POST", "/projects/<project_id>/transitions/<transition_id>/approve", permission="project.approve_transition",
           body=S.DecisionIn, if_match=True, requirement="PLB-034",
           summary="Approve a transition awaiting independent approval (every gate is evaluated again)")  # fmt: skip
def approve(req: Req, project_id: str, transition_id: str):
    p, t = _pending(req, project_id, transition_id)
    service.approve(req.session, req.ctx, p, t, (req.body or S.DecisionIn()).reason, req.if_match)
    return _transition_result(req, p, t, 200)


@api.route("POST", "/projects/<project_id>/transitions/<transition_id>/reject", permission="project.approve_transition",
           body=S.ReasonIn, if_match=True, requirement="PLB-034", summary="Reject a transition, with a reason")  # fmt: skip
def reject(req: Req, project_id: str, transition_id: str):
    p, t = _pending(req, project_id, transition_id)
    service.reject(req.session, req.ctx, p, t, req.body.reason, req.if_match)
    return _transition_result(req, p, t, 200)


@api.route("POST", "/projects/<project_id>/transitions/<transition_id>/withdraw",
           any_of=("project.manage_stage", "project.complete_handover"), body=S.ReasonIn, if_match=True,
           requirement="PLB-006", summary="Withdraw a transition awaiting approval, with a reason")  # fmt: skip
def withdraw(req: Req, project_id: str, transition_id: str):
    p, t = _pending(req, project_id, transition_id)
    service.withdraw(req.session, req.ctx, p, t, req.body.reason, req.if_match)
    return _transition_result(req, p, t, 200)


# --- checklist ---------------------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/checklist/<item_id>/complete", permission="project.complete_checklist",
           body=S.ChecklistIn, if_match=True, requirement="PLB-015",
           summary="Complete a checklist item, or mark it not applicable with a reason")  # fmt: skip
def complete_item(req: Req, project_id: str, item_id: str):
    p = _project(req, project_id)
    item = service.child(req.session, ProjectChecklistItem, p, item_id)
    service.complete_item(req.session, req.ctx, p, item, req.body, req.if_match)
    return _detail(req, p)


@api.route("POST", "/projects/<project_id>/checklist/<item_id>/reopen", permission="project.complete_checklist",
           body=S.ReasonIn, if_match=True, requirement="PLB-015", summary="Reopen a checklist item, with a reason")  # fmt: skip
def reopen_item(req: Req, project_id: str, item_id: str):
    p = _project(req, project_id)
    item = service.child(req.session, ProjectChecklistItem, p, item_id)
    service.reopen_item(req.session, req.ctx, p, item, req.body.reason, req.if_match)
    return _detail(req, p)


# --- milestones --------------------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/milestones", permission="project.manage_milestone", body=S.MilestoneIn,
           status=201, idempotent_create=True, requirement="PLB-013", summary="Add a milestone")  # fmt: skip
def add_milestone(req: Req, project_id: str):
    p = _project(req, project_id)
    service.add_milestone(req.session, req.ctx, p, req.body)
    return _detail(req, p, status=201)


@api.route("PATCH", "/projects/<project_id>/milestones/<milestone_id>", permission="project.manage_milestone",
           body=S.MilestonePatch, if_match=True, requirement="PLB-013",
           summary="Plan or change a milestone (completion is explicit: /complete)")  # fmt: skip
def update_milestone(req: Req, project_id: str, milestone_id: str):
    p = _project(req, project_id)
    m = service.child(req.session, ProjectMilestone, p, milestone_id)
    service.update_milestone(req.session, req.ctx, p, m, req.body, req.if_match)
    return _detail(req, p)


@api.route("POST", "/projects/<project_id>/milestones/<milestone_id>/complete", permission="project.manage_milestone",
           body=S.MilestoneCompleteIn, if_match=True, requirement="PLB-014",
           summary="Complete a milestone with its actual date")  # fmt: skip
def complete_milestone(req: Req, project_id: str, milestone_id: str):
    p = _project(req, project_id)
    m = service.child(req.session, ProjectMilestone, p, milestone_id)
    service.complete_milestone(req.session, req.ctx, p, m, req.body, req.if_match)
    return _detail(req, p)


# --- blockers ----------------------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/blockers", permission="project.raise_blocker", body=S.BlockerIn,
           status=201, idempotent_create=True, requirement="PLB-018",
           summary="Raise a gating blocker or an informational issue")  # fmt: skip
def raise_blocker(req: Req, project_id: str):
    p = _project(req, project_id)
    service.raise_blocker(req.session, req.ctx, p, req.body)
    return _detail(req, p, status=201)


def _blocker(req: Req, project_id: str, blocker_id: str):
    p = _project(req, project_id)
    return p, service.child(req.session, ProjectBlocker, p, blocker_id)


@api.route("PATCH", "/projects/<project_id>/blockers/<blocker_id>", permission="project.resolve_blocker",
           body=S.BlockerPatch, if_match=True, requirement="PLB-018", summary="Update a blocker's status or owner")  # fmt: skip
def update_blocker(req: Req, project_id: str, blocker_id: str):
    p, b = _blocker(req, project_id, blocker_id)
    service.update_blocker(req.session, req.ctx, p, b, req.body, req.if_match)
    return _detail(req, p)


@api.route("POST", "/projects/<project_id>/blockers/<blocker_id>/resolve", permission="project.resolve_blocker",
           body=S.ResolutionIn, if_match=True, requirement="PLB-018", summary="Resolve a blocker, saying how")  # fmt: skip
def resolve_blocker(req: Req, project_id: str, blocker_id: str):
    p, b = _blocker(req, project_id, blocker_id)
    service.close_blocker(req.session, req.ctx, p, b, "RESOLVED", req.body.resolution, req.if_match)
    return _detail(req, p)


@api.route("POST", "/projects/<project_id>/blockers/<blocker_id>/cancel", permission="project.resolve_blocker",
           body=S.ResolutionIn, if_match=True, requirement="PLB-018", summary="Cancel a blocker raised in error")  # fmt: skip
def cancel_blocker(req: Req, project_id: str, blocker_id: str):
    p, b = _blocker(req, project_id, blocker_id)
    service.close_blocker(req.session, req.ctx, p, b, "CANCELLED", req.body.resolution, req.if_match)
    return _detail(req, p)


# --- site readiness ----------------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/site-readiness", permission="project.manage_site_readiness",
           body=S.ReadinessIn, status=201, idempotent_create=True, requirement="PLB-017",
           summary="Add a site-readiness item the accepted quotation did not list")  # fmt: skip
def add_readiness(req: Req, project_id: str):
    p = _project(req, project_id)
    service.add_readiness(req.session, req.ctx, p, req.body)
    return _detail(req, p, status=201)


@api.route("PATCH", "/projects/<project_id>/site-readiness/<item_id>", permission="project.manage_site_readiness",
           body=S.ReadinessPatch, if_match=True, requirement="PLB-017",
           summary="Record the site's readiness for an item and the action it needs")  # fmt: skip
def update_readiness(req: Req, project_id: str, item_id: str):
    p = _project(req, project_id)
    r = service.child(req.session, ProjectSiteReadiness, p, item_id)
    service.update_readiness(req.session, req.ctx, p, r, req.body, req.if_match)
    return _detail(req, p)


# --- quality check and snags -------------------------------------------------------------------------------------------
@api.route("POST", "/projects/<project_id>/qc-checks", permission="project.manage_qc", body=S.QcIn, status=201,
           idempotent_create=True, requirement="PLB-026", summary="Record a quality-check result (or a recheck)")  # fmt: skip
def record_qc(req: Req, project_id: str):
    p = _project(req, project_id)
    service.record_qc(req.session, req.ctx, p, req.body)
    return _detail(req, p, status=201)


@api.route("POST", "/projects/<project_id>/snags", permission="project.manage_snag", body=S.SnagIn, status=201,
           idempotent_create=True, requirement="PLB-027", summary="Raise a snag")  # fmt: skip
def raise_snag(req: Req, project_id: str):
    p = _project(req, project_id)
    service.raise_snag(req.session, req.ctx, p, req.body)
    return _detail(req, p, status=201)


def _snag(req: Req, project_id: str, snag_id: str):
    p = _project(req, project_id)
    return p, service.child(req.session, ProjectSnag, p, snag_id)


@api.route("PATCH", "/projects/<project_id>/snags/<snag_id>", permission="project.manage_snag", body=S.SnagPatch,
           if_match=True, requirement="PLB-027", summary="Change a snag's owner, target date or details")  # fmt: skip
def update_snag(req: Req, project_id: str, snag_id: str):
    p, sn = _snag(req, project_id, snag_id)
    service.update_snag(req.session, req.ctx, p, sn, req.body, req.if_match)
    return _detail(req, p)


@api.route("POST", "/projects/<project_id>/snags/<snag_id>/status", permission="project.manage_snag",
           body=S.SnagStatusIn, if_match=True, requirement="PLB-027",
           summary="Move a snag: in progress, ready for recheck, resolved (recheck passed), closed")  # fmt: skip
def snag_status(req: Req, project_id: str, snag_id: str):
    p, sn = _snag(req, project_id, snag_id)
    service.snag_status(req.session, req.ctx, p, sn, req.body, req.if_match)
    return _detail(req, p)
