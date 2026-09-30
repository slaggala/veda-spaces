# Staging bootstrap runbook (AUT-002, AUT-003)

This runbook covers the one-time bootstrap of the **dedicated Veda staging AWS account** in **ap-south-1**.
It is the only step that uses owner credentials. After it, every workflow runs through GitHub OIDC.
It has no dependency on Aurion or any other system, and does not deploy the application or enable public intake.

- **Status:** written and tested offline; remediated after the independent review (F1–F10, see the review package §8).
  It has **not been run** against any AWS account.
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
Terraform variable validation refuse to run while `account_id` is `null`, or for any other account (F3).

| Field | Value |
|---|---|
| `account_id` | The 12-digit ID of the dedicated staging account |
| `account_name` | Its name exactly as `aws account get-account-information` returns it (for example `veda-staging`) |
| `account_alias` | Its IAM account alias, or `null` if it has none |
| `manage_account_guardrails` | `true` unless the account already manages the guardrails (§6). Changing it later never removes them |
| `allowed_foreign_resources` | Pre-existing IAM roles, users, buckets, instances or Lambda functions that are *not* Veda's but may stay. Empty for a new account (`OrganizationAccountAccessRole` is listed by default) |

Discovery then refuses the run unless the live account name and alias match, neither looks like production or
Aurion (`prod`, `aurion`), and the account holds nothing beyond `veda-*` resources, service-linked and SSO roles,
and the allowlist.

Then, at run time:

| # | Item | Used for |
|---|---|---|
| 1 | The same account ID | `EXPECTED_ACCOUNT_ID`: checked against the manifest and the session |
| 2 | A **temporary** administrator session in that account (access key `ASIA…`, secret key, **session token**) | Bootstrap only; it expires by itself |
| 3 | A Cloudflare API token with **Zone:Read and DNS:Read on `vedaspaces.com` only**, short TTL (`CF_READ_TOKEN`) | Optional at bootstrap: discovers the account and zone IDs and checks for name collisions. No Cloudflare write or edit token is needed or accepted at this stage |
| 4 | Optional: a fine-grained GitHub token (`GH_ADMIN_TOKEN`) with **only *Variables: write*** on this repository | Lets `00-bootstrap` publish the role ARNs as repository variables; without it, run `make -C infra github-variables APPLY=1` locally. Never grant it *Environments* or *Administration* |

Ways to obtain the temporary session (pick one):

```sh
# From the Organizations management account, into the new member account:
aws sts assume-role --role-arn arn:aws:iam::<ACCOUNT_ID>:role/OrganizationAccountAccessRole \
  --role-session-name veda-bootstrap --duration-seconds 3600

# From an IAM Identity Center profile for the new account:
aws configure export-credentials --profile <veda-staging-admin> --format env
```

## 3. Run it

### Option A: locally (recommended for the first run)

Prerequisites: `aws` v2, `terraform` 1.16.4, `jq`, `curl`, `git`, `gh` (authenticated as a repository admin).
Run from a clean checkout of `main` that includes the manifest commit.

```sh
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… AWS_SESSION_TOKEN=… AWS_REGION=ap-south-1
export CF_API_TOKEN=…                                            # optional (read-only token)

make -C infra check                                              # offline checks
make -C infra github-environments REVIEWERS=<login>              # dry run: environments + main protection
make -C infra github-environments REVIEWERS=<login> APPLY=1
make -C infra github-verify                                      # read back; fails on any drift
make -C infra bootstrap-plan  EXPECTED_ACCOUNT_ID=<ACCOUNT_ID>    # read-only; review infra/generated/bootstrap-plan.txt
make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=<ACCOUNT_ID> PLAN_FILE=generated/bootstrap.tfplan
                                                                 # applies that reviewed plan; type the account ID
make -C infra github-variables                                   # dry run, then again with APPLY=1
```

`bootstrap-apply` without `PLAN_FILE` plans, shows the plan and asks for the account ID before applying the plan it
just showed. It never applies anything that was not shown.

### Option B: the `00-bootstrap` workflow

A `workflow_dispatch` workflow can only be started once it exists on the default branch. Merge this change first.

1. Create and verify the GitHub environments and the `main` protection:
   `make -C infra github-environments REVIEWERS=<login> APPLY=1 && make -C infra github-verify`.
2. Store the temporary session in the `bootstrap` environment:
   ```sh
   gh secret set BOOTSTRAP_AWS_ACCESS_KEY_ID     --env bootstrap
   gh secret set BOOTSTRAP_AWS_SECRET_ACCESS_KEY --env bootstrap
   gh secret set BOOTSTRAP_AWS_SESSION_TOKEN     --env bootstrap
   gh secret set CF_READ_TOKEN                   --env bootstrap   # optional, read-only
   gh secret set GH_ADMIN_TOKEN                  --env bootstrap   # optional, Variables: write only
   ```
3. Run it: Actions → **00-bootstrap** → mode `plan`. Read the job summary and the `bootstrap-plan-<run id>`
   artifact (`bootstrap-plan.txt`). Note the run ID.
4. Run it again with mode `apply` and `plan_run_id` = that run ID. A `bootstrap` environment reviewer approves the
   run. It applies **that plan file**, after checking that the plan run was a successful `plan` run of this workflow
   on `main` for the same commit, and that the plan's SHA-256, commit and account match its metadata (F4).
   If anything changed in between (a new commit, or state), plan again.
5. **Delete the bootstrap secrets** afterwards (they have expired anyway):
   `gh secret delete BOOTSTRAP_AWS_ACCESS_KEY_ID --env bootstrap` (and the other two).

The workflow refuses to run without a session token, with a key that is not an `ASIA…` temporary key, from any
branch but `main`, while `main` is unprotected, or for an account other than the manifest's.

## 4. What the run does

1. **Guards:** region must be `ap-south-1`; the account must be the manifest's and `aws sts get-caller-identity`
   must return it. The Terraform provider also pins `allowed_account_ids`, and the Terraform variable validation
   checks the manifest too.
2. **Account identity** (fails closed): account name and alias match the manifest; neither looks like production
   or Aurion; no foreign IAM roles or users, S3 buckets, EC2 instances or Lambda functions (§2).
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
   `bootstrap-plan.meta.json` (commit, clean tree, account, repository, SHA-256, whether state existed).
5. **Plan guard** (`check-plan.sh`, on every plan and again before apply). It refuses:
   - any delete or replace;
   - any IAM role without `veda-boundary`, or with a trust policy unknown at plan time;
   - any trust in another account, in everyone, or in an identity provider other than GitHub;
   - GitHub trust on any role other than `veda-gh-*`, or with a subject other than `repo:<owner>/<repo>:environment:<name>`;
   - any resource policy, Lambda permission, function URL, KMS grant or AMI/snapshot permission that opens something
     to another account or the public.
6. **Apply** (apply mode only). This applies the reviewed plan file and nothing else; Terraform refuses it if the
   state changed since. On the first run it then:
   - migrates the local state to `s3://veda-tfstate-<account>/bootstrap/terraform.tfstate`;
   - checks that the object exists (in this account);
   - deletes the local copy.
7. **Outputs:** `infra/generated/bootstrap-outputs.json` lists the role ARNs, the state bucket and key, and the backend settings.

Re-running is safe. When the state bucket exists, the script uses the remote state and the plan shows only the differences.

## 5. Checks after apply

All of these commands are read-only:

```sh
aws s3api get-bucket-versioning        --bucket veda-tfstate-<ACCOUNT_ID>        # Enabled
aws s3api get-bucket-encryption        --bucket veda-tfstate-<ACCOUNT_ID>        # aws:kms, alias/veda-tfstate key
aws s3api get-public-access-block      --bucket veda-tfstate-<ACCOUNT_ID>        # all true
aws s3api head-object --bucket veda-tfstate-<ACCOUNT_ID> --key bootstrap/terraform.tfstate
aws iam get-role --role-name veda-gh-apply --query 'Role.[PermissionsBoundary.PermissionsBoundaryArn,MaxSessionDuration]'
aws iam get-role --role-name veda-gh-plan  --query Role.AssumeRolePolicyDocument   # sub = repo:<owner>/<repo>:environment:staging-plan
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
- writes to `bootstrap/*` state, and any change to the state bucket's configuration, versions or key;
- weakening the account guardrails; stopping, deleting or re-scoping CloudTrail trails; archiving Access Analyzer
  findings; launching or switching an instance to IMDSv1;
- sharing snapshots or AMIs, KMS grants to other accounts, S3 writes to other accounts, Lambda permissions for other
  accounts, public function URLs;
- bypassing GOVERNANCE Object Lock retention.

The state bucket's own policy also refuses every `veda-*` role bootstrap-state writes and bucket changes, even a
role that were somehow outside the boundary.

**Not enforceable by IAM, enforced by the plan guard instead:** a trust policy's content (other accounts, GitHub
subjects) and resource policies' principals. `check-plan.sh` checks these on every bootstrap plan; AUT-301 must run
it on every staging plan (§8).

## 8. Constraints on later stories

| Story | Constraint from this bootstrap |
|---|---|
| AUT-104 | Trails can be created and started by `veda-gh-apply`, but never updated, re-scoped (event selectors) or deleted by any Veda role. Define the trail's event selectors at creation; later changes are owner-run. |
| AUT-107 | Seeded app secrets are never Terraform-managed (the CI roles cannot read them). |
| AUT-201/203 | `veda-gh-plan` cannot read parameters outside `/veda/staging/config/*`, so secret-bearing parameters (`/edge/*`) must not be refreshed by a plan (seed them outside Terraform, or with write-only arguments). Cloudflare secrets that stay in Terraform state are readable by plan runs, which now need a reviewer. |
| AUT-301 | Run `infra/scripts/check-plan.sh` on every staging plan and refuse the apply on any finding. Use the repository variables `AWS_ROLE_ARN_PLAN/APPLY/DEPLOY/EVIDENCE`. Apply only a reviewed saved plan, as `00-bootstrap` does. |

## 9. Teardown

The state bucket and key have `prevent_destroy`, so `terraform destroy` refuses to remove them. **This is deliberate:
it is not a workflow step.** If the account itself is being retired:
1. destroy every other stack first;
2. remove the `prevent_destroy` lines in a reviewed change;
3. empty the bucket and destroy with an owner session.

The KMS key has a 30-day deletion window.
