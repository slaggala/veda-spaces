# Review package: AUT-301 (staging plan and apply workflows)

- **For:** independent review, the same process as AUT-001…003.
- **Scope:** the infrastructure workflows that every staging stack (AUT-101 onward) goes through, and the empty
  `staging-core` root they act on. Nothing is applied and no AWS resource is created by this change. The apply workflow
  is **disabled** (fails closed) until owner decision OD-B7 and gate N-04-S are recorded.
- **Base:** `main` after PR #18 (the bootstrap, AUT-002, applied on 2026-10-03, evidence in
  [`docs/release-evidence/AUT-002/`](../../release-evidence/AUT-002/README.md); its trust policies re-applied on
  2026-10-04 with GitHub's immutable OIDC subject,
  [AUT-002-trust-subject-reapply.md](AUT-002-trust-subject-reapply.md)).
- **Runbook:** [`staging-infra-workflows.md`](../../operations/staging-infra-workflows.md).

## 1. Files

| File | What it is |
|---|---|
| `.github/workflows/10-infra-plan.yml` | OIDC plan of `staging-core` in `staging-plan`; plan guard; plan text kept off the log; artifact only when N-04-S allows |
| `.github/workflows/11-infra-apply.yml` | Credential-free preflight (gates, inputs, repository, `main`, environments, plan binding) → apply job in `staging-infra` (gates again, approval proof, plan binding again, OIDC `veda-gh-apply`, digest-bound apply) |
| `infra/scripts/stack.sh` | `plan` / `apply` / `gate` for a staging stack |
| `infra/scripts/oidc-session.sh` | OIDC token → `veda-gh-<role>` session, verified and masked, exported via `$GITHUB_ENV` |
| `infra/scripts/verify-run.sh` | New `--stack` mode: binds a `10-infra-plan` run, its artifact and the approved digest to an `11-infra-apply` run (bootstrap mode unchanged) |
| `infra/scripts/install-tools.sh` | New `--only` option: the workflows install only the pinned, SHA-256-verified Terraform |
| `infra/config/apply-gate.json` | The apply gate: OD-B7 and N-04-S, both `UNDECIDED` |
| `infra/terraform/envs/staging-core/` | Empty root: partial S3 backend, provider pinned to the manifest account and Mumbai, default tags, lock file, offline tests |
| `infra/Makefile` | `staging-core` added to the checked roots; offline checks use their own Terraform data directory (§6) |
| `infra/tests/run.sh`, `infra/tests/stubs/terraform` | 94 new checks (§5); the Terraform stub accepts `-chdir=` and prints plan output like the real `terraform plan` |
| `docs/operations/staging-infra-workflows.md`, `infra/README.md`, `envs/staging-core/README.md` | Runbook and status |

## 2. Design decisions for review

| # | Decision | Why |
|---|---|---|
| D1 | Two workflow files (plan, apply), not one with a mode input | The plan runs on pull requests (review). The apply exists only as a manual `main` run whose name carries the approved digest. Each role's trust names its own environment |
| D2 | Reuse the bootstrap's controls instead of new ones: `check-plan.sh`, `verify-run.sh` (digest binding, RR-05; approval proof, RR-07), `github-setup.sh --verify-environments`, the credential-free preflight | They are already reviewed, mutation-tested and in CI |
| D3 | A committed apply gate (`apply-gate.json`), checked in three places (preflight, apply job, `stack.sh`) | OD-B7 says no workflow may assume `veda-gh-apply` until the gap is closed or accepted. A file changed only by reviewed PR makes the decision auditable; refusal in the preflight means the apply job never requests the environment or a token |
| D4 | Plan text never in the job log; artifact only from a private repository or once N-04-S is accepted | The repository is public: job logs and artifacts are world-readable. This is the bootstrap's N-04 decision extended to staging plans. Consequence: until N-04-S is decided, no plan can be reviewed in GitHub, so no apply can run |
| D5 | OIDC exchange in a 60-line script (`curl` to the job's token endpoint, `aws sts assume-role-with-web-identity`) instead of a third-party action | No new supply-chain dependency; testable offline; the session is verified (`get-caller-identity` = `veda-gh-<role>/gh-<run>-<attempt>-<role>`) and masked |
| D6 | `stack.sh` proves Mumbai confinement on every run (us-east-1 read must be denied) | Detects a role that lost `veda-boundary` before Terraform runs |
| D7 | Backend values from the manifest (bucket name) and the repository variables (state key ARN), cross-checked | A wrong or tampered repository variable is refused, not used |
| D8 | Only `workflow_dispatch` plan runs on `main` can be applied | Pull-request plans come from unmerged code; push plans can race. The reviewer approves a deliberate plan run |

## 3. Threats and controls

| Threat | Control | Where tested |
|---|---|---|
| Apply before OD-B7 | Gate refuses in the preflight, the apply job and `stack.sh`; empty, malformed or reshaped gate files refuse | §5 gate checks |
| Applying a plan nobody approved, or another one | Digest in the run name (reviewer approves it); artifact bytes = GitHub's upload digest; plan file = approved digest; metadata = run, commit, workflow, stack, account, Terraform; text re-rendered = reviewed text | `verify-run.sh --stack`, `stack.sh apply` checks |
| Plan made on a branch, from a fork, by another workflow | Only successful `workflow_dispatch` runs of `10-infra-plan` on `main` from this repository | `verify-run.sh --stack` checks |
| Apply from anywhere but `11-infra-apply` on `main` | `GITHUB_WORKFLOW_REF` check in `stack.sh`; preflight `GITHUB_REF` and workflow ref checks | `stack.sh apply` check |
| Wrong role or account | Trust policies (bootstrap); `oidc-session.sh` and `stack.sh` verify the session ARN and account; provider `allowed_account_ids` | OIDC and session checks |
| A role without `veda-boundary` | us-east-1 probe must be denied | Session check |
| Destructive or unsafe plan | `check-plan.sh` on every plan, and again before apply | Plan guard check |
| Credentials leaking in logs | Secret and session token masked; the OIDC token is never printed; no stored secrets; `persist-credentials: false` | OIDC checks; workflow contract |
| Infrastructure detail in public logs | Plan output to file only; artifact gated by N-04-S | Plan-log check |
| Unprotected environment | `--verify-environments` (reviewers, no admin bypass, main-only, `main` protected with every required check) before any session; approval proof | Workflow contract (order checks) |
| Supply chain | Actions pinned to commits; Terraform pinned by SHA-256 | Workflow contract; RD-02 |

## 4. Residual risks

| # | Risk | Level | Handling |
|---|---|---|---|
| R1 | `veda-gh-apply` administers the account (bootstrap R1). Once enabled, a reviewed plan can do anything the boundary allows | High (by design) | OD-B7 (trust-writing gap) with RR-C (SCP) before enabling; reviewer approval of each digest |
| R2 | The `staging-plan` reviewer approves pull-request plans of unmerged code; `ReadOnlyAccess` minus the data denies is readable by that code | Medium | Reviewer required (F9); plan role denied data reads; only `main` dispatch plans are applyable |
| R3 | Plan text unavailable for review in a public repository (N-04-S undecided) | Low (blocks applies) | Owner decision: make the repository private, or accept publishing staging plan text |
| R4 | ~~Repository-name OIDC trust (RR-A)~~ | Closed | Immutable GitHub subject ID trust: every role trusts only `repo:slaggala@37840263/veda-spaces@1392733148:environment:<env>` (owner and repository numeric IDs; PR #18, re-applied 2026-10-04). A renamed, transferred or re-registered repository cannot match |
| R5 | Single owner approves their own runs (OD-B5) | Accepted | Revisit before a second collaborator |

## 5. Tests

`infra/tests/run.sh` has **94 new checks**, giving **440 passed** and 0 failed (346 on `main`, which includes the 13 checks
of the immutable-subject fix, PR #18):
- **Workflow contract:**
  - triggers;
  - environments;
  - `id-token` only in the two OIDC jobs, never at workflow level;
  - fork guard;
  - the approval proven before any AWS session (order checks);
  - gates first in the preflight, and again in the apply job before any session;
  - the approved plan fetched before any session;
  - the digest and run in the apply command and in the run name;
  - manual trigger only for apply;
  - no stored secrets; actions pinned to commits; every checkout without credentials.
- **Apply gate:**
  - the committed gate refuses (OD-B7, N-04-S); decided gates with records pass;
  - refusals: no record; a record that doesn't exist; a status the gate doesn't allow; a missing gate; an unknown gate; an empty, malformed or array-shaped file; a missing file.
- **`stack.sh plan`:**
  - the empty root gives "No changes", prints the digest to approve, and creates nothing, after the plan guard;
  - neither the plan text nor Terraform's own plan output reaches the job log; the output is kept in the plan log file;
  - the exact backend configuration; a saved plan with a lock timeout;
  - metadata bound to stack, commit, account, state key, digest and change counts;
  - refusals: an apply session; a session not confined to Mumbai; another account; another state bucket; another account's state key; an unknown stack; a destroy (plan guard).
- **`stack.sh apply`:**
  - the approved plan is applied, exactly that file;
  - the committed gate refuses before Terraform runs;
  - refusals:
    - not run by `11-infra-apply` on `main`;
    - another digest; a plan made locally; another run, commit or stack;
    - the reviewed text replaced; another Terraform version; a different re-rendered text;
    - a plan session.
- **`oidc-session.sh`:**
  - exchange for the approved account's role, with audience `sts.amazonaws.com`;
  - secret and token masked and exported; the OIDC token never printed;
  - refusals: no `id-token` permission; a repository variable naming another role; long-term keys; a session of another role; an unknown role.
- **`verify-run.sh --stack`:** a core plan bound; refusals for a `00-bootstrap` plan run, the wrong apply workflow, a pull-request plan run, another branch, and the bootstrap mode on a core run.
- **Tooling:** `--only` refuses unknown tools; `staging-core` in the checked roots; committed lock file; partial backend; provider pinned to the manifest account.

`terraform test` for `staging-core`: 2 passed (the empty root plans; another region is refused). The bootstrap's 33
still pass.

**Mutation check:** each control below was removed on its own, in a full copy of the repository tree, and the suite
re-run. All 8 are detected.

| # | Control removed | Failing checks |
|---|---|---|
| M1 | Gate refuses an empty or reshaped file | 3 |
| M2 | `stack.sh apply` checks the gate | 1 |
| M3 | Terraform plan output kept off the log | 2 (after the fix in §6.3) |
| M4 | OIDC secret masked | 1 |
| M5 | Apply accepts only plans of `10-infra-plan` on `main` | 1 |
| M6 | `verify-run.sh --stack` requires the apply run to be `11-infra-apply` | 2 |
| M7 | Preflight checks the gate | 1 |
| M8 | Apply requires a `veda-gh-apply` session | 4 |

## 6. Fixes made while testing

1. **Gate fail-open, caught by a test.** A malformed test fixture produced an empty gate file, and the first version of
   `stack.sh gate` **accepted** it: jq prints nothing for empty input, so "no problems" was read as "decided". The gate
   now refuses anything that is not a JSON object with a `gates` object, and four tests (empty, malformed, array,
   missing) cover it.
2. **Offline checks after a real run.** After the bootstrap run, the bootstrap root's local `.terraform` points at the
   S3 backend, and `make -C infra check` stopped working offline on the operator's workstation. The offline `validate`
   and `test` now use their own data directory under the gitignored `infra/generated/tf-check/`. It sits outside the
   bootstrap root, where the clean-tree rule would refuse it.
3. **A test that could not fail, caught by the mutation check.** Removing the plan-log redirect (M3) went undetected:
   the Terraform stub's `plan` printed nothing, so a leak could not show. The stub now prints a marker as the real
   `terraform plan` does, and two checks prove the output stays off the job log and is kept in the plan log file.

## 7. Validation (local, macOS arm64, pinned tools)

| Check | Result |
|---|---|
| `make -C infra check` | Exit 0: tool versions pinned; manifest complete; fmt; validate (bootstrap, staging-core); `terraform test` 33 + 2 passed; script tests **440 passed, 0 failed**; tflint clean; checkov 178/0/23 (bootstrap) and 1/0/0 (staging-core); shellcheck clean; actionlint clean on every workflow |
| `api/tests/unit/test_governance_docs.py` | Passes |
| Secret scan | No new candidates (the one fake STS secret in the tests carries an allowlist pragma) |
| CI | See the pull request |

## 8. First proof: `10-infra-plan` against the empty `staging-core`

**Result: passed** on 2026-10-04, within the scope below. Run
[37173741130](https://github.com/slaggala/veda-spaces/actions/runs/37173741130) (the head of PR #17 at the time; the run records the commit), job
`plan (staging-core)`: success.

| Check | Log line (UTC) |
|---|---|
| Approval | 16:56:36 run 37173741130 was approved for environment 'staging-plan' by: slaggala |
| GitHub settings | 16:56:39 GitHub settings for slaggala/veda-spaces match the bootstrap rules |
| OIDC session | 16:56:42 `arn:aws:sts::813238078849:assumed-role/veda-gh-plan/gh-37173741130-1-plan` (1 h) |
| Account and region | 16:56:45 session confined to ap-south-1 by IAM (us-east-1 denied); session in account 813238078849 |
| Backend | 16:56:55 `s3://veda-tfstate-813238078849/staging/core.tfstate` (state key, native lock) |
| Plan guard | 16:57:04 no destroy, everything in ap-south-1, every role bounded at path /, GitHub trust only from each role's protected environment, no trust or resource policy outside account 813238078849 |
| Plan summary | 16:57:04 No changes. Your infrastructure matches the configuration. |
| Plan digest | `e9af4976b7ccfc4ce23fb37a27fe3269dbc9047af082f66e5d8b5fba994acd2e` |
| Plan mode | 16:57:04 nothing was created |
| Publication | Not published: the repository is public and N-04-S is UNDECIDED |

**Scope of the proof.**

| Control | Proven live by this run |
|---|---|
| OIDC session (`veda-gh-plan` from `staging-plan`, immutable GitHub subject ID trust) | **Yes** |
| Region confinement (us-east-1 denied to the session) | **Yes** |
| Plan guards (`check-plan.sh` on the plan; "No changes"; nothing created) | **Yes** |
| Approval proof and environment verification before the session | **Yes** |
| Artifact digest binding (plan run → uploaded artifact → approved digest → `11-infra-apply`, RR-05) | **No** |

The proof was a `pull_request` run, and no artifact was uploaded (N-04-S is undecided and the repository is public).
Therefore **artifact digest binding has not yet been proven live**. It is covered only by the offline tests (§5,
`verify-run.sh --stack`; mutations M5 and M6). It can first be proven by a `10-infra-plan` run on `main` that uploads
its artifact, which needs N-04-S decided, and then only by an `11-infra-apply` run, which needs OD-B7 decided.

The earlier run (37149305740, same day) was refused by AWS (`AccessDenied` on `AssumeRoleWithWebIdentity`): the roles
did not yet use immutable GitHub subject ID trust, while the repository issues the immutable subject. That was fixed by PR #18 and the owner's
re-apply of the four trust policies (0 to add, 4 to change, 0 to destroy; `assume_role_policy` subject only).
Nothing was planned or created by the refused run.

## 9. Owner decisions this review prepares

| Decision | Options | Gate value |
|---|---|---|
| **OD-B7**, the trust-writing gap of `veda-gh-apply` | (a) close it with an SCP from management account `749251636763` that denies `iam:CreateRole` and `iam:UpdateAssumeRolePolicy` to every principal but `veda-gh-apply`, and limits it as the plan guard does (RR-C); (b) accept it, with per-digest review as the control | `CLOSED` or `ACCEPTED`, with the decision record |
| ~~RR-A~~ | **Closed:** immutable GitHub subject ID trust (PR #18; the owner re-applied the four trust policies on 2026-10-04) | None; no longer part of OD-B7 |
| **N-04-S**, staging plan text in a public repository | Make the repository private, or accept publishing staging plan text (no secrets are Terraform-managed, AUT-107/302) | `PRIVATE_REPOSITORY` or `ACCEPTED`, with the decision record |
