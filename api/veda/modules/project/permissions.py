"""Project lifecycle capabilities (PLB-32, PLB-33). Capabilities, not people: a persona is a set of these codes.

Every code supports scope. **ALL** reaches every project; **OWN** reaches a project only while the actor is an active
member of its team (``project_member``): the ownership definition the roadmap fixed for PROJ (10 §PROJ). A global
capability alone is therefore never project access, and team membership alone grants nothing (PLB-09): both are
evaluated, on the server, for every request.

Default grants use existing roles only where their meaning fits; no role is created for the ownership concepts
(commercial, design, project, site, quality, handover owner). The operations, project-management, installation and
quality personas have no repository role: their holders are granted the codes individually
(``user.permission.manage``), as for the catalog and the Customer Promise. ADMIN is not everything.

- FOUNDER (the business owner): every code, ALL.
- SALES_MANAGER (commercial approvals): books accepted quotations as projects, assigns the first team, sees the
  commercial baseline and the history, raises blockers. ALL.
- DESIGNER: on projects they are a member of: checklists, milestones, blockers (the design owner's work).
- SURVEYOR: on projects they are a member of: site readiness and blockers.
- SALES: on projects they are a member of: view and raise blockers (customer follow-up).
- ESTIMATOR: on projects they are a member of: view, with the commercial baseline.
- ADMIN: what the working roles hold, ALL (so it can still administer their accounts; never booking, stage moves,
  approvals, team assignment or handover).

Execution (PEX, 0212): ``project.manage_work`` (work packages) and ``project.verify_snag`` (independent verification of a
snag fix, and closing a snag without a fix) are FOUNDER's only by default; the operations and quality personas are
granted them individually. ACCOUNTANT holds no ``project.*`` code.
"""

from veda.platform.rbac.registry_types import PermissionDef


def _p(code: str, name: str, description: str, requirement: str) -> PermissionDef:
    return PermissionDef(code, name, description, True, None, requirement)


PERMISSIONS: tuple[PermissionDef, ...] = (
    _p("project.view", "View projects", "See projects: stage, owners, readiness, blockers, milestones, timeline",
       "PLB-010"),
    _p("project.create_from_acceptance", "Book projects", "Book an accepted quotation as a project (never any other "
       "commercial state)", "PLB-001"),
    _p("project.assign_team", "Assign project teams", "Assign and remove project owners and team members", "PLB-008"),
    _p("project.manage_stage", "Request stage transitions", "Request a project's move to its next stage (gates are "
       "evaluated by the system)", "PLB-006"),
    _p("project.approve_transition", "Approve stage transitions", "Approve or reject a transition that needs an "
       "independent approval (never one you requested)", "PLB-034"),
    _p("project.complete_checklist", "Complete checklists", "Complete and reopen checklist items", "PLB-015"),
    _p("project.checklist.not_applicable", "Mark checklist items not applicable", "Mark a required checklist item "
       "not applicable, with a reason", "PLB-015"),
    _p("project.manage_milestone", "Manage milestones", "Add milestones, plan and complete them", "PLB-013"),
    _p("project.raise_blocker", "Raise blockers", "Raise blockers and informational issues", "PLB-018"),
    _p("project.resolve_blocker", "Resolve blockers", "Update, resolve and cancel blockers", "PLB-018"),
    _p("project.manage_site_readiness", "Manage site readiness", "Record the site's readiness and the actions it "
       "needs", "PLB-017"),
    _p("project.manage_qc", "Record quality checks", "Record quality-check results and rechecks", "PLB-026"),
    _p("project.manage_snag", "Manage snags", "Raise, fix, recheck and close snags", "PLB-027"),
    _p("project.complete_handover", "Complete handovers", "Complete a project's handover", "PLB-029"),
    _p("project.view_commercial_baseline", "View project commercial baselines", "See the accepted baseline lineage "
       "with amounts, digests and variations", "PLB-003"),
    _p("project.manage_work", "Manage work packages", "Plan, start, complete, reopen and cancel a project's work "
       "packages", "PEX-010"),
    _p("project.verify_snag", "Verify snags", "Verify a snag's fix (never your own) and close a snag without a fix, "
       "with a reason", "PEX-031"),
    _p("project.view_audit", "View project history", "See the full transition and audit history of a project",
       "PLB-035"),
)  # fmt: skip

CODES = tuple(p.code for p in PERMISSIONS)
_DESIGNER = ("project.view", "project.complete_checklist", "project.manage_milestone", "project.raise_blocker")
_SURVEYOR = ("project.view", "project.manage_site_readiness", "project.raise_blocker")
_SALES = ("project.view", "project.raise_blocker")
_ESTIMATOR = ("project.view", "project.view_commercial_baseline")
_SALES_MANAGER = ("project.view", "project.create_from_acceptance", "project.assign_team",
                  "project.view_commercial_baseline", "project.view_audit", "project.raise_blocker")  # fmt: skip
# ADMIN administers the working roles' accounts, and the escalation guard refuses managing an account that holds a code
# the administrator lacks: ADMIN therefore holds exactly what the working roles hold (ALL), and nothing else.
_ADMIN = tuple(dict.fromkeys((*_DESIGNER, *_SURVEYOR, *_SALES, *_ESTIMATOR)))

MATRIX: dict[str, dict[str, str]] = {
    code: {
        "FOUNDER": "A",
        **({"ADMIN": "A"} if code in _ADMIN else {}),
        **({"SALES_MANAGER": "A"} if code in _SALES_MANAGER else {}),
        **({"DESIGNER": "O"} if code in _DESIGNER else {}),
        **({"SURVEYOR": "O"} if code in _SURVEYOR else {}),
        **({"SALES": "O"} if code in _SALES else {}),
        **({"ESTIMATOR": "O"} if code in _ESTIMATOR else {}),
    }
    for code in CODES
}

# PLB-08: what an owner of each responsibility must be able to do (validated when the owner is assigned).
RESPONSIBILITY_CAPABILITY = {
    "COMMERCIAL": "project.view_commercial_baseline",
    "DESIGN": "project.complete_checklist",
    "PROJECT": "project.manage_stage",
    "SITE": "project.manage_site_readiness",
    "QUALITY": "project.manage_qc",
    "HANDOVER": "project.complete_handover",
    "MEMBER": "project.view",
}
