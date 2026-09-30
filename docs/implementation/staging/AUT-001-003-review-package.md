# Review package: AUT-001 … AUT-003 (staging bootstrap)

- **Instruction:** VEDA-SPACES-STAGING-AUTOMATION-IMPLEMENTATION (owner decisions D-1 … D-13 approved).
- **Base:** `origin/main` @ `c29690326e11e1cc6a995989f103c33c95118031`.
- **Branch:** `infra/staging-bootstrap-aut-001-003`.
- **Scope:** repository structure, Terraform bootstrap, bootstrap workflow, documentation. **No AWS resource
  created, no Terraform applied, nothing deployed, no application code or production system touched.**
- **Revision 2:** remediation of the independent review (verdict NOT CERTIFIED, findings F1–F16) on top of
  `fca56da`. §8 maps every finding to its fix and its regression tests. The sections below describe the remediated code.

## 1. Constraint compliance

| Constraint | How it is met |
|---|---|
| No AWS resources created / no apply | Only offline checks ran: `terraform validate`, and `terraform test` with fake credentials and overridden values. The script guard tests ran with AWS credentials disabled. |
| No deployment | No deploy workflow exists yet. `00-bootstrap` cannot run until merged to the default branch **and** given owner credentials. |
| No application code touched | Changes are confined to `infra/`, `.github/workflows/00-bootstrap.yml`, `.pre-commit-config.yaml` (hooks limited to infra paths) and two docs. `api/`, `app/`, `dist/`, `docs/architecture/` and `ci.yml` are unchanged. |
| No production / Aurion | The account is approved in a committed manifest (`infra/config/staging-account.json`, `account_id: null` until the owner commits it). Scripts, workflow and Terraform validation refuse any other account; discovery also checks the account name and alias, refuses production/Aurion-looking names and any foreign resource. `environment = "production"` is refused by validation. |
| Dedicated branch | `infra/staging-bootstrap-aut-001-003`, with no upstream set (it cannot be pushed to `main` by accident). |

## 2. Files

| Path | Item | Purpose |
|---|---|---|
| `infra/README.md` | AUT-001 | Layout, pinned versions, commands, safety rules |
| `infra/Makefile` | AUT-001 | `check` (offline: fmt, validate, test, test-scripts, lint), `bootstrap-plan/apply`, `github-environments/verify/variables` |
| `infra/.gitignore` | AUT-001 | State, plans, generated files, backend file |
| `infra/.tflint.hcl` | AUT-001 | tflint + AWS ruleset 0.49.0 |
| `.pre-commit-config.yaml` | AUT-001 | fmt/validate/tflint/checkov/shellcheck/actionlint, infra paths only |
| `infra/{terraform/modules,terraform/envs/*,host,ssm-documents,evidence,load}/README.md` | AUT-001 | Placeholders naming the backlog item that fills each directory |
| `infra/config/staging-account.json` | AUT-002/003 | **Approved account manifest** (F3, F5): account ID, name, alias, guardrail management, allowed foreign resources. `null` until the owner's reviewed commit |
| `infra/terraform/bootstrap/versions.tf` | AUT-002 | Terraform ≥ 1.10, AWS provider ~> 6.66, `allowed_account_ids`, default tags |
| `…/variables.tf` | AUT-002 | Inputs with validations (12-digit account **equal to the manifest's**, ap-south-1 only, staging only, sessions 15–60 min) |
| `…/main.tf` | AUT-002 | Manifest, names, and ARNs built from names so policies are known at plan time |
| `…/state.tf` | AUT-002 | State KMS key + alias; state bucket (versioning, SSE-KMS, TLS-only, own-account key only, lifecycle, **deny of `veda-*` bootstrap-state writes and bucket changes**) |
| `…/guardrails.tf` | AUT-002 | Account defaults, managed per the manifest, `prevent_destroy` |
| `…/oidc.tf` | AUT-002 | GitHub OIDC provider (or reuse, `prevent_destroy`) and trust pinned to repository + environment |
| `…/boundary.tf` | AUT-002 | **Self-propagating** `veda-boundary` permissions boundary |
| `…/roles.tf` | AUT-002 | `veda-gh-plan/apply/deploy/evidence` and their policies |
| `…/outputs.tf` | AUT-002 | Role ARNs, state/backend config, rendered policy documents |
| `…/terraform.tfvars.example` | AUT-002 | Override reference |
| `…/.terraform.lock.hcl` | AUT-002 | Provider hashes for linux/darwin × amd64/arm64 |
| `…/tests/bootstrap.tftest.hcl` | AUT-002 | 17 offline test runs, 7 of them IAM-evaluated (§5) |
| `…/tests/policy_eval/` | AUT-002 | Offline IAM policy evaluator (explicit deny, identity allow, boundary allow; wildcards; conditions) |
| `…/tests/negative/*.tftest.hcl` | AUT-002 | Must-fail `prevent_destroy` tests with a mock provider, run by `infra/tests/run.sh` |
| `…/tests/fixtures/*.json` | AUT-002 | Test manifests |
| `infra/scripts/lib.sh` | AUT-003 | Guards: region, approved account, account identity, fail-closed lookups, repository |
| `infra/scripts/discover.sh` | AUT-003 | Read-only discovery (AWS, GitHub, Cloudflare, operator IP) after the identity check |
| `infra/scripts/check-plan.sh` | AUT-003 | **Plan guard**: no destroy, bounded roles, no external or broad trust, no external resource policies |
| `infra/scripts/bootstrap.sh` | AUT-003 | Plan (+ metadata + guard) / apply of a reviewed plan, first-run state migration, outputs |
| `infra/scripts/github-setup.sh` | AUT-003 | Environments (admins cannot bypass), `main` protection, `--verify`, repository variables; dry run by default |
| `infra/scripts/.shellcheckrc` | AUT-003 | Source path for shellcheck |
| `infra/tests/run.sh`, `infra/tests/stubs/{aws,gh,terraform}` | AUT-003 | Offline script, plan-guard, workflow, documentation and negative-Terraform tests (§5) |
| `.github/workflows/00-bootstrap.yml` | AUT-003 | Manually started plan, then apply **of that plan run's plan file**, with temporary STS credentials |
| `docs/operations/staging-bootstrap.md` | AUT-003 | Runbook |
| `docs/implementation/staging/AUT-001-003-review-package.md` | — | This document |

## 3. Design decisions for review

1. **Local state first, then migrated.** The first apply keeps state locally and moves it into the bucket it just created, then checks
   it is there. The backend file is generated (gitignored) only once the bucket exists, so a fresh clone behaves the same on the
   first and on later runs.
2. **S3 native locking** (`use_lockfile`). There is no DynamoDB table.
3. **Policies are fully known at plan time.** ARNs are built from names (boundary, OIDC provider, state bucket), the state key is
   matched by `kms:ResourceAliases`, and the bucket policy admits only keys of this account and region (not the exact key ARN, which
   exists only after apply). The reviewer sees the exact IAM JSON in the plan, the plan guard can check it, and the tests evaluate it.
4. **Trust pinned to repository + GitHub environment.** Subject `repo:<owner>/<repo>:environment:<env>`, audience
   `sts.amazonaws.com`, no wildcards (tested). Pull-request, branch and fork tokens carry different subjects and are refused.
5. **Two environments added beyond the plan**: `staging-plan` (plans on PRs; **reviewer required**, because it reads state) and
   `staging-evidence` (evidence collection, main only). Every environment has `can_admins_bypass: false`; `main` is protected.
6. **The permissions boundary is self-propagating** (F1). Any role under it can create or re-bound a role only with `veda-boundary`,
   and can write IAM only on `veda-*` roles, policies and instance profiles. So no chain of created roles ends outside it. It also refuses:
   - other regions;
   - IAM users, keys and identity providers; Organizations and account changes;
   - the privileged AWS managed policies;
   - changes to the bootstrap identities (including new `veda-gh-*` names), bootstrap-state writes, and state bucket or key changes;
   - weakening the guardrails, CloudTrail or Access Analyzer; IMDSv1;
   - cross-account sharing, grants, writes and Lambda permissions;
   - GOVERNANCE bypass.

   It deliberately does **not** block Object Lock configuration, which AUT-103 needs; each lock bucket's own policy protects it.
7. **Data reads.** The plan, deploy and evidence roles cannot read application data or seeded secrets. The plan role is further limited
   (parameters outside `/config`, objects outside state, logs, console and command output). **The apply role is not contained by these
   denies**: it administers the account and can reach data through the host role (R1).
8. **The bootstrap state is owner-only**, enforced twice: by the boundary and by the state bucket's policy (which holds even for a
   `veda-*` role outside the boundary).
9. **Temporary credentials only.** `00-bootstrap` fails without a session token or with a non-`ASIA` key. The runbook tells the owner to
   delete the bootstrap secrets after use.
10. **Nothing is destroyed by automation.** The plan guard refuses any delete or replace. The guardrails and the OIDC provider are
    `prevent_destroy`, so a changed manifest or a discovery error fails the plan. Discovery lookups fail closed.
11. **Apply = the reviewed plan** (F4). The plan run records the commit, clean tree, account, repository, SHA-256 and state layout of
    the saved plan. The apply run applies that exact file after checking all of them, and Terraform itself refuses a stale plan.
12. **The account is approved in code** (F3), and its identity is checked live before any plan.
13. **macOS compatible:** the scripts and tests run under bash 3.2 (no `mapfile`, no associative arrays).

## 4. Security review: residual risks

| # | Risk | Severity | Treatment |
|---|---|---|---|
| R1 | `veda-gh-apply` is broad inside the account (service wildcards for the staging services). Anyone who can run an approved apply controls the staging account **within the boundary**, including reading application data through the host role. It cannot leave the boundary (F1 fixed, tested). | Medium | Accepted by design. Controls: `staging-infra` reviewer approval (admins cannot bypass), main-only branch policy on a protected `main`, one-hour sessions, the self-propagating boundary, and a reviewed, guarded plan (AUT-301). |
| R2 | IAM has no condition key for trust-policy content, so the boundary cannot stop a new `veda-*` role trusting another account or a broad GitHub subject. | Medium → Low | `check-plan.sh` refuses such trust (tested). It runs on every bootstrap plan. **AUT-301 must run it on every staging plan.** Access Analyzer (account analyzer, findings cannot be archived by roles) reports external trust. An SCP/RCP would make it absolute; the account is not assumed to be in an Organization. |
| R3 | Terraform state will contain Cloudflare-generated secrets. The plan role reads state. | Low–Medium | Plan runs now need a `staging-plan` reviewer. State is KMS-encrypted and readable only by these roles. Parameter values outside `/config` are denied to the plan role. |
| R4 | `ReadOnlyAccess` on the plan role. | Low | Explicit denies remove parameter values, object reads outside state, logs, console/command output and data-plane reads (tested). |
| R5 | `prevent_self_review: false` lets a single owner approve their own runs. | Low | Required for a single-owner repository. Change it once a second reviewer exists. |
| R6 | The boundary's region deny exempts only listed global services. | Low | Found at the first AUT-1xx plan; fixed by extending `global_actions` in a reviewed change. |
| R7 | The account default IMDSv2 hop limit is 2. | Info | Matches the staging design (RR-09). IMDSv1 is now refused by the boundary. |
| R8 | The state bucket has no server-access logging. | Low | Checkov skip with justification. AUT-104 adds CloudTrail S3 data events for the state bucket. |
| R9 | The boundary is 5,536 of the 6,144 characters IAM allows. | Low | Asserted in the tests. A later addition that does not fit must replace a statement, not be dropped. |
| R10 | The state bucket admits any KMS key of this account and region in a PutObject header, not only the state key (the exact key ARN is not known at plan time). | Low | Default encryption uses the state key; keys of other accounts are refused; state-key tampering and bucket changes are denied. |
| R11 | AUT-104's trail cannot be updated or re-scoped by any Veda role. | Info (constraint) | Deliberate (F6): event selectors are set at creation; later changes are owner-run (runbook §8). |
| R12 | The OIDC trust names the repository, not its numeric ID (F12). A deleted or renamed repository or owner could be re-registered. | Low | Not remediated here. Keep the repository and `slaggala` account; a later change can pin `repository_id` with a custom `sub` claim. |
| R13 | Account identity relies on the committed name, alias and an empty account; there is no Organizations OU check. | Low | The account may be standalone. Add an OU check if the account is moved into an Organization. |

## 5. Validation results

All checks are offline. No AWS, GitHub or Cloudflare API was called with credentials: the Terraform tests use fake
credentials and overridden or mocked values, and the script tests use stub `aws`, `gh` and `terraform` commands.

| Check | Result |
|---|---|
| `terraform fmt -check -recursive` (1.16.4) | Pass |
| `terraform init -backend=false` + `validate` | Pass: "The configuration is valid." |
| `terraform test` (17 runs) | **17 passed, 0 failed**. Includes 7 runs that evaluate the rendered policies with `tests/policy_eval` (99 IAM requests, §8) |
| Mutation check of the evaluator | Against the original `fca56da` boundary and bucket policy, the F1, F2, F6 and F7 runs **fail** (e.g. "unbounded admin role: expected deny, got allow"). With the plan-role denies and `aws:ResourceAccount` conditions removed, the F7 and F9 runs fail. The tests detect the reviewed weaknesses, not just the new strings. |
| Negative `prevent_destroy` tests (mock provider) | Turning guardrails off and passing our OIDC provider as "existing" both **fail the plan** with "Instance cannot be destroyed", after a successful first apply |
| `infra/tests/run.sh` | **103 passed, 0 failed** (account identity, fail-closed lookups, plan guard, reviewed-plan apply, GitHub settings, workflow, documentation) |
| Policy size | Every managed policy < 6,144 characters (asserted). Boundary 5,536; deploy 2,974; plan 2,635; evidence 2,243; apply-services 1,872; apply-iam 1,848; state bucket policy 1,290 |
| tflint 0.64.0 + AWS ruleset 0.49.0 | Pass, 0 issues |
| checkov 3.3.20 | **167 passed, 0 failed, 23 skipped** (skips unchanged, each inline with its reason) |
| shellcheck 0.11.0 (scripts, tests, stubs) | Pass |
| actionlint 1.7.12 (with shellcheck) on `00-bootstrap.yml` | Pass |
| `make -C infra check` | **Exit 0** |

**Not validated (needs a real account, so it is part of the first owner-run bootstrap):**
- `terraform plan` or `apply` against AWS, and the plan guard on a real plan (its rules are tested on constructed plans shaped like the bootstrap's);
- IAM's own evaluation of the boundary (the offline evaluator implements the operators these policies use; `aws iam simulate-custom-policy` on the rendered `policy_documents` output is a useful first post-apply check);
- `account get-account-information`, the foreign-resource listing and the other discovery calls against a real account;
- OIDC token exchange end to end; state migration; the Cloudflare discovery API calls;
- running `00-bootstrap` in GitHub (it must be on the default branch), including `gh run download` of the plan artifact.

## 6. Reviewer checklist

- [ ] `infra/config/staging-account.json` holds the right account ID, name and alias (owner commit, reviewed).
- [ ] The trust subjects in `oidc.tf` name the right repository and environments.
- [ ] `boundary.tf` is self-propagating (`DenyRoleWithoutBoundary`, `DenyIamWritesOutsideVeda`) and nothing needed by AUT-101 … AUT-112 is blocked (R6, R11).
- [ ] `apply_iam` only allows creating roles that carry the boundary.
- [ ] The deploy and evidence roles can run only `veda-*` documents on the tagged host, and touch S3 only in this account.
- [ ] Application data and `/veda/staging/app/*` are denied to the plan, deploy and evidence roles; the apply-role exception (R1) is accepted.
- [ ] `bootstrap.sh` applies only a plan that was shown, or a reviewed plan whose checksum, commit, account and state layout match.
- [ ] `check-plan.sh` refuses deletes, unbounded roles, external or broad trust, and external resource policies.
- [ ] `00-bootstrap.yml` refuses long-lived keys, runs only from a protected `main`, and applies only the plan of a named plan run.
- [ ] Residual risks R1–R13 are accepted, or follow-ups are assigned (R2 → AUT-301, R8 → AUT-104, R12 → later).

## 7. Remaining work

| Item | Notes |
|---|---|
| Owner: commit the account manifest | `account_id`, `account_name`, `account_alias` in a reviewed PR (runbook §2). Nothing runs before it |
| Owner-run bootstrap | Needs a temporary session and, optionally, a read-only Cloudflare token (runbook §2). Run it locally first (Option A) |
| AUT-101 … AUT-112 | Core AWS modules and the `staging-core` root |
| AUT-201 … AUT-205 | Cloudflare modules and the `staging-edge` root (constraint: runbook §8) |
| AUT-301 | `10-infra-plan`/`11-infra-apply`, **running `check-plan.sh` on every plan, applying only reviewed saved plans**, and the live-site DNS guard |
| AUT-302 … AUT-306 | Secrets seed, release, deploy, app, smoke |
| AUT-401 … AUT-406 | Evidence and drills |

## 8. Remediation of the independent review (revision 2)

| Finding | Fix | Regression tests |
|---|---|---|
| **F1** (Critical) boundary does not carry over; apply role → full admin | `veda-boundary` denies `iam:CreateRole`/`PutRolePermissionsBoundary` without itself, and every IAM write outside `veda-*` roles/policies/instance profiles. The privileged-managed-policy deny moved into it (plus `job-function/*`). `veda-gh-*` names cannot be created, and GitHub roles cannot be passed | `f1_apply_role_cannot_escape_boundary` (12 requests), `f1_escalated_role_stays_inside_boundary` (20 requests: the review's exact escalation, a role with `*:*` under the boundary) |
| **F2** (High) bootstrap state writable by the apply role; bucket configuration changeable | Boundary: `DenyBootstrapStateWrites` and a wider `DenyStateTampering` (every `PutBucket*`, `Put*Configuration`, ACLs, retention, versions). The bucket policy denies the same to any `veda-*` principal | `f2_apply_role_cannot_touch_bootstrap_state` (17), `f2_bucket_policy_protects_bootstrap_state` (5) |
| **F3** (High) target account never verified | Committed manifest; Terraform validation and every script and workflow step check it. Live identity checks: name, alias, production/Aurion names, foreign roles/users/buckets/instances/functions, all fail closed | `rejects_account_missing_from_manifest`, `rejects_account_other_than_manifest`; 15 `run.sh` checks (F3 section) |
| **F4** (High) unreviewed plan applied; no delete gate | Plan run writes plan + metadata (commit, clean tree, account, SHA-256, state layout). Apply verifies them, then applies that file only. `--yes` requires it. The workflow fetches the plan of a named, successful plan run on `main` for the same commit. `check-plan.sh` refuses deletes and replaces. The OIDC tag lookup fails closed, and the provider is `prevent_destroy` | 13 reviewed-plan checks, 3 fail-closed lookup checks, 2 delete/replace guard checks, negative `oidc_destroy`, 11 workflow checks |
| **F5** (Medium) `--skip-guardrails` destroys guardrails | Flag removed. The choice is `manage_account_guardrails` in the manifest. Every guardrail is `prevent_destroy`, and the delete gate also applies. Runbook §6 corrected | `guardrails_can_be_disabled` (manifest), negative `guardrails_destroy` (6 resources), `prevent_destroy` coverage check, `--skip-guardrails` refusal |
| **F6** (Medium) guardrail/audit denies bypassable | Adds `ec2:EnableSnapshotBlockPublicAccess`, CloudTrail delete/update/selectors/tags/event data stores, Access Analyzer archive rules and `UpdateFindings`, IMDSv1 at launch or on an instance | `f6_f7_boundary_guardrails_and_cross_account` (15 F6 requests, including 2 proving the evidence role still reads trail and analyzer configuration) |
| **F7** (Medium) cross-account exits | Boundary denies snapshot/AMI attribute sharing, KMS grants outside the account (unless for an AWS resource), S3 writes to other accounts, Lambda permissions for other accounts, public function URLs. `aws:ResourceAccount` on every S3 allow of the state, deploy and evidence roles. Plan guard refuses external trust and resource policies | `f6_f7_…` (9 F7 requests), `f7_deploy_and_evidence_s3_is_account_bound` (7), 12 plan-guard checks (and 5 for GitHub trust, R2) |
| **F8** (Medium) apply-role data claim overstated | Runbook §7, this package §3.7 and R1, and the `roles.tf` header state the exception | 3 documentation checks |
| **F9** (Medium) `staging-plan` too broad | Reviewer required on `staging-plan`. The plan role is denied parameter values outside `/config`, objects outside state, logs, console/command output and data-plane reads | `f9_plan_role_cannot_read_secrets_or_data` (14), GitHub dry-run and `--verify` checks |
| **F10** (Medium) GitHub protections weak | `can_admins_bypass: false` on every environment. `main` protection (PR required, enforced for admins, no force push or deletion) applied and checked by the workflow preflight. `--verify` reads everything back. Role ARNs are repository variables, so `GH_ADMIN_TOKEN` needs only *Variables: write* | 18 GitHub checks (dry run, variables, `--verify` of a compliant repository and 7 drift cases), workflow preflight checks |
| F11 (Low) 403 read as "absent" | `head-bucket --expected-bucket-owner`; 404 = absent, anything else stops the run | 3 state-bucket checks |
| F13 (Low) Cloudflare pagination | All pages of DNS records are read | Not covered offline (Cloudflare API) |
| F15 (Low) session length unvalidated | 900–3600 s validation | `rejects_session_longer_than_one_hour` |
| F12, F14, F16 (Low/info) | Not changed; recorded as R12, R13 and in §5 | — |
