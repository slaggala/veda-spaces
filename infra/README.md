# Veda Spaces staging infrastructure

Infrastructure as code for the **dedicated Veda staging AWS account** (ap-south-1) and its Cloudflare edge.
It has no dependency on Aurion or any other system, and never touches production.
Runbook: [docs/operations/staging-bootstrap.md](../docs/operations/staging-bootstrap.md).

```
git clone → owner provides AWS + Cloudflare access → 00-bootstrap → infra workflows → staging environment
```

## Status

| Item | State |
|---|---|
| AUT-001 repository structure | this directory |
| AUT-002 Terraform bootstrap | `terraform/bootstrap/`: written and tested offline, **not applied** |
| AUT-003 bootstrap workflow | `.github/workflows/00-bootstrap.yml` + `scripts/`: **not run** |
| AUT-101 onward | not started (see `terraform/modules/README.md`) |

## Layout

```
infra/
  Makefile                 make -C infra help
  .tflint.hcl              tflint + AWS ruleset (pinned)
  scripts/
    lib.sh                 shared guards (region, account, repository)
    discover.sh            read-only auto-discovery → generated/discovered.json
    bootstrap.sh           plan | apply of terraform/bootstrap, state migration, outputs
    github-setup.sh        GitHub environments and variables (dry run by default)
  terraform/
    bootstrap/             state bucket + KMS, GitHub OIDC, 4 roles, permissions boundary, account guardrails
      tests/               offline `terraform test` suite
    modules/               AUT-101 … AUT-112, AUT-201 … AUT-205
    envs/staging-core/     AWS root (AUT-1xx)
    envs/staging-edge/     Cloudflare root (AUT-2xx)
  host/                    cloud-init and host files (AUT-109)
  ssm-documents/           deploy, collect, drill documents (AUT-107)
  evidence/                gate evidence collectors (AUT-401)
  load/                    k6 load tests (AUT-405)
  generated/               (gitignored) discovery, plans, outputs
```

## Pinned versions

| Tool | Version |
|---|---|
| Terraform | 1.16.4 (`>= 1.10` required for S3 native locking) |
| AWS provider | `~> 6.66` (lock file: linux/darwin × amd64/arm64) |
| tflint / AWS ruleset | 0.64.0 / 0.49.0 |
| actions/checkout, hashicorp/setup-terraform, actions/upload-artifact | pinned by commit SHA |

## Commands

```sh
make -C infra check                                             # offline: fmt, validate, test, tflint, checkov, shellcheck, actionlint
make -C infra bootstrap-plan  EXPECTED_ACCOUNT_ID=123456789012   # read-only against the Veda account
make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=123456789012   # one time; asks to type the account ID
make -C infra github-environments                                # dry run; APPLY=1 to create
make -C infra github-variables                                   # dry run; APPLY=1 to set
```

## Safety rules

- **One account, one region:** every script checks the session's account against `EXPECTED_ACCOUNT_ID`, the
  provider pins `allowed_account_ids`, and the boundary refuses any region except ap-south-1.
- **No long-lived AWS keys in GitHub:** only the one-time bootstrap uses owner credentials, and it accepts
  temporary STS credentials only. Everything after it uses OIDC roles pinned to one repository and one GitHub environment.
- **Plan before apply:** `00-bootstrap` defaults to `plan`; apply needs the `bootstrap` environment reviewers.
- **No application data or secrets for CI roles:** every GitHub role is denied Litestream/snapshot/anchor
  object reads and `/veda/staging/app/*` parameters.
- **Data-bearing resources** (`prevent_destroy`): state bucket, state KMS key; later the data volume and the
  Object Lock buckets.
