# AUT-001..003 staging bootstrap: pre-bootstrap conditions closure

- **Date:** 2026-09-30
- **Certified base:** `e8157f31a9e6df23d79c2b4d79bed896a7b65cb0`, *CERTIFIED WITH PRE-BOOTSTRAP CONDITIONS*
  (conditions PB-01 to PB-11, findings N-01 to N-12)
- **This change:** closes what can be closed without AWS access and without values only the owner holds. Nothing was
  applied or deployed; no AWS or Cloudflare API was called; no credential was requested or used. GitHub environments
  were created by the owner's authorization (PB-03).
- **Owner decisions:** [`AUT-001-003-owner-decisions.md`](AUT-001-003-owner-decisions.md)
- **Status:** written by the implementer. It needs an independent review before the first real run, as the base did.

## 1. Pre-bootstrap conditions

| ID | Condition | Status | What closed it / what remains |
|---|---|---|---|
| PB-01 | Complete account manifest | **Design closed; values open (owner)** | Manifest schema v2: `region`, `organizations_mode`, `repository`, `repository_id`, `max_owner_session_seconds`, required `account_alias`, `saml_providers` allowlist. `infra/scripts/check-manifest.sh` (`--complete` before any AWS call; placeholders refused). Terraform binds `aws_region` and `github_owner/github_repo` to the manifest. Scripts and the workflow check the repository by name **and numeric ID**. **Open:** the owner commits `account_id`, `account_name`, `account_alias`, `bootstrap_principal_arns` in a reviewed PR |
| PB-02 | Account dedicated to Veda, all regions | **Control closed; evidence needs AWS** | Discovery now inventories every enabled region (EC2, non-default VPCs, Lambda, RDS, ECS, Secrets Manager, customer KMS keys) and account-wide IAM (roles, users, OIDC/SAML providers) and S3; refuses anything outside ap-south-1, anything named like Aurion or `swing-trader` (even if allowlisted), any `veda-*` resource before the bootstrap, an Organizations member account, and fails closed on any lookup error. `infra/scripts/account-inventory.sh` writes the evidence. **Open:** the owner runs it with the region-guarded session; it is also enforced automatically before any plan |
| PB-03 | GitHub environments and `main` | **Closed** | `bootstrap`, `staging-plan`, `staging-infra`, `staging`, `staging-evidence` created 2026-09-30 with `slaggala` as required reviewer (none on `staging-evidence`), `can_admins_bypass: false`, main-only branches (all but `staging-plan`). `github-setup.sh --verify` (admin read) and `--verify-environments` (workflow-token view) pass. `github-setup.sh` was fixed first: it no longer overwrites `main` protection (it would have dropped the 5 required status checks); they are unchanged |
| PB-04 | PR #2 required checks | **Fixed locally; open until pushed and merged (owner)** | Secret scan: inline `pragma: allowlist secret` on the two false positives, and the reviewed baseline updated for the commit SHAs these documents cite. Governance test: the four AUT-001..003 commits added to `KNOWN_COMMITS`. Both pass locally. **Open:** push to PR #2 (not authorized in this session), CI green, merge with a merge commit (the cited SHAs must stay in `main`'s history) |
| PB-05 | Owner decisions recorded | **Closed for the bootstrap** | OD-B1 to OD-B8. RR-A and RR-I acknowledgements remain open; they gate AUT-301 and boundary changes, not the bootstrap |
| PB-06 | Mumbai-only owner session | **Closed (code); proved live at the first run** | `infra/config/bootstrap-session-policy.json` (region deny; exemptions = the boundary's global services + the inventory reads, tested equal). `require_region_guarded_session`: a read in us-east-1 must be **denied** or the run stops. Plan guard region checks (§2) |
| PB-07 | No Cloudflare token | **Closed** | OD-B3; runbook first-run steps unset `CF_API_TOKEN` |
| PB-08 | Clean tree, ignored files included | **Closed** | `require_clean_tree` refuses tracked changes, untracked and **ignored** files (`override.tf`, `*_override.tf`, `terraform.tfvars`, …) in the plan's paths and non-git checkouts; only Terraform working files and generated inputs are tolerated |
| PB-09 | Dedicated owner role | **Closed (code); the owner creates the role** | Roles only (no users), root may not run the bootstrap (Terraform precondition and discovery), role ARN exact, `MaxSessionDuration` ≤ 3600, trust only inside the account (no identity provider, service, other account, `*`) |
| PB-10 | Live IAM simulation before apply | **Closed (code); runs live at the first run** | `infra/scripts/simulate-boundary.sh`, called after the plan guard in both modes: 7 `iam:SimulateCustomPolicy` probes of the rendered boundary (one must be allowed, six denied); any mismatch or error stops before apply |
| PB-11 | No `GH_ADMIN_TOKEN` | **Closed** | OD-B4; variables are set locally |

## 2. Findings

| ID | Status | Resolution |
|---|---|---|
| N-01 (SAML) | **Resolved** | The false claim is corrected in `boundary.tf` and the runbook. The test now models a real SAML session (no `aws:FederatedProvider`) and asserts that the boundary does *not* deny it. The control moved where it works: no Veda role can create a SAML provider, and discovery refuses any account with one. Residual: a SAML provider the owner adds later, which remains part of the AUT-301 gate (OD-B7) |
| N-02 (region) | **Resolved** | Plan guard (verified on a real `terraform show -json` of Terraform 1.16.4 / AWS provider 6.x, kept as `infra/tests/fixtures/plan-regions.json`). It refuses: any AWS provider whose region is not the constant `ap-south-1` or `var.aws_region`; providers inside modules; `aws_region` ≠ Mumbai; and any resource planned in another or unknown region, which catches **aliases, module providers and the AWS provider v6 per-resource `region` argument**. The owner session is IAM-confined (PB-06); the manifest region is bound in Terraform |
| N-03 (dedication) | **Resolved in code** | PB-02 above |
| N-04 (public artifacts) | **Resolved** | `00-bootstrap` refuses to run unless the repository is private, and checks the repository name and ID against the manifest. `discovered.json` is no longer uploaded or summarised. The first run is local (OD-B4) |
| N-05 (ignored files) | **Resolved** | PB-08 |
| N-06 (guard coverage) | Partly | `forget` and any action other than create/update/read/no-op are refused. The remaining resource types stay gated before AUT-301 |
| N-08 (S20) | Resolved | Test asserts the `refs/heads/main` check |
| N-11 (repository ID) | Partly | Scripts and workflow check the ID. The AWS OIDC trust still names the repository (RR-A, before AUT-301) |
| N-12 (owner hygiene) | **Resolved** | PB-09 |
| N-07, N-09, N-10 | N-09 = PB-04. N-07 and N-10 unchanged (Low / Info) |

## 3. Validation (offline, no credentials)

| Check | Result |
|---|---|
| `make -C infra check` (manifest schema, fmt, validate, `terraform test`, script tests, tflint, checkov, shellcheck, actionlint) | Exit 0 |
| `terraform test` | 33 passed, 0 failed (was 29: +root session, +IAM-user owner, +repository mismatch, +manifest region) |
| `infra/tests/run.sh` | 278 passed, 0 failed (was 191) |
| checkov | 178 passed, 0 failed, 23 skipped (unchanged skips) |
| Secret scan (`api/tools/secret_scan.sh`) | No new candidates |
| `api/tests/unit/test_governance_docs.py` | Passes |
| Mutation check of the new controls | 26 of 26 detected (§5) |

## 4. What still needs real AWS access

All of the following run inside the controlled first run, with the owner's region-guarded session of one hour or
less. Each one is a stop condition:
1. the region-guard proof (a us-east-1 read is denied);
2. the account identity and all-region inventory (PB-02 evidence);
3. the owner-role checks (PB-09);
4. the plan and the plan guard on the real plan;
5. the IAM simulation of the rendered boundary (PB-10);
6. the apply of the reviewed digest;
7. the live bucket and key policy comparison;
8. the CloudTrail Event History export (OD-B6).

The OIDC token exchange is first exercised at AUT-301.

## 5. Mutation check of the new controls

Each new control was reverted on its own in a scratch copy and the suites were re-run. All **26 of 26** reverts were
detected. The first pass found one weak test: TF3 survived because the IAM-user fixture also failed the "session
must be listed" precondition. The fixture now lists the session role as well, so only the roles-only rule can fail
it, and TF3 is detected.

| Group | Reverted controls (all detected) |
|---|---|
| Region (R01–R06) | plan-guard region findings; per-resource region; module providers; the region-guard proof in `bootstrap.sh`; the proof accepting any error; `ec2:RunInstances` exempted in the session policy |
| Dedicated account (A01–A09) | veda-tagged instances allowed outside Mumbai; the Aurion/swing-trader name check; the standalone check; the owner-role trust check; the owner max-session check; root/IAM-user sessions; SAML providers allowed; pre-bootstrap `veda-*` squatting; a failed regional listing ignored |
| Clean tree (C01–C02) | ignored files tolerated; non-git checkout accepted |
| GitHub (G01–G03) | repository ID not compared; public repository allowed in the workflow; `main` protection always rewritten |
| Manifest (P01–P02) | placeholders accepted; `organizations_mode` unchecked |
| Terraform (TF1–TF4) | repository not bound to the manifest; root session allowed; IAM-user owners allowed; manifest region unchecked |

The PB-10 simulation (added after this mutation pass) has its own positive and negative tests: agreement, one
wrong answer, a simulator denying everything, simulation unavailable, no boundary in the plan, and apply stopped.
