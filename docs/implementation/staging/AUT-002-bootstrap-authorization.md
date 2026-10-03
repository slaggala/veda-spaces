# AUT-002 staging bootstrap: owner waiver, authorization and final readiness

- **Date:** 2026-10-03
- **Recorded from:** the owner's instruction of 2026-10-03 (repository owner `slaggala`, Srinivasulu Laggala)
- **Repository state evaluated:** `main` after PR #14, with CI green. `make -C infra check` passes on a clean checkout
  (pinned tools, complete manifest, 33 Terraform tests, 333 script tests, checkov 178 passed / 0 failed);
  `infra/scripts/github-setup.sh --verify` passes (five protected environments; `main` protected with six required
  checks, `infra` included).
- **Not done by this record:** the bootstrap is **not run**, and no AWS or Cloudflare resource is created. Running it is
  a separate step, carried out by the operator below under §2.

## 1. RD-04: closure review, **WAIVED** by the owner

| Field | Value |
|---|---|
| Item | RD-04: the pre-bootstrap closure ([AUT-001-003-pre-bootstrap-closure.md](AUT-001-003-pre-bootstrap-closure.md)) states that it needs an independent review before the first real run |
| Decision | **WAIVED** (2026-10-03) |
| Owner's rationale | The bootstrap program has already completed the independent certification review, the owner-input review, the security review, the CI review, the PR review and the bootstrap readiness review. No additional closure review is required before the first controlled bootstrap. |
| Scope the waiver covers | The changes made after the certified base `e8157f31a9e6df23d79c2b4d79bed896a7b65cb0`: the pre-bootstrap closure and owner-input templates (PR #2), the member-account revision of OD-B2 and the manifest (PR #3), and the required-check gate in `github-setup.sh` that `bootstrap.sh` runs before apply (PR #14). Each was reviewed and merged through its pull request with CI green; none received a separate independent review |
| Compensating controls (unchanged) | The run's own stop conditions: region-guard proof, account identity and all-region inventory, owner-session checks, plan guard on the real plan, live IAM simulation of the boundary, environment-protection gate, digest-bound apply, live bucket and key policy comparison (runbook §4) |

## 2. Bootstrap authorization, **APPROVED** by the owner

| Field | Value |
|---|---|
| Decision | **APPROVED** (2026-10-03) |
| Operator | Srinivasulu Laggala |
| AWS account | `veda-staging` (813238078849), member of organization `o-q9ji0hj18c`; never the management account |
| Region | ap-south-1 |
| Execution environment | The approved local workstation |
| Method | Controlled first bootstrap: runbook [§3 Option A](../../operations/staging-bootstrap.md) (local); the `00-bootstrap` workflow is not used (public repository, OD-B4) |
| Security requirements | `bootstrap-owner` role only · MFA required · a temporary access key for `bootstrap-operator`, created on the run day only and deleted after completion · no root credentials · no permanent credentials |
| Run procedure | [P0-release-readiness-report.md §7.1](../P0-release-readiness-report.md), steps 1–8: offline checks; MFA-backed, region-guarded one-hour session; inventory evidence; plan; review of the plan text and digest; digest-bound apply; post-apply checks and repository variables; evidence; deletion of the access key |
| Stop rule | Any stop condition of the runbook ends the run; nothing is forced or retried around a refusal. A refused plan is investigated before a new plan is made |
| Not authorized by this record | Any staging stack after the bootstrap (AUT-101 onward, gated by OD-B7 for `veda-gh-apply`), any Cloudflare change, any change in the management account |

## 3. MFA status

| Check | Status | Evidence |
|---|---|---|
| `bootstrap-operator` has an MFA device | **Enabled**, as the owner attests (2026-10-03) | Owner statement. The command-line read-back (`aws iam list-mfa-devices --user-name bootstrap-operator`) was not provided. It is not needed separately: the run cannot start without it (next row) |
| `bootstrap-owner` can be assumed only with MFA | Enforced by the role's trust policy (`aws:MultiFactorAuthPresent`, MFA age under one hour) | CloudShell validation, 12/12 checks (2026-10-02, PR #3) |
| The run's session is MFA-backed | Proven at the run: `assume-role` with `--serial-number` and `--token-code` is refused without the device, so the run fails closed | Runbook §2; the evidence of the run (CloudTrail `AssumeRole` with MFA, OD-B6) |

## 4. Final readiness

| Prerequisite | Status |
|---|---|
| Manifest complete (PB-01) | Met: PR #3; `check-manifest.sh --complete` passes |
| Dedicated member account, alias, owner role | Met: CloudShell 12/12; re-checked automatically at the run |
| GitHub environments and `main` protection with required checks (PB-03, RD-02) | Met: `--verify` passes |
| CI green on `main` | Met |
| Owner decisions OD-B1…OD-B8 | Met |
| Operator workstation and pinned tools; `make -C infra check` on a clean `main` | Met (2026-10-03) |
| `bootstrap-operator` MFA (RD-03) | Met (owner attestation; enforced at the run) |
| Closure review (RD-04) | Waived by the owner (§1) |
| Run authorization | Approved by the owner (§2) |
| Temporary access key | Created on the run day by the operator, deleted after the run (by design not before) |
| No Cloudflare token, no `GH_ADMIN_TOKEN`, no secrets in the repository | Met: 0 secrets |

**Verdict: READY FOR CONTROLLED BOOTSTRAP.** The run itself remains a separate, operator-executed step under §2.
Its stop conditions are the final gate.
