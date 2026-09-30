# Review package: AUT-001 … AUT-003 (staging bootstrap)

- **Instruction:** VEDA-SPACES-STAGING-AUTOMATION-IMPLEMENTATION (owner decisions D-1 … D-13 approved).
- **Base:** `origin/main` @ `c29690326e11e1cc6a995989f103c33c95118031`.
- **Branch:** `infra/staging-bootstrap-aut-001-003`.
- **Scope:** repository structure, Terraform bootstrap, bootstrap workflow, documentation. **No AWS resource
  created, no Terraform applied, nothing deployed, no application code or production system touched.**
- **Revision 2:** remediation of the independent review (verdict NOT CERTIFIED, findings F1–F16) on top of
  `fca56da`. §8 maps every finding to its fix and its regression tests.
- **Revision 3:** remediation of the independent re-review (verdict NOT CERTIFIED, blockers RR-01, RR-02, RR-03,
  RR-05, RR-07) on top of `74d0724`. §9 maps every blocker to its fix, its tests and its mutation check. The sections
  below describe the remediated code.

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
| `infra/config/staging-account.json` | AUT-002/003 | **Approved account manifest** (F3, F5, RR-01): account ID, name, alias, guardrail management, **owner principals of the bootstrap state** (`bootstrap_principal_arns`), allowed foreign resources. `null`/empty until the owner's reviewed commit |
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
| `…/tests/bootstrap.tftest.hcl` | AUT-002 | 29 offline test runs, 12 of them IAM-evaluated (§5) |
| `…/tests/policy_eval/` | AUT-002 | Offline IAM policy evaluator (explicit deny, identity allow, boundary allow; wildcards; conditions) |
| `…/tests/negative/*.tftest.hcl` | AUT-002 | Must-fail `prevent_destroy` tests with a mock provider, run by `infra/tests/run.sh` |
| `…/tests/fixtures/*.json` | AUT-002 | Test manifests |
| `infra/scripts/lib.sh` | AUT-003 | Guards: region, approved account, account identity, fail-closed lookups, repository |
| `infra/scripts/discover.sh` | AUT-003 | Read-only discovery (AWS, GitHub, Cloudflare, operator IP) after the identity check |
| `infra/scripts/check-plan.sh` | AUT-003 | **Plan guard**: no destroy, bounded roles, no external or broad trust, no external resource policies |
| `infra/scripts/bootstrap.sh` | AUT-003 | Plan (+ metadata + guard) / apply of a reviewed plan, first-run state migration, outputs |
| `infra/scripts/github-setup.sh` | AUT-003 | Environments (admins cannot bypass), `main` protection, `--verify`, `--verify-environments` (the RR-07 apply gate), repository variables; dry run by default |
| `infra/scripts/verify-run.sh` | AUT-003 | `plan-run`: binds plan run → artifact digest → approved plan digest → metadata and text (RR-05). `approval`: proves a run was approved for an environment (RR-07) |
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
   protected by its own key policy (which names the bucket and the owners, not the key's ARN or alias; RR-02), and the bucket
   policy admits only keys of this account and region (not the exact key ARN, which exists only after apply). The reviewer sees
   the exact JSON in the plan, the plan guard can check it, the tests evaluate it, and apply reads it back.
4. **Trust pinned to repository + GitHub environment.** Subject `repo:<owner>/<repo>:environment:<env>`, audience
   `sts.amazonaws.com`, no wildcards (tested). Pull-request, branch and fork tokens carry different subjects and are refused.
5. **Two environments added beyond the plan**: `staging-plan` (plans on PRs; **reviewer required**, because it reads state) and
   `staging-evidence` (evidence collection, main only). Every environment has `can_admins_bypass: false`; `main` is protected.
6. **The permissions boundary is self-propagating** (F1). Any role under it can create or re-bound a role only with `veda-boundary`,
   and can write IAM only on `veda-*` roles, policies and instance profiles. So no chain of created roles ends outside it. It also refuses:
   - other regions;
   - IAM users, keys and identity providers; Organizations and account changes;
   - the privileged AWS managed policies;
   - changes to the bootstrap identities (including new `veda-gh-*` names), any access to bootstrap state, and state bucket changes
     or replication into it;
   - IAM entities under a path; role creation and trust changes by any role but `veda-gh-apply`; federated sessions of any
     role but the `veda-gh-*` roles (RR-03);
   - weakening the guardrails, CloudTrail or Access Analyzer; IMDSv1;
   - cross-account sharing, grants, writes and Lambda permissions;
   - GOVERNANCE bypass.

   It deliberately does **not** block Object Lock configuration, which AUT-103 needs; each lock bucket's own policy protects it.
7. **Data reads.** The plan, deploy and evidence roles cannot read application data or seeded secrets. The plan role is further limited
   (parameters outside `/config`, objects outside state, logs, console and command output). **The apply role is not contained by these
   denies**: it administers the account and can reach data through the host role (R1).
8. **The bootstrap state is owner-only** (RR-01), enforced three times: by the boundary, by the state bucket's policy (an allow-list
   of the manifest's `bootstrap_principal_arns` and the account root, so it holds for every other principal whatever its name,
   path or boundary) and by the state key's policy (RR-02). Apply verifies the live bucket and key policies afterwards.
9. **Temporary credentials only.** `00-bootstrap` fails without a session token or with a non-`ASIA` key. The runbook tells the owner to
   delete the bootstrap secrets after use.
10. **Nothing is destroyed by automation.** The plan guard refuses any delete or replace. The guardrails and the OIDC provider are
    `prevent_destroy`, so a changed manifest or a discovery error fails the plan. Discovery lookups fail closed.
11. **Apply = the approved plan** (F4, RR-05). The plan run records the commit, clean tree, account, repository, workflow, run,
    Terraform version, the SHA-256 of the plan and of its text, and the state layout. The approver approves an apply run whose name
    carries the plan's SHA-256; the apply checks the artifact against GitHub's upload digest, the file against the approved digest,
    the metadata, and re-renders the text; Terraform itself refuses a stale plan.
14. **Environment protection is a hard prerequisite of apply** (RR-07): verified by a credential-free job before the environment
    job exists, proven by the run's approval record before any secret is read, and verified again by `bootstrap.sh` before apply.
12. **The account is approved in code** (F3), and its identity is checked live before any plan.
13. **macOS compatible:** the scripts and tests run under bash 3.2 (no `mapfile`, no associative arrays).

## 4. Security review: residual risks

| # | Risk | Severity | Treatment |
|---|---|---|---|
| R1 | `veda-gh-apply` is broad inside the account (service wildcards for the staging services). Anyone who can run an approved apply controls the staging account **within the boundary**, including reading application data through the host role. It cannot leave the boundary (F1 fixed, tested). | Medium | Accepted by design. Controls: `staging-infra` reviewer approval (admins cannot bypass), main-only branch policy on a protected `main`, one-hour sessions, the self-propagating boundary, and a reviewed, guarded plan (AUT-301). |
| R2 | IAM has no condition key for trust-policy content. | Low | RR-03 narrows it to one gated writer: the boundary lets **only `veda-gh-apply`** create a role or change a trust policy, forbids IAM paths, and makes any federated session of a non-`veda-gh-*` role useless. The apply role's trust content is checked by `check-plan.sh` on the reviewed, digest-bound plan (bootstrap now; **AUT-301 must do the same on every staging plan**). Remaining gap: a `staging-infra`-approved job running raw API calls instead of the guarded plan could still write an external trust; Access Analyzer reports it. An RCP would make it absolute; the account is not assumed to be in an Organization. |
| R3 | Terraform state will contain Cloudflare-generated secrets. The plan role reads state. | Low–Medium | Plan runs now need a `staging-plan` reviewer. State is KMS-encrypted and readable only by these roles. Parameter values outside `/config` are denied to the plan role. |
| R4 | `ReadOnlyAccess` on the plan role. | Low | Explicit denies remove parameter values, object reads outside state, logs, console/command output and data-plane reads (tested). |
| R5 | `prevent_self_review: false` lets a single owner approve their own runs. | Low | Required for a single-owner repository. Change it once a second reviewer exists. |
| R6 | The boundary's region deny exempts only listed global services. | Low | Found at the first AUT-1xx plan; fixed by extending `global_actions` in a reviewed change. |
| R7 | The account default IMDSv2 hop limit is 2. | Info | Matches the staging design (RR-09). IMDSv1 is now refused by the boundary. |
| R8 | The state bucket has no server-access logging. | Low | Checkov skip with justification. AUT-104 adds CloudTrail S3 data events for the state bucket. |
| R9 | The boundary is 5,947 of the 6,144 characters IAM allows. | Low | Asserted in the tests. A later addition that does not fit must replace a statement, not be dropped. |
| R10 | The state bucket admits any KMS key of this account and region in a PutObject header, not only the state key (the exact key ARN is not known at plan time). | Low | Default encryption uses the state key; keys of other accounts are refused; `bootstrap/*` is owner-only in the bucket policy whatever the key; the state key's own policy refuses administration and bootstrap-state use to non-owners (RR-02); the live policies are verified after every apply. |
| R14 | Bootstrap state and the state key are owned by the principals in `bootstrap_principal_arns` (plus the account root). A lost or renamed owner principal leaves only the root able to change them. | Low | Deliberate (RR-01/RR-02). Runbook §6 describes the rotation (list the new principal, apply with the old one) and root recovery. |
| R15 | The offline evaluator's model of `aws:FederatedProvider` and of the KMS/S3 request context (`kms:ViaService`, `kms:EncryptionContext:aws:s3:arn` per object, `s3:DataAccessPointArn`) follows AWS documentation; it is not IAM itself. | Low | The post-apply check reads the live policies back. First real-account check: `aws iam simulate-custom-policy` / `simulate-principal-policy` on the boundary and a `kms decrypt` of a `bootstrap/*` object by `veda-gh-apply` (must be denied). |
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
| `terraform test` (29 runs) | **29 passed, 0 failed**. Includes 12 runs that evaluate the rendered policies with `tests/policy_eval` (404 IAM/KMS/S3 requests, §8, §9), 6 owner-list precondition runs and the environment-mapping run |
| Mutation check of the evaluator | Against the original `fca56da` boundary and bucket policy, the F1, F2, F6 and F7 runs **fail** (e.g. "unbounded admin role: expected deny, got allow"). With the plan-role denies and `aws:ResourceAccount` conditions removed, the F7 and F9 runs fail. The tests detect the reviewed weaknesses, not just the new strings. |
| Negative `prevent_destroy` tests (mock provider) | Turning guardrails off and passing our OIDC provider as "existing" both **fail the plan** with "Instance cannot be destroyed", after a successful first apply |
| Mutation check of the RR fixes | Each RR fix reverted on its own in a scratch copy makes the corresponding tests fail (§9) |
| `infra/tests/run.sh` | **191 passed, 0 failed** (account identity, fail-closed lookups, plan guard, approved-plan binding, environment gate and approval proof, live state protection, GitHub settings, workflow, documentation) |
| Policy size | Every managed policy < 6,144 characters (asserted). Boundary 5,947; deploy 2,974; plan 2,738; evidence 2,243; apply-services 1,975; apply-iam 1,848; state bucket policy 1,651; state key policy 1,600 (bucket/key limits asserted too) |
| tflint 0.64.0 + AWS ruleset 0.49.0 | Pass, 0 issues |
| checkov 3.3.20 | **178 passed, 0 failed, 23 skipped** (each skip inline with its reason; the three key-policy skips now point at the key policy's own deny) |
| shellcheck 0.11.0 (scripts, tests, stubs) | Pass |
| actionlint 1.7.12 (with shellcheck) on `00-bootstrap.yml` | Pass |
| `make -C infra check` | **Exit 0** |

**Not validated (needs a real account, so it is part of the first owner-run bootstrap):**
- `terraform plan` or `apply` against AWS, and the plan guard on a real plan (its rules are tested on constructed plans shaped like the bootstrap's);
- IAM's own evaluation of the boundary (the offline evaluator implements the operators these policies use; `aws iam simulate-custom-policy` on the rendered `policy_documents` output is a useful first post-apply check);
- `account get-account-information`, the foreign-resource listing and the other discovery calls against a real account;
- OIDC token exchange end to end; state migration; the Cloudflare discovery API calls;
- running `00-bootstrap` in GitHub (it must be on the default branch), including the REST calls `verify-run.sh` makes (run,
  artifact list with its `digest`, artifact zip download, run approvals) and `--verify-environments` with the workflow token;
- the live `get-key-policy` / `get-bucket-policy` comparison against a real account (AWS may normalise more than the tested cases;
  a false mismatch fails closed).

## 6. Reviewer checklist

- [ ] `infra/config/staging-account.json` holds the right account ID, name and alias (owner commit, reviewed).
- [ ] `bootstrap_principal_arns` lists exactly the owner session's IAM role (with path) or user, and nothing else (RR-01, RR-02).
- [ ] `state.tf`: the bucket policy and the key policy deny every non-owner as described in §9; S3 Bucket Keys are off.
- [ ] `boundary.tf`: `DenyIamPaths`, `DenyTrustWritesExceptApplyRole`, `DenyFederatedSessionsOutsideGitHubRoles` (RR-03).
- [ ] `00-bootstrap.yml`: `preflight` has no environment and no secret; `bootstrap` needs it and proves its approval first (RR-07);
      apply takes `plan_sha256` and binds it through `verify-run.sh` and `bootstrap.sh` (RR-05).
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

## 9. Remediation of the independent re-review (revision 3)

Verdict of the re-review of `74d0724`: NOT CERTIFIED, blockers RR-01, RR-02, RR-03, RR-05, RR-07. Nothing was applied,
no credential was requested and no AWS or Cloudflare resource was created; all validation is offline.

| Blocker | Weakness in `74d0724` | Fix | Tests (all offline) |
|---|---|---|---|
| **RR-01** bootstrap state movement | Bucket policy denied *named* principals (`role/veda-*`): a role under a path (`role/x/veda-rogue`), a non-`veda` role or a user passed. Reads, copies, `s3:Replicate*`, restore, version rollback of `bootstrap/*` were not denied; access points bypassed the boundary's ARN match | **Owner allow-list** (`bootstrap_principal_arns` in the reviewed manifest + account root). Bucket policy: every non-owner is denied **any** S3 action on `bootstrap/*`, every bucket-configuration change, version deletion and replication into the bucket; access-point requests denied for all. Boundary: `s3:*` on `bootstrap/*` and `s3:Replicate*` denied. Plan preconditions: list non-empty, exact ARNs in the account, no `veda-*` identity (any path), current session listed. Post-apply: live bucket policy must equal the reviewed one | `rr01_bucket_policy_bootstrap_state_owner_only` (186 requests: 8 non-owner principals × 17 object actions, 3 × 13 bucket actions, access points, owner/root allowed), `rr01_boundary_alone_protects_bootstrap_state` (12), 6 precondition runs, updated `f2_*`; script: live bucket policy drift fails closed |
| **RR-02** KMS by alias | Key policy was root delegation only; protection came from `kms:ResourceAliases` in the boundary and role policies; `bootstrap.sh` found the key through the alias; S3 Bucket Keys made the encryption context bucket-wide | **Key policy enforces**: non-owners may only use (Encrypt/Decrypt/GenerateDataKey), describe, get, list; all use only via `s3.ap-south-1`, only with a per-object context in the state bucket; `bootstrap/*` context only for owners; no other account. **Bucket Keys off.** All `kms:ResourceAliases` conditions removed (asserted). Role key permissions bound by `kms:ViaService` + `staging/*` context. Scripts take the key from the bucket's default encryption; the alias must agree. Post-apply: live key policy, encryption, rotation verified | `rr02_key_policy_enforces_state_key_protection` (74 requests with the apply role's real `kms:*` and **no boundary**, no alias in any request), `rr02_plan_role_uses_the_key_for_staging_state_only` (4), `defaults` asserts; script: 9 live-protection checks (shared with RR-01) |
| **RR-03** path and trust bypass | `role/veda-*` also matches `role/veda-x/admin`; any bounded role could create or re-trust roles; guard accepted **any** environment name in a GitHub subject and ignored `path` | Boundary: `DenyIamPaths` (nothing under `veda-*/…`), `DenyTrustWritesExceptApplyRole` (`CreateRole`/`UpdateAssumeRolePolicy` only by `veda-gh-apply`), `DenyFederatedSessionsOutsideGitHubRoles`. Terraform: `github_environments` fixed. Guard: path `/` and `veda-*` names only; each `veda-gh-*` role trusted only by its protected environment, one subject, `sts:AssumeRoleWithWebIdentity` only; `NotAction` trust, privileged managed policies, users/groups/keys/providers refused; non-plan input refused | `rr03_boundary_closes_path_and_trust_bypass` (27), `rr03_rejects_other_github_environment`, updated `f1_*`; script: 25 guard checks (and 3 updated R2 checks) |
| **RR-05** plan binding | Apply trusted the plan run's own metadata checksum; the run was matched by workflow **name** and display title | Apply takes **`plan_sha256`**, shown in the run name the environment reviewer approves. `verify-run.sh plan-run` accepts only a successful plan run of `.github/workflows/00-bootstrap.yml` (path **and** workflow ID) on `main`, this repository, this commit; exactly one artifact whose zip SHA-256 equals the digest GitHub recorded at upload; plan SHA-256 equal to the approved digest; metadata naming that digest, run, commit and workflow; text SHA-256 as recorded. `bootstrap.sh` checks the approved digest against the file, the workflow, run, Terraform version, and **re-renders the plan text** and compares it with the reviewed text before applying | script: 10 `bootstrap.sh` binding checks (incl. a substituted, self-consistent plan), 16 `verify-run.sh plan-run` checks (other workflow file with the same name, other workflow ID, fork, commit, branch, failed/apply run, tampered/duplicate/expired/foreign artifact, missing digest), 13 workflow checks |
| **RR-07** environment protection | `environment: bootstrap` fails open (GitHub auto-creates a missing environment without reviewers); nothing verified protection before secrets were exposed; local apply never checked it | Workflow split: credential-free **`preflight`** job verifies every environment and `main` (and the plan binding) **before** the `bootstrap` job can request its environment; the `bootstrap` job proves an **approved review** for `bootstrap` in this run before any secret is read. `bootstrap.sh --mode apply` refuses unless `github-setup.sh --verify-environments` passes (uses only endpoints a workflow token can read) | script: 8 `--verify-environments` checks, 4 apply-refused checks (refused, and nothing applied), 5 `verify-run.sh approval` checks, and the workflow checks above (approval before the first secret; preflight has no environment or secret; the environment job needs the preflight) |

**Mutation check.** Each fix was reverted on its own in a scratch copy, after an unmutated baseline of the same copy
passed (29/0 Terraform runs, 191/0 script checks). **18 of 18 mutations are detected**:

| Mutation (fix reverted) | Detected by |
|---|---|
| RR-01 bucket policy back to the name-based `74d0724` shape | `rr01_bucket_policy_bootstrap_state_owner_only` |
| RR-01 boundary back to write-only bootstrap deny | `rr01_boundary_alone_protects_bootstrap_state` |
| RR-01 owner precondition "no `veda-*` owner" removed | `rr01_owner_list_rejects_veda_role`, `…_under_a_path` (each alone) |
| RR-02 key policy back to root delegation only | `rr02_key_policy_enforces_state_key_protection`, `rr02_plan_role_…`, `f2_apply_role_…` |
| RR-02 S3 Bucket Key back on | `defaults` |
| RR-03 `DenyIamPaths` removed | `rr03_boundary_closes_path_and_trust_bypass` |
| RR-03 `DenyTrustWritesExceptApplyRole` removed | `rr03_…`, `f1_escalated_role_stays_inside_boundary` |
| RR-03 `DenyFederatedSessionsOutsideGitHubRoles` removed | `rr03_boundary_closes_path_and_trust_bypass` |
| RR-03 `github_environments` validation removed | `rr03_rejects_other_github_environment` |
| RR-03 guard back to "any environment" (`74d0724`) | 3 environment-binding guard checks |
| RR-03 guard ignores paths | 3 path guard checks |
| RR-05 approved digest not checked (`74d0724` self-attested metadata) | substituted-plan check |
| RR-05 plan text not re-rendered | re-render check |
| RR-05 plan run matched by name, not workflow path/ID | same-name workflow and workflow-ID checks |
| RR-05 artifact digest not checked | artifact-bytes check |
| RR-07 apply not gated on environment protection (`74d0724`) | 4 apply-refused checks |
| RR-07 workflow back to one job without approval proof | 3 workflow checks |
| RR-01/RR-02 post-apply live protection check removed | 8 live-protection checks |

`terraform test` skips the runs after the first failure in a file, so the failing-run counts are lower bounds.
