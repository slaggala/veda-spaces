# AUT-001..003 staging bootstrap: owner decisions

- **Date:** 2026-09-30
- **Owner:** repository owner (`slaggala`), the sole collaborator and the reviewer of every GitHub environment
- **Context:** the independent certification of `e8157f31a9e6df23d79c2b4d79bed896a7b65cb0` returned *CERTIFIED WITH
  PRE-BOOTSTRAP CONDITIONS* (PB-01 to PB-11). These decisions close the owner-decision part of PB-05. Where a decision
  is enforced by code, the enforcing check is named. Nothing here authorizes running the bootstrap.

## Decisions

| ID | Decision | Enforced by |
|---|---|---|
| OD-B1 | **AWS region: ap-south-1 (Mumbai) only.** Every regional resource of every Veda stack lives there. Global services (IAM, STS, billing, support, read-only Organizations/account) are the only exceptions. Using an India region is not, by itself, a claim of legal or regulatory compliance | Terraform `aws_region` validation and the manifest `region`; `check-plan.sh` refuses any other provider region, module provider or per-resource region; `veda-boundary` region deny for every Veda role; the region-deny session policy on the owner session, proved at run time (`require_region_guarded_session`) |
| OD-B2 | **Organizations: member account** (revised 2026-10-02; was "standalone"). The account first used turned out to be the management account of organization `o-q9ji0hj18c` (`749251636763`). AWS advises against workloads in a management account, and SCPs do not apply to it. The owner chose to keep the organization and create a dedicated member account, **`veda-staging` (`813238078849`)**, for Veda staging. The management account holds no Veda resources. This also makes an SCP/RCP backstop available for the AUT-301 gate (OD-B7, RR-C/RR-D) | Manifest `organizations_mode: member`, `organization_id`, `management_account_id`; `check-manifest.sh` refuses any other mode and the management account as the staging account; discovery requires membership of exactly that organization with that management account (`require_organization_member`) |
| OD-B3 | **Cloudflare: no write token for the bootstrap.** The first run uses no Cloudflare token at all. A read-only token (Zone:Read, DNS:Read on `vedaspaces.com`) may be used later for discovery | Runbook §2 and §3; nothing in the bootstrap writes to Cloudflare |
| OD-B4 | **Bootstrap: controlled local first run** (runbook §3, Option A). No AWS credential is stored in GitHub for it; `GH_ADMIN_TOKEN` is not created | The `00-bootstrap` workflow refuses to run from a public repository (the repository is public) |
| OD-B5 | **Single-owner review model accepted** (RR-F, RR-G): `prevent_self_review: false` on every environment and 0 required approvals on `main`, while the owner is the only collaborator. To be revisited before any collaborator or second reviewer is added | `github-setup.sh` (environments created 2026-09-30) |
| OD-B6 | **CloudTrail until AUT-104** (RR-H): rely on CloudTrail Event History (90-day management events) and export the bootstrap session's events as first-run evidence. No trail is created before bootstrap | Runbook first-run evidence step |
| OD-B7 | **AUT-301 trust-writing gap** (RR-D, with N-01): raw API trust writes by `veda-gh-apply` are **decided before AUT-301**, as a gate: no workflow may assume `veda-gh-apply` until it is closed or explicitly accepted. It does not affect the bootstrap, which never assumes the apply role | Gate recorded here and in the closure matrix |
| OD-B8 | **Owner principal:** a dedicated IAM role in the staging account, not the root user and not an IAM user. It allows sessions of one hour at most and is trusted only by principals of the account | Manifest schema (roles only); Terraform preconditions (session must be a manifest role, not root); discovery (`require_owner_session`: role ARN, `MaxSessionDuration` ≤ 3600, trust inside the account) |

## Acknowledgements still open (do not block the bootstrap)

| ID | Item | Gate |
|---|---|---|
| RR-A | The repository will not be renamed, transferred or deleted while the OIDC roles trust `repo:slaggala/veda-spaces:…` by name. The bootstrap scripts and workflow now also check the repository's numeric ID (1392733148), but the AWS trust policies still match on the name. **2026-10-04: resolved in code by adopting GitHub's immutable subject (`repo:slaggala@37840263/veda-spaces@1392733148:…`), which the repository already issues; effective once the bootstrap is re-applied ([AUT-002-trust-subject-reapply.md](AUT-002-trust-subject-reapply.md)). Re-applied by the owner on 2026-10-04: RR-A is closed by immutable GitHub subject ID trust** | Before AUT-301 (move to a custom OIDC `sub` claim that includes `repository_id`) |
| RR-C | With the member account, an SCP or RCP from the management account can close the AUT-301 trust-writing gap; choosing and applying one is part of OD-B7 | Before AUT-301 |
| RR-I | The boundary uses 5,947 of the 6,144 characters IAM allows. Any addition must compress or replace a statement | Before any boundary change |

## Owner actions taken (2026-10-02)

In the management account `749251636763`, by the owner as root: member account `veda-staging` (`813238078849`)
created through Organizations (root email `interiors+veda-staging@vedaspaces.com`, access role
`OrganizationAccountAccessRole`); IAM user `org-admin` that can only switch into that role, with MFA. In
`veda-staging`, through that role: account alias `veda-staging`; IAM user `bootstrap-operator` that can only
assume `bootstrap-owner` with MFA; role `bootstrap-owner` (path `/`, one-hour sessions, trusted only by
`bootstrap-operator` with MFA, `AdministratorAccess`). No Veda infrastructure was created.

## Values the owner had to commit (PB-01)

`account_id`, `account_name`, `account_alias` (required) and `bootstrap_principal_arns` in
`infra/config/staging-account.json`, through a reviewed pull request. `infra/scripts/check-manifest.sh --complete`
must pass. These are not secrets, but only the owner knows them. **Done in PR #3** (2026-10-02).

## Decisions of 2026-10-03

RD-04 (independent review of the pre-bootstrap closure) **waived**, and the first controlled bootstrap **authorized**:
see [AUT-002-bootstrap-authorization.md](AUT-002-bootstrap-authorization.md).
