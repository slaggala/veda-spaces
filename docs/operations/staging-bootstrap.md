# Staging bootstrap runbook (AUT-002, AUT-003)

This runbook covers the one-time bootstrap of the **dedicated Veda staging AWS account** in **ap-south-1**.
It is the only step that uses owner credentials. After it, every workflow runs through GitHub OIDC.
It has no dependency on Aurion or any other system, and does not deploy the application or enable public intake.

- **Status:** written and tested offline; remediated after the independent review (F1–F10, see the review package §8)
  and the final-certification re-review (RR-01, RR-02, RR-03, RR-05, RR-07, review package §9); pre-bootstrap
  conditions PB-01 to PB-11 addressed in
  [`AUT-001-003-pre-bootstrap-closure.md`](../implementation/staging/AUT-001-003-pre-bootstrap-closure.md).
  **Applied to `veda-staging` (813238078849) on 2026-10-03** by the local procedure (Option A), under the owner
  authorization; evidence: [`docs/release-evidence/AUT-002/`](../release-evidence/AUT-002/README.md).
- **Owner decisions (2026-09-30, OD-B2 revised 2026-10-02):** ap-south-1 (Mumbai) only; a **member account**
  (`veda-staging`, `813238078849`) of organization `o-q9ji0hj18c`, never its management account; no
  Cloudflare write token for the bootstrap; **controlled local first run** (§3, Option A). See
  [`AUT-001-003-owner-decisions.md`](../implementation/staging/AUT-001-003-owner-decisions.md).
- **Code:** [`infra/terraform/bootstrap`](../../infra/terraform/bootstrap), [`infra/scripts`](../../infra/scripts),
  [`.github/workflows/00-bootstrap.yml`](../../.github/workflows/00-bootstrap.yml).

## 1. What the bootstrap creates

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `veda-tfstate-<account>` | Terraform state for every stack: versioned, SSE-KMS, TLS-only, public access blocked, `prevent_destroy` |
| KMS key + alias | `alias/veda-tfstate` | State encryption; yearly rotation; `prevent_destroy` |
| IAM OIDC provider | `token.actions.githubusercontent.com` | GitHub Actions federation (reused if the account already has one) |
| IAM policy | `veda-boundary` | Self-propagating permissions boundary on every Veda role (§7) |
| IAM roles | `veda-gh-plan`, `veda-gh-apply`, `veda-gh-deploy`, `veda-gh-evidence` | Workflow roles, one per GitHub environment, one-hour sessions |
| Account guardrails | — | S3 public-access block for the account, EBS encryption by default, EBS snapshot and AMI public sharing blocked, IMDSv2 required by default (hop limit 2), IAM Access Analyzer. Managed only when the manifest says so; `prevent_destroy` |

Nothing else is created: no VPC, no instance, no bucket other than the state bucket, no Cloudflare resource.

## 2. What the owner provides

**First, in a reviewed pull request:** record the dedicated account in
[`infra/config/staging-account.json`](../../infra/config/staging-account.json). Every script, the workflow and the
Terraform variable validation refuse to run while `account_id` is `null`, or for any other account (F3), and
`infra/scripts/check-manifest.sh --complete` must pass (PB-01). The fixed fields (`schema_version`, `region` =
`ap-south-1`, `organizations_mode` = `member` with `organization_id` and `management_account_id`, `repository` =
`slaggala/veda-spaces`, `repository_id`, `repository_owner_id`,
`max_owner_session_seconds` = 3600) record the owner decisions and are checked on every run.

| Field | Value |
|---|---|
| `account_id` | The 12-digit ID of the dedicated staging account |
| `account_name` | Its name exactly as `aws account get-account-information` returns it (for example `veda-staging`) |
| `account_alias` | Its IAM account alias (**required**: create one with `aws iam create-account-alias` if the account has none). It must not contain `prod` or `aurion` |
| `manage_account_guardrails` | `true` unless the account already manages the guardrails (§6). Changing it later never removes them |
| `bootstrap_principal_arns` | The exact IAM **role** ARN (with its path) of the dedicated owner role that runs the bootstrap, for example `arn:aws:iam::<ACCOUNT_ID>:role/bootstrap-owner` (never a `veda-*` name). These principals, and the account root, are the **only** ones that can read or write bootstrap state, change the state bucket or administer the state key (RR-01, RR-02). No wildcards, no IAM users, no `veda-*` identity. The role must allow sessions of at most one hour (`MaxSessionDuration` ≤ 3600) and be trusted only by principals of this account (no identity provider, service or other account; PB-09). The root user may not run the bootstrap |
| `allowed_foreign_resources` | Pre-existing IAM roles, users, SAML providers, buckets, instances or Lambda functions that are *not* Veda's but may stay. For the new member account: the owner role and `OrganizationAccountAccessRole` in `iam_roles` (the owner role is required by `check-manifest.sh --complete`) and the owner IAM user in `iam_users`, nothing else. Anything named like Aurion or `swing-trader` is refused even if listed. Exact owner inputs, the owner-role specification and templates: [`bootstrap-owner-inputs.md`](bootstrap-owner-inputs.md) |

Discovery then refuses the run unless (N-03): the live account name and alias match; neither looks like production
or Aurion (`prod`, `aurion`); the account is a member of exactly the approved organization and is not its
management account (owner decision: member account); the
session is an assumed owner role and every owner role passes the checks above; and an inventory of **every enabled
region** finds nothing but the allowlist and, once the bootstrap has run, Veda's own resources in ap-south-1. The
inventory covers IAM roles, users and identity providers (only the GitHub OIDC provider; **no SAML provider**, N-01),
S3 buckets, and per region EC2 instances, non-default VPCs, Lambda functions, RDS instances, ECS clusters, Secrets
Manager secrets and customer-managed KMS keys. Before the bootstrap has run, no `veda-*` resource may exist at all.

Then, at run time:

| # | Item | Used for |
|---|---|---|
| 1 | The same account ID | `EXPECTED_ACCOUNT_ID`: checked against the manifest and the session |
| 2 | A **temporary**, **region-guarded** session of the owner role (access key `ASIA…`, secret key, **session token**), at most one hour | Bootstrap only; it expires by itself |
| 3 | **No Cloudflare token for the first run** (owner decision; PB-07). Later, a read-only token (Zone:Read, DNS:Read on `vedaspaces.com` only) may be used for discovery; a write token is never used by the bootstrap | Cloudflare discovery is deferred to AUT-201 |
| 4 | **No `GH_ADMIN_TOKEN` for the first run** (PB-11): set repository variables locally with `make -C infra github-variables APPLY=1` | — |

**The session must be confined to ap-south-1 by IAM (PB-06).** The owner role is not under `veda-boundary`, so the
session carries the region-deny session policy
[`infra/config/bootstrap-session-policy.json`](../../infra/config/bootstrap-session-policy.json). It denies every
action outside ap-south-1 except the global services the boundary exempts and the read-only calls of the all-region
inventory. `bootstrap.sh` and `discover.sh` prove it before anything else: a harmless read in us-east-1 must be
**denied**, otherwise they stop.

```sh
aws sts assume-role --role-arn arn:aws:iam::<ACCOUNT_ID>:role/<owner role> \
  --role-session-name veda-bootstrap-$(date -u +%Y%m%d) --duration-seconds 3600 \
  --policy file://infra/config/bootstrap-session-policy.json
```

## 3. Run it

### Option A: locally (the approved procedure for the first run)

Prerequisites: `aws` v2, `jq`, `curl`, `git`, `gh` (authenticated as a repository admin), Python 3.13, and the pinned
check tools (Terraform 1.16.4, tflint, shellcheck, actionlint, checkov): `make -C infra tools` installs them, SHA-256
verified, into `infra/.tools`.
Run from a **clean checkout** of `main` that includes the manifest commit. The plan refuses a checkout with
uncommitted, untracked or *ignored* files the plan could read (`override.tf`, `*_override.tf`, `terraform.tfvars`;
N-05, PB-08). Before the first run, record the all-region inventory evidence with the same session (PB-02):
`infra/scripts/account-inventory.sh --expected-account-id <ACCOUNT_ID>` writes
`infra/generated/account-inventory.json` and fails unless the account is dedicated to Veda.

```sh
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… AWS_SESSION_TOKEN=… AWS_REGION=ap-south-1   # region-guarded
unset CF_API_TOKEN                                               # no Cloudflare token (owner decision)

infra/scripts/check-manifest.sh --complete                       # PB-01
make -C infra check                                              # offline checks
make -C infra github-environments REVIEWERS=<login>              # dry run: environments + main protection
make -C infra github-environments REVIEWERS=<login> APPLY=1
make -C infra github-verify                                      # read back; fails on any drift
make -C infra bootstrap-plan  EXPECTED_ACCOUNT_ID=<ACCOUNT_ID>    # read-only; review infra/generated/bootstrap-plan.txt
                                                                 # and note the "plan sha256" it prints
make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=<ACCOUNT_ID> PLAN_FILE=generated/bootstrap.tfplan \
  PLAN_SHA256=<the reviewed digest>                              # applies that approved plan; type the account ID
make -C infra github-variables                                   # dry run, then again with APPLY=1
```

`bootstrap-apply` without `PLAN_FILE` plans, shows the plan and its SHA-256, and asks for the account ID before
applying the plan it just showed. It never applies anything that was not shown. With `PLAN_FILE`, it applies only
the file whose SHA-256 is `PLAN_SHA256` and whose text, rendered again, is the text you reviewed (RR-05).

Either way, **apply refuses to start unless the GitHub environments are protected** (RR-07): `github-setup.sh
--verify-environments` must pass (every environment present with required reviewers where required, no admin
bypass, the main-only branch policy, and `main` protected). Run the `github-environments` step first.

### Option B: the `00-bootstrap` workflow (not for the first run; private repository only)

A `workflow_dispatch` workflow can only be started once it exists on the default branch. It runs **only from a
private repository** (N-04): the plan artifact and the job summary are readable by anyone who can read the
repository. While the repository is public, the workflow refuses to start and Option A is the only way. It also
checks the repository name and numeric ID against the manifest (PB-01).

1. Create and verify the GitHub environments and the `main` protection:
   `make -C infra github-environments REVIEWERS=<login> APPLY=1 && make -C infra github-verify`.
2. Store the temporary session in the `bootstrap` environment:
   ```sh
   gh secret set BOOTSTRAP_AWS_ACCESS_KEY_ID     --env bootstrap
   gh secret set BOOTSTRAP_AWS_SECRET_ACCESS_KEY --env bootstrap
   gh secret set BOOTSTRAP_AWS_SESSION_TOKEN     --env bootstrap
   gh secret set CF_READ_TOKEN                   --env bootstrap   # optional, read-only (never a write token)
   gh secret set GH_ADMIN_TOKEN                  --env bootstrap   # optional, Variables: write only
   ```
3. Run it: Actions → **00-bootstrap** → mode `plan`. Read the job summary and the `bootstrap-plan-<run id>`
   artifact (`bootstrap-plan.txt`). Note the run ID and the **plan sha256** in the summary.
4. Run it again with mode `apply`, `plan_run_id` = that run ID and `plan_sha256` = that digest. The run's name shows
   both, so the `bootstrap` environment reviewer approves that exact digest. It applies **that plan file** only
   (RR-05), after checking that:
   - the plan run is a successful `workflow_dispatch` plan run of `.github/workflows/00-bootstrap.yml` (path and
     workflow ID, not the name) on `main`, in this repository, for the same commit;
   - the artifact's bytes match the SHA-256 GitHub recorded when the plan run uploaded it;
   - the plan file's SHA-256 is the approved `plan_sha256`, and its metadata names that digest, run and workflow;
   - the plan text, rendered again from the file, is byte-identical to the reviewed `bootstrap-plan.txt`.
   If anything changed in between (a new commit, or state), plan again.
5. **Delete the bootstrap secrets** afterwards (they have expired anyway):
   `gh secret delete BOOTSTRAP_AWS_ACCESS_KEY_ID --env bootstrap` (and the other two).

The workflow refuses to run without a session token, with a key that is not an `ASIA…` temporary key, from any
branch but `main`, while `main` is unprotected, or for an account other than the manifest's.

**It fails closed on environment protection (RR-07).** A first `preflight` job, with no environment and no secret,
verifies every environment and `main` before the `bootstrap` job may even request its environment, so a missing
environment is never auto-created without reviewers. The `bootstrap` job then proves, through the run's approval
record, that a reviewer approved it for `bootstrap` before it reads any secret.

## 4. What the run does

1. **Guards:** region must be `ap-south-1`; the account must be the manifest's and `aws sts get-caller-identity`
   must return it; the manifest must be complete; the session must be **denied** a read in us-east-1 (PB-06). The
   Terraform provider also pins `allowed_account_ids`, and the Terraform variable validation checks the manifest
   (account, region, repository) too.
2. **Account identity** (fails closed): account name and alias match the manifest; neither looks like production
   or Aurion; a member (not the management) account of the approved organization; the session is an owner role and every owner role is safe (§2); nothing in any
   enabled region but the allowlist and Veda's own resources in ap-south-1; nothing named like Aurion or
   `swing-trader` (N-03). The repository is the manifest's by name and numeric ID (PB-01).
3. **Discovery** (`discover.sh`, read-only), written to `infra/generated/discovered.json`:
   - account and caller;
   - availability zones, and whether t4g.medium is offered in ap-south-1a;
   - the Amazon Linux 2023 arm64 AMI;
   - SES sandbox status;
   - whether an OIDC provider already exists, and whether the bootstrap created it (a failed lookup stops the run);
   - whether the state bucket exists in this account (a 403, e.g. the name taken elsewhere, stops the run), the key, and the roles;
   - current account guardrails;
   - GitHub repository;
   - Cloudflare account and zone, planned-name collisions (every page of records) and live-site records;
   - the operator's public IP.
4. **Plan:** `terraform plan` to `infra/generated/bootstrap.tfplan`, its text in `bootstrap-plan.txt`, and
   `bootstrap-plan.meta.json` (commit, clean tree, account, repository, workflow, run, Terraform version, SHA-256 of
   the plan and of its text, whether state existed). The plan fails unless `bootstrap_principal_arns` is set, exact,
   free of `veda-*` identities and includes the session running it. When the state bucket exists, its key is the
   one the bucket's default encryption names; the alias must agree with it (RR-02).
5. **Plan guard** (`check-plan.sh`, on every plan and again before apply). It refuses:
   - any delete or replace;
   - any IAM role without `veda-boundary`, or with a trust policy unknown at plan time;
   - any IAM role, policy or instance profile under a path, or not named `veda-*` (RR-03);
   - any trust in another account, in everyone, or in an identity provider other than GitHub, or with
     `NotAction`/`NotPrincipal`;
   - GitHub trust whose subject is not GitHub's immutable form, `repo:<owner>@<owner id>/<repo>@<repo id>:environment:<env>`,
     with the IDs from the manifest (RR-A; the repository issues it, `use_immutable_subject`, checked by
     `github-setup.sh --verify` and `--verify-environments`);
   - GitHub trust on any role but the four `veda-gh-*` roles, or from any environment but the role's own protected
     one (`plan`→`staging-plan`, `apply`→`staging-infra`, `deploy`→`staging`, `evidence`→`staging-evidence`), with
     any action but `sts:AssumeRoleWithWebIdentity` (RR-03);
   - privileged AWS managed policies, IAM users, groups, keys, SAML or other OIDC providers, account settings;
   - an input that is not a Terraform plan;
   - anything outside ap-south-1 (PB-06): an AWS provider whose region is not the constant `ap-south-1` or the root
     variable `aws_region`, any provider configured inside a module, `aws_region` set to another region, or any
     resource whose planned region (AWS provider v6 records it per resource, whichever alias, module or per-resource
     `region` argument set it) is another region or unknown; a `forget` (`removed` block) is refused like a delete;
   - any resource policy, Lambda permission, function URL, KMS grant or AMI/snapshot permission that opens something
     to another account or the public.
6. **Apply** (apply mode only). This applies the reviewed plan file and nothing else; Terraform refuses it if the
   state changed since. On the first run it then:
   - migrates the local state to `s3://veda-tfstate-<account>/bootstrap/terraform.tfstate`;
   - checks that the object exists (in this account);
   - deletes the local copy.

   Then, on every apply, it reads the live state bucket policy, default encryption, key policy and key rotation back
   and stops unless they are exactly the reviewed ones (RR-01, RR-02). No outputs are written otherwise.
7. **Outputs:** `infra/generated/bootstrap-outputs.json` lists the role ARNs, the state bucket and key, and the backend settings.

Re-running is safe. When the state bucket exists, the script uses the remote state and the plan shows only the differences.

## 5. Checks after apply

All of these commands are read-only:

```sh
aws s3api get-bucket-versioning        --bucket veda-tfstate-<ACCOUNT_ID>        # Enabled
aws s3api get-bucket-encryption        --bucket veda-tfstate-<ACCOUNT_ID>        # aws:kms, the state key, BucketKeyEnabled false
aws kms get-key-policy --key-id <state key ARN> --policy-name default            # = terraform output policy_documents.state_key
aws s3api get-public-access-block      --bucket veda-tfstate-<ACCOUNT_ID>        # all true
aws s3api head-object --bucket veda-tfstate-<ACCOUNT_ID> --key bootstrap/terraform.tfstate
aws iam get-role --role-name veda-gh-apply --query 'Role.[PermissionsBoundary.PermissionsBoundaryArn,MaxSessionDuration]'
aws iam get-role --role-name veda-gh-plan  --query Role.AssumeRolePolicyDocument   # sub = repo:slaggala@37840263/veda-spaces@1392733148:environment:staging-plan
aws iam get-policy-version --policy-arn arn:aws:iam::<ACCOUNT_ID>:policy/veda-boundary --version-id v1  # matches terraform output policy_documents
aws ec2 get-ebs-encryption-by-default                                            # true
aws ec2 get-instance-metadata-defaults                                           # HttpTokens required, hop limit 2
aws accessanalyzer list-analyzers --query 'analyzers[].name'                     # veda-account-analyzer
```

Then `make -C infra github-verify`: environments, reviewers, `can_admins_bypass: false` and `main` protection.

The first OIDC proof comes with AUT-301, when `10-infra-plan` assumes `veda-gh-plan` from the `staging-plan` environment.

## 6. Recovery

| Situation | Action |
|---|---|
| The plan shows something unexpected | Stop. Nothing has been created. Fix the input or the code and plan again. |
| Discovery refuses the account (name, alias, foreign resources) | Stop. Check you have the right account. If a listed resource is legitimately there, add it to `allowed_foreign_resources` in a reviewed change. |
| The plan guard refuses a delete or replace | Nothing is applied. Find out why the plan wants to remove something; a destroy is only ever a reviewed, owner-run change outside this workflow. |
| An apply run refuses the reviewed plan (checksum, commit, account, state changed) | Plan again on the current commit and apply that run. |
| A first apply fails **before** state migration | Resources may exist while only local state (`infra/terraform/bootstrap/terraform.tfstate`) knows them. Locally, keep the file and rerun `bootstrap-apply`. In CI, download the `bootstrap-local-state-<run>` artifact, put it at that path, and rerun locally. Never delete it until migration succeeds. |
| The script refuses because local state exists while the bucket exists | A previous migration was interrupted. Compare the local file with `s3://…/bootstrap/terraform.tfstate`. Keep the newer serial in S3, then remove the local file. |
| Apply refuses: "GitHub environment protection is a prerequisite of apply" | An environment is missing or unprotected, or `main` is not protected. Run `make -C infra github-environments REVIEWERS=<login> APPLY=1`, then `make -C infra github-verify`, then apply again. Never create the environments by hand without reviewers. |
| Apply stops after Terraform: "the live protections … are not the reviewed ones" | Something other than the plan changed the bucket or key policy, encryption or rotation. Do not use the state. Compare `aws kms get-key-policy` and `aws s3api get-bucket-policy` with `terraform output policy_documents`, find who changed them (CloudTrail), then plan and apply again with an owner session. |
| The owner principal changed (new SSO permission set, other admin role) | The new principal cannot touch bootstrap state or the key until it is listed. Add it to `bootstrap_principal_arns` in a reviewed change and apply that change **with the old principal** (or the account root). If the old principal no longer exists, the account root can replace the bucket policy and the key policy (both keep the root). |
| A state lock is stuck (`*.tflock` object) | Confirm no job is running, then `terraform force-unlock <ID>` from the bootstrap directory. |
| The session expired mid-run | Get a new temporary session and rerun. Applies are idempotent. |
| An OIDC provider already exists (e.g. created by someone else) | Discovery passes it in as existing and the bootstrap does not manage it. |
| The account already manages its own guardrails | Before the **first** apply, set `manage_account_guardrails: false` in the manifest (reviewed change). After they are created, setting it to `false` makes the plan fail (`prevent_destroy`) instead of removing them; handing them over is a manual, owner-run `terraform state rm` of the guardrail resources. |

## 7. Permissions model

| Role | GitHub environment | Can |
|---|---|---|
| `veda-gh-plan` | `staging-plan` (any branch, **reviewer required**) | Read-only (AWS `ReadOnlyAccess`) minus the denies below; read state; write only the `staging/*.tflock` lock objects |
| `veda-gh-apply` | `staging-infra` (main only, reviewer) | Create the staging stacks; IAM only on `veda-*` resources; new roles **must** carry `veda-boundary` |
| `veda-gh-deploy` | `staging` (main only, reviewer) | Push to ECR `veda-api`; write the artifacts bucket (this account only); run `veda-deploy`, `veda-drill-*` and `veda-seed-fixtures` on the host tagged project=veda-spaces, env=staging; read alarms, logs, the drill queue |
| `veda-gh-evidence` | `staging-evidence` (main only) | `SecurityAudit`; run `veda-collect` on the tagged host; read `/veda/staging/config/*`; write the evidence bucket (this account only) |

Every environment has `can_admins_bypass: false`. `main` requires a pull request (0 approvals, so a single owner
can merge), enforced for admins, with no force push or deletion.

**Application data and secrets.** The plan, deploy and evidence roles are denied reads of Litestream, snapshot and
anchor objects, of `/veda/staging/app/*` parameters, and of Secrets Manager values. The plan role is further denied
every parameter value outside `/veda/staging/config/*` (including `/edge/*`), every object outside the state
bucket, log contents, console and command output, and data-plane reads. `veda-gh-apply` carries the same
explicit denies, **but** it administers the account (`ssm:*`, `ec2:*`, `lambda:*`, `iam:PassRole` of `veda-*`
roles). It can therefore reach that data through the host role, for example by running a command on the host. It
is controlled by the `staging-infra` approval and the reviewed plan, not by these denies (review package R1).

**Boundary (`veda-boundary`)** caps every Veda role, and every role those roles create. It refuses:
- any region except ap-south-1 (global services excepted);
- creating or re-bounding a role without `veda-boundary`, and any IAM write outside `veda-*` roles, policies and
  instance profiles (users, groups, `OrganizationAccountAccessRole`, SSO roles, identity providers, account settings);
- attaching `AdministratorAccess*`, `PowerUserAccess`, `IAMFullAccess`, `AWSOrganizationsFullAccess` or any
  `job-function/*` policy;
- Organizations and account changes;
- changes to the boundary, the `veda-gh-*` roles and policies (including creating new `veda-gh-*` names) and the OIDC provider;
- IAM roles, policies and instance profiles under a path (`role/veda-x/admin` would otherwise match `role/veda-*`) (RR-03);
- creating a role or changing a trust policy by any role but `veda-gh-apply` (RR-03);
- any use of a web-identity (OIDC) session of a role other than the four `veda-gh-*` roles (RR-03). SAML sessions
  are **not** covered: AWS sets `aws:FederatedProvider` for OIDC sessions only (N-01). SAML is closed instead by no
  Veda role being able to create a SAML provider and discovery refusing any account that has one;
- any S3 action on `bootstrap/*` state (read, copy, write, replicate, restore, tag, delete), and any change to the
  state bucket's configuration or versions, or replication into it (RR-01);
- weakening the account guardrails; stopping, deleting or re-scoping CloudTrail trails; archiving Access Analyzer
  findings; launching or switching an instance to IMDSv1;
- sharing snapshots or AMIs, KMS grants to other accounts, S3 writes to other accounts, Lambda permissions for other
  accounts, public function URLs;
- bypassing GOVERNANCE Object Lock retention.

**State bucket policy (RR-01).** Holds for every principal, bounded or not, whatever its name or path: only the
`bootstrap_principal_arns` and the account root may perform any S3 action on `bootstrap/*`, change the bucket's
configuration, delete an object version or replicate into the bucket; nobody reaches the bucket through an access
point.

**State key policy (RR-02).** The key policy itself, not an alias or the boundary, protects the key: only the owner
principals and the account root may administer it (everyone else may only describe it, read its metadata and use it
for S3); it encrypts and decrypts only through S3, only for objects of the state bucket, one object at a time (S3
Bucket Keys are off); `bootstrap/*` objects only for the owners; no other account. The GitHub roles' own key
permission has the same bounds (through S3, `staging/*` only).

**Trust policies (RR-03).** IAM has no condition key for a trust policy's content. What IAM does enforce: only
`veda-gh-apply` can write any trust policy, nothing under a path can be created, and a federated session of any role
but the `veda-gh-*` roles can do nothing (OIDC; for SAML see the boundary above). What the plan guard enforces on every plan (`check-plan.sh`; AUT-301 must
run it on every staging plan, §8): the trust content of every role the apply role creates.

## 8. Constraints on later stories

| Story | Constraint from this bootstrap |
|---|---|
| AUT-104 | Trails can be created and started by `veda-gh-apply`, but never updated, re-scoped (event selectors) or deleted by any Veda role. Define the trail's event selectors at creation; later changes are owner-run. |
| AUT-107 | Seeded app secrets are never Terraform-managed (the CI roles cannot read them). |
| AUT-201/203 | `veda-gh-plan` cannot read parameters outside `/veda/staging/config/*`, so secret-bearing parameters (`/edge/*`) must not be refreshed by a plan (seed them outside Terraform, or with write-only arguments). Cloudflare secrets that stay in Terraform state are readable by plan runs, which now need a reviewer. |
| AUT-301 | Run `infra/scripts/check-plan.sh` on every staging plan and refuse the apply on any finding. Use the repository variables `AWS_ROLE_ARN_PLAN/APPLY/DEPLOY/EVIDENCE`. Apply only a reviewed saved plan bound by digest, as `00-bootstrap` does (`verify-run.sh plan-run`, a `plan_sha256` input, a credential-free preflight job and `verify-run.sh approval`). Only `veda-gh-apply` can create roles or write trust. |
| AUT-1xx | Every Veda IAM role, policy and instance profile lives at path `/` and is named `veda-*`. Trust policy changes happen only through `veda-gh-apply`. State encryption uses per-object KMS context (no S3 Bucket Keys on the state bucket). |

## 9. Teardown

The state bucket and key have `prevent_destroy`, so `terraform destroy` refuses to remove them. **This is deliberate:
it is not a workflow step.** If the account itself is being retired:
1. destroy every other stack first;
2. remove the `prevent_destroy` lines in a reviewed change;
3. empty the bucket and destroy with an owner session.

The KMS key has a 30-day deletion window.
