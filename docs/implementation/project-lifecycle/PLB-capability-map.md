# Project Lifecycle: capability map (PLB-32, PLB-33)

There are sixteen `project.*` capabilities, all scoped:

- **ALL** reaches every project.
- **OWN** reaches a project only while the person is an active member of its team.

Visibility needs `project.view` in scope. Every action needs its own capability in the project's scope, and the server
checks both on every request. Team membership grants nothing by itself, and no code is sensitive-classed.

| Capability | Allows | FOUNDER | SALES_MANAGER | ADMIN | DESIGNER | SURVEYOR | SALES | ESTIMATOR |
|---|---|---|---|---|---|---|---|---|
| `project.view` | See projects | ALL | ALL | ALL | OWN | OWN | OWN | OWN |
| `project.create_from_acceptance` | Book an accepted quotation | ALL | ALL | | | | | |
| `project.assign_team` | Assign or end owners and members | ALL | ALL | | | | | |
| `project.manage_stage` | Request a stage move | ALL | | | | | | |
| `project.approve_transition` | Approve or reject a move (never your own) | ALL | | | | | | |
| `project.complete_checklist` | Complete or reopen checklist items | ALL | | ALL | OWN | | | |
| `project.checklist.not_applicable` | Waive a required item, with a reason | ALL | | | | | | |
| `project.manage_milestone` | Milestones | ALL | | ALL | OWN | | | |
| `project.raise_blocker` | Raise blockers | ALL | ALL | ALL | OWN | OWN | OWN | |
| `project.resolve_blocker` | Update, resolve or cancel blockers | ALL | | | | | | |
| `project.manage_site_readiness` | Site readiness | ALL | | ALL | | OWN | | |
| `project.manage_qc` | Quality checks | ALL | | | | | | |
| `project.manage_snag` | Snags | ALL | | | | | | |
| `project.complete_handover` | Handover | ALL | | | | | | |
| `project.view_commercial_baseline` | Baseline amounts and digests | ALL | ALL | ALL | | | | OWN |
| `project.view_audit` | Full transition evaluations and audit history | ALL | ALL | | | | | |

ADMIN holds exactly what the working roles hold. The account-management escalation guard refuses to let an
administrator manage an account that holds a code the administrator lacks, so without these codes ADMIN could no longer
manage designers, surveyors, sales or estimators. ADMIN never books, moves stages, approves, assigns teams or hands over.

Operations and project leads, installation and quality staff have no repository role. They are granted individually
(`user.permission.manage`), typically at OWN:

- `project.manage_stage`, `project.complete_checklist`, `project.checklist.not_applicable` and
  `project.manage_milestone`;
- `project.raise_blocker`, `project.resolve_blocker` and `project.manage_site_readiness`;
- `project.manage_qc`, `project.manage_snag` and `project.complete_handover`.

The independent approver is granted `project.approve_transition`.

## What an owner must hold (validated at assignment)

| Responsibility | Capability |
|---|---|
| COMMERCIAL | `project.view_commercial_baseline` |
| DESIGN | `project.complete_checklist` |
| PROJECT | `project.manage_stage` |
| SITE | `project.manage_site_readiness` |
| QUALITY | `project.manage_qc` |
| HANDOVER | `project.complete_handover` |
| MEMBER | `project.view` |
