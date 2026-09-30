# Review package: AUT-001 … AUT-003 (staging bootstrap)

- **Instruction:** VEDA-SPACES-STAGING-AUTOMATION-IMPLEMENTATION (owner decisions D-1 … D-13 approved).
- **Base:** `origin/main` @ `c29690326e11e1cc6a995989f103c33c95118031`.
- **Branch:** `infra/staging-bootstrap-aut-001-003`.
- **Scope:** repository structure, Terraform bootstrap, bootstrap workflow, documentation. **No AWS resource
  created, no Terraform applied, nothing deployed, no application code or production system touched.**

## 1. Constraint compliance

| Constraint | How it is met |
|---|---|
| No AWS resources created / no apply | Only offline checks ran: `terraform validate`, and `terraform test` with fake credentials and overridden values. The script guard tests ran with AWS credentials disabled. |
| No deployment | No deploy workflow exists yet. `00-bootstrap` cannot run until merged to the default branch **and** given owner credentials. |
| No application code touched | Changes are confined to `infra/`, `.github/workflows/00-bootstrap.yml`, `.pre-commit-config.yaml` (hooks limited to infra paths) and two docs. `api/`, `app/`, `dist/`, `docs/architecture/` and `ci.yml` are unchanged. |
| No production / Aurion | Every script and the provider are pinned to one expected account and to ap-south-1. `environment = "production"` is refused by validation. No GCP or Aurion reference exists. |
| Dedicated branch | `infra/staging-bootstrap-aut-001-003`, with no upstream set (it cannot be pushed to `main` by accident). |

## 2. Files

| Path | Item | Purpose |
|---|---|---|
| `infra/README.md` | AUT-001 | Layout, pinned versions, commands, safety rules |
| `infra/Makefile` | AUT-001 | `check` (offline), `bootstrap-plan/apply`, `github-environments/variables` |
| `infra/.gitignore` | AUT-001 | State, plans, generated files, backend file |
| `infra/.tflint.hcl` | AUT-001 | tflint + AWS ruleset 0.49.0 |
| `.pre-commit-config.yaml` | AUT-001 | fmt/validate/tflint/checkov/shellcheck/actionlint, infra paths only |
| `infra/{terraform/modules,terraform/envs/*,host,ssm-documents,evidence,load}/README.md` | AUT-001 | Placeholders naming the backlog item that fills each directory |
| `infra/terraform/bootstrap/versions.tf` | AUT-002 | Terraform ≥ 1.10, AWS provider ~> 6.66, `allowed_account_ids`, default tags |
| `…/variables.tf` | AUT-002 | Inputs with validations (12-digit account, ap-south-1 only, staging only) |
| `…/main.tf` | AUT-002 | Names, and ARNs built from names so policies are known at plan time |
| `…/state.tf` | AUT-002 | State KMS key + alias; state bucket (versioning, SSE-KMS, TLS-only, wrong-key deny, lifecycle) |
| `…/guardrails.tf` | AUT-002 | Account defaults: S3/EBS-snapshot/AMI public blocks, EBS encryption, IMDSv2, Access Analyzer |
| `…/oidc.tf` | AUT-002 | GitHub OIDC provider (or reuse) and trust pinned to repository + environment |
| `…/boundary.tf` | AUT-002 | `veda-boundary` permissions boundary |
| `…/roles.tf` | AUT-002 | `veda-gh-plan/apply/deploy/evidence` and their policies |
| `…/outputs.tf` | AUT-002 | Role ARNs, state/backend config |
| `…/terraform.tfvars.example` | AUT-002 | Override reference |
| `…/.terraform.lock.hcl` | AUT-002 | Provider hashes for linux/darwin × amd64/arm64 |
| `…/tests/bootstrap.tftest.hcl` | AUT-002 | 7 offline test runs |
| `infra/scripts/lib.sh` | AUT-003 | Guards: region, account, repository |
| `infra/scripts/discover.sh` | AUT-003 | Read-only discovery (AWS, GitHub, Cloudflare, operator IP) |
| `infra/scripts/bootstrap.sh` | AUT-003 | Plan/apply, first-run state migration, outputs |
| `infra/scripts/github-setup.sh` | AUT-003 | Environments and variables; dry run by default |
| `infra/scripts/.shellcheckrc` | AUT-003 | Source path for shellcheck |
| `.github/workflows/00-bootstrap.yml` | AUT-003 | Manually started plan/apply with temporary STS credentials |
| `docs/operations/staging-bootstrap.md` | AUT-003 | Runbook |
| `docs/implementation/staging/AUT-001-003-review-package.md` | — | This document |

## 3. Design decisions for review

1. **Local state first, then migrated.** The first apply keeps state locally and moves it into the bucket it just created, then checks
   it is there. The backend file is generated (gitignored) only once the bucket exists, so a fresh clone behaves the same on the
   first and on later runs.
2. **S3 native locking** (`use_lockfile`). There is no DynamoDB table.
3. **Policies are fully known at plan time.** ARNs are built from names (boundary, OIDC provider), and the state key is matched by
   `kms:ResourceAliases`. The reviewer therefore sees the exact IAM JSON in the plan, not "known after apply". The tests depend on this too.
4. **Trust pinned to repository + GitHub environment.** Subject `repo:<owner>/<repo>:environment:<env>`, audience
   `sts.amazonaws.com`, no wildcards (tested). Pull-request, branch and fork tokens carry different subjects and are refused.
5. **Two environments added beyond the plan**, so the read-only roles need no approval while the writing roles do:
   `staging-plan` (for plans on PRs) and `staging-evidence` (for evidence collection).
6. **Permissions boundary on every Veda role**, including roles the apply role creates later (`iam:PermissionsBoundary`
   condition). It refuses:
   - other regions;
   - IAM users, keys and identity providers;
   - Organizations and account changes;
   - changes to the bootstrap identities, the state bucket or key, and the guardrails;
   - `cloudtrail:StopLogging`;
   - GOVERNANCE bypass.

   It deliberately does **not** block Object Lock configuration, which AUT-103 needs; each lock bucket's own policy protects it.
7. **CI roles cannot read application data or seeded secrets.** Every role is explicitly denied objects in the Litestream, snapshot and anchor
   buckets, `/veda/staging/app/*` and Secrets Manager values. This constrains AUT-107: seeded app secrets are never Terraform-managed.
8. **The bootstrap state is owner-only.** Workflow roles write only `staging/*` state keys and lock files.
9. **Temporary credentials only.** `00-bootstrap` fails without a session token. The runbook tells the owner to delete the bootstrap
   secrets after use.
10. **Re-runs don't delete the OIDC provider.** Discovery recognises a provider the bootstrap created (by tag) and keeps managing it.
    Only a provider that predates the bootstrap is passed in as existing.
11. **macOS compatible:** the scripts run under bash 3.2 (no `mapfile`, no associative arrays).

## 4. Security review: residual risks

| # | Risk | Severity | Treatment |
|---|---|---|---|
| R1 | `veda-gh-apply` is broad inside the account (service wildcards for the staging services). Anyone who can run an approved apply controls the staging account within the boundary. | Medium | Accepted by design. Controls: `staging-infra` reviewer approval, main-only branch policy, one-hour sessions, the boundary's denies, and a reviewed plan. |
| R2 | The apply role could create a new `veda-*` role whose trust admits a broader GitHub subject (for example `pull_request`), skipping the environment approval. | Medium | IAM has no condition key for trust-policy content. **AUT-301 must add a plan check** that fails when any role outside bootstrap trusts `token.actions.githubusercontent.com`. |
| R3 | Terraform state will later contain Cloudflare-generated secrets (tunnel token, Turnstile secret). The plan role can read state, and PR authors can trigger plans. | Low–Medium | Staging only. State is KMS-encrypted and readable only by these roles. **AUT-201/203 write those values under `/veda/staging/edge/*`**, and only repository writers can run plans. Documented, not solved. |
| R4 | `ReadOnlyAccess` on the plan role includes object reads on buckets other than the three data buckets (artifacts, evidence, CloudTrail logs). | Low | These hold no application data or secrets. The data buckets are explicitly denied. |
| R5 | `prevent_self_review: false` lets a single owner approve their own runs. | Low | Required for a single-owner repository. Change it once a second reviewer exists. |
| R6 | The boundary's region deny exempts only listed global services. A global API the later stacks need (for example a Budgets or Cost Explorer variant not in the list) would be refused. | Low | Found at the first AUT-1xx plan and fixed by extending `global_actions` in a reviewed change. |
| R7 | The account default IMDSv2 hop limit is 2, so containers can reach the instance role (needed for Litestream, S3, KMS, SES). | Info | Matches the staging design. It is also why RR-09 needs a code fix, not an infrastructure one. |
| R8 | The state bucket has no server-access logging. | Low | Checkov skip with justification. AUT-104 adds CloudTrail S3 data events for the state bucket. |

## 5. Validation results

All checks are offline. No AWS account was contacted with credentials.

| Check | Result |
|---|---|
| `terraform fmt -check -recursive` (1.16.4) | Pass |
| `terraform init -backend=false` + `validate` | Pass: "The configuration is valid." |
| `terraform test` (7 runs: defaults, bootstrap-state isolation, OIDC reuse, guardrails off, other region, bad account, production refused) | **7 passed, 0 failed** |
| Policy size (every managed policy < 6,144 characters, asserted in the tests) | Pass |
| tflint 0.64.0 + AWS ruleset 0.49.0 | Pass, 0 issues |
| checkov 3.3.20 | **167 passed, 0 failed, 23 skipped.** Every skip is inline with its reason: 8 boundary (`Allow *` ceiling), 6 apply services, 3 resource `*` where required, 3 KMS root statement, 3 state-bucket items (CRR, events, access logs). |
| shellcheck 0.11.0 (from the repository root and from `infra/scripts`) | Pass |
| `bash -n` with macOS bash 3.2.57 | Pass: all 4 scripts |
| actionlint 1.7.12 (with shellcheck) on `00-bootstrap.yml` and `ci.yml` | Pass |
| `make -C infra check` | **Exit 0** |
| Script guards, credentials disabled: bad account ID, bad mode, wrong region, no credentials, unknown argument, missing outputs file | Each refused with exit 1 and a clear message |
| `github-setup.sh` dry run (read-only GitHub lookups) | Prints the 9 environment calls and 8 variable calls; changes nothing |

**Not validated (needs a real account, so it is part of the first owner-run bootstrap):**
- `terraform plan` or `apply` against AWS;
- OIDC token exchange end to end;
- region-deny behaviour against real API calls;
- state migration;
- the Cloudflare discovery API calls;
- running `00-bootstrap` in GitHub, which requires it on the default branch.

## 6. Reviewer checklist

- [ ] The trust subjects in `oidc.tf` name the right repository and environments.
- [ ] The boundary denies in `boundary.tf` match the intended guardrails, and nothing needed by AUT-101 … AUT-112 is blocked (R6).
- [ ] `apply_iam` only allows creating roles that carry the boundary.
- [ ] The deploy and evidence roles can run only `veda-*` documents on the tagged host.
- [ ] Every role is denied application data and `/veda/staging/app/*`.
- [ ] `bootstrap.sh` cannot apply without the account guard, and asks for confirmation unless `--yes` is given.
- [ ] `00-bootstrap.yml` refuses long-lived keys, defaults to `plan`, and uses pinned actions.
- [ ] Residual risks R1–R8 are accepted, or follow-ups are assigned (R2 → AUT-301, R3 → AUT-201/203, R8 → AUT-104).

## 7. Remaining work

| Item | Notes |
|---|---|
| Owner-run bootstrap | Needs the account ID, a temporary session and, optionally, a Cloudflare read token (runbook §2). Run it locally first (Option A). |
| AUT-101 … AUT-112 | Core AWS modules and the `staging-core` root |
| AUT-201 … AUT-205 | Cloudflare modules and the `staging-edge` root |
| AUT-301 | `10-infra-plan`/`11-infra-apply`, **including the R2 trust-policy guard and the live-site DNS guard** |
| AUT-302 … AUT-306 | Secrets seed, release, deploy, app, smoke |
| AUT-401 … AUT-406 | Evidence and drills |
