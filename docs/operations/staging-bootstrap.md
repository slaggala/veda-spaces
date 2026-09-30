# Staging bootstrap runbook (AUT-002, AUT-003)

This runbook covers the one-time bootstrap of the **dedicated Veda staging AWS account** in **ap-south-1**.
It is the only step that uses owner credentials. After it, every workflow runs through GitHub OIDC.
It has no dependency on Aurion or any other system, and does not deploy the application or enable public intake.

- **Status:** written and tested offline. It has **not been run** against any AWS account.
- **Code:** [`infra/terraform/bootstrap`](../../infra/terraform/bootstrap), [`infra/scripts`](../../infra/scripts),
  [`.github/workflows/00-bootstrap.yml`](../../.github/workflows/00-bootstrap.yml).

## 1. What the bootstrap creates

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `veda-tfstate-<account>` | Terraform state for every stack: versioned, SSE-KMS, TLS-only, public access blocked, `prevent_destroy` |
| KMS key + alias | `alias/veda-tfstate` | State encryption; yearly rotation; `prevent_destroy` |
| IAM OIDC provider | `token.actions.githubusercontent.com` | GitHub Actions federation (reused if the account already has one) |
| IAM policy | `veda-boundary` | Permissions boundary on every Veda role (§7) |
| IAM roles | `veda-gh-plan`, `veda-gh-apply`, `veda-gh-deploy`, `veda-gh-evidence` | Workflow roles, one per GitHub environment, one-hour sessions |
| Account guardrails | — | S3 public-access block for the account, EBS encryption by default, EBS snapshot and AMI public sharing blocked, IMDSv2 required by default (hop limit 2), IAM Access Analyzer |

Nothing else is created: no VPC, no instance, no bucket other than the state bucket, no Cloudflare resource.

## 2. What the owner provides

| # | Item | Used for |
|---|---|---|
| 1 | The dedicated AWS account ID (12 digits) | `EXPECTED_ACCOUNT_ID`: every step refuses any other account |
| 2 | A **temporary** administrator session in that account (access key, secret key, **session token**) | Bootstrap only; it expires by itself |
| 3 | A Cloudflare API token with read access to zone `vedaspaces.com` (`CF_READ_TOKEN`) | Optional at bootstrap: discovers the account and zone IDs and checks for name collisions |
| 4 | Optional: a fine-grained GitHub token (`GH_ADMIN_TOKEN`) with *Variables: write* and *Environments: write* on this repository | Lets `00-bootstrap` publish role ARNs as variables; without it, run `make -C infra github-variables APPLY=1` locally |

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

```sh
export AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… AWS_SESSION_TOKEN=… AWS_REGION=ap-south-1
export CF_API_TOKEN=…                                            # optional (read-only token)

make -C infra check                                              # offline checks
make -C infra bootstrap-plan  EXPECTED_ACCOUNT_ID=<ACCOUNT_ID>    # read-only; review infra/generated/bootstrap-plan.txt
make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=<ACCOUNT_ID>    # type the account ID to confirm
make -C infra github-environments REVIEWERS=<login>              # dry run, then again with APPLY=1
make -C infra github-variables                                   # dry run, then again with APPLY=1
```

### Option B: the `00-bootstrap` workflow

A `workflow_dispatch` workflow can only be started once it exists on the default branch. Merge this change first.

1. Create the GitHub environments: `make -C infra github-environments REVIEWERS=<login> APPLY=1`.
2. Store the temporary session in the `bootstrap` environment:
   ```sh
   gh secret set BOOTSTRAP_AWS_ACCESS_KEY_ID     --env bootstrap
   gh secret set BOOTSTRAP_AWS_SECRET_ACCESS_KEY --env bootstrap
   gh secret set BOOTSTRAP_AWS_SESSION_TOKEN     --env bootstrap
   gh secret set CF_READ_TOKEN                   --env bootstrap   # optional
   gh secret set GH_ADMIN_TOKEN                  --env bootstrap   # optional
   ```
3. Run it: Actions → **00-bootstrap** → mode `plan`, then read the job summary and the `bootstrap-plan-*` artifact.
4. Run it again with mode `apply`. A `bootstrap` environment reviewer approves the run.
5. **Delete the bootstrap secrets** afterwards (they have expired anyway):
   `gh secret delete BOOTSTRAP_AWS_ACCESS_KEY_ID --env bootstrap` (and the other two).

The workflow refuses to run without a session token, so long-lived keys cannot be used.

## 4. What the run does

1. **Guards:** region must be `ap-south-1`; `aws sts get-caller-identity` must return `EXPECTED_ACCOUNT_ID`. The
   Terraform provider also pins `allowed_account_ids`.
2. **Discovery** (`discover.sh`, read-only), written to `infra/generated/discovered.json`:
   - account and caller;
   - availability zones, and whether t4g.medium is offered in ap-south-1a;
   - the Amazon Linux 2023 arm64 AMI;
   - SES sandbox status;
   - whether an OIDC provider already exists, and whether the bootstrap created it;
   - whether the state bucket and key exist, and whether the roles do;
   - current account guardrails;
   - GitHub repository;
   - Cloudflare account and zone, planned-name collisions and live-site records;
   - the operator's public IP.
3. **Plan:** `terraform plan`, with the plan text saved in `infra/generated/bootstrap-plan.txt`.
4. **Apply** (apply mode only). This applies the saved plan. On the first run it then:
   - migrates the local state to `s3://veda-tfstate-<account>/bootstrap/terraform.tfstate`;
   - checks that the object exists;
   - deletes the local copy.
5. **Outputs:** `infra/generated/bootstrap-outputs.json` lists the role ARNs, the state bucket and key, and the backend settings.

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
aws ec2 get-ebs-encryption-by-default                                            # true
aws ec2 get-instance-metadata-defaults                                           # HttpTokens required, hop limit 2
aws accessanalyzer list-analyzers --query 'analyzers[].name'                     # veda-account-analyzer
```

The first OIDC proof comes with AUT-301, when `10-infra-plan` assumes `veda-gh-plan` from the `staging-plan` environment.

## 6. Recovery

| Situation | Action |
|---|---|
| The plan shows something unexpected | Stop. Nothing has been created. Fix the input or the code and plan again. |
| A first apply fails **before** state migration | Resources may exist while only local state (`infra/terraform/bootstrap/terraform.tfstate`) knows them. Locally, keep the file and rerun `bootstrap-apply`. In CI, download the `bootstrap-local-state-<run>` artifact, put it at that path, and rerun locally. Never delete it until migration succeeds. |
| The script refuses because local state exists while the bucket exists | A previous migration was interrupted. Compare the local file with `s3://…/bootstrap/terraform.tfstate`. Keep the newer serial in S3, then remove the local file. |
| A state lock is stuck (`*.tflock` object) | Confirm no job is running, then `terraform force-unlock <ID>` from the bootstrap directory. |
| The session expired mid-run | Get a new temporary session and rerun. Applies are idempotent. |
| An OIDC provider already exists (e.g. created by someone else) | Discovery passes it in as existing and the bootstrap does not manage it. |
| The account already manages its own guardrails | Rerun with `--skip-guardrails` (`bootstrap.sh`) so the bootstrap leaves them alone. |

## 7. Permissions model

| Role | GitHub environment | Can |
|---|---|---|
| `veda-gh-plan` | `staging-plan` (any branch, no reviewer) | Read-only (AWS `ReadOnlyAccess`); read state; write only the `*.tflock` lock object |
| `veda-gh-apply` | `staging-infra` (main only, reviewer) | Create the staging stacks; IAM only on `veda-*` resources; new roles **must** carry `veda-boundary`; cannot attach AdministratorAccess, PowerUserAccess, IAMFullAccess or AWSOrganizationsFullAccess |
| `veda-gh-deploy` | `staging` (main only, reviewer) | Push to ECR `veda-api`; write the artifacts bucket; run `veda-deploy`, `veda-drill-*` and `veda-seed-fixtures` on the host tagged project=veda-spaces, env=staging; read alarms, logs, the drill queue |
| `veda-gh-evidence` | `staging-evidence` (main only) | `SecurityAudit`; run `veda-collect` on the tagged host; read `/veda/staging/config/*`; write the evidence bucket |

Applies to every role:
- **Denied** reads of Litestream, snapshot and anchor objects, of `/veda/staging/app/*` parameters, and of Secrets Manager values.
- **Boundary (`veda-boundary`)** refuses any region except ap-south-1 (global services excepted). It also refuses:
  - IAM users, access keys and identity providers;
  - Organizations and account changes;
  - changes to the boundary, the `veda-gh-*` roles and the OIDC provider;
  - weakening the state bucket, the state key or the account guardrails;
  - stopping CloudTrail;
  - bypassing GOVERNANCE Object Lock retention.

## 8. Teardown

The state bucket and key have `prevent_destroy`, so `terraform destroy` refuses to remove them. **This is deliberate:
it is not a workflow step.** If the account itself is being retired:
1. destroy every other stack first;
2. remove the `prevent_destroy` lines in a reviewed change;
3. empty the bucket and destroy with an owner session.

The KMS key has a 30-day deletion window.
