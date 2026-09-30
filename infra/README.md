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
| AUT-002 Terraform bootstrap | `terraform/bootstrap/`: written and tested offline, remediated after independent review, **not applied** |
| AUT-003 bootstrap workflow | `.github/workflows/00-bootstrap.yml` + `scripts/`: **not run** |
| AUT-101 onward | not started (see `terraform/modules/README.md`) |

## Layout

```
infra/
  Makefile                 make -C infra help
  .tflint.hcl              tflint + AWS ruleset (pinned)
  config/
    staging-account.json   the approved staging account and the owners of its bootstrap state (reviewed change only;
                           null/empty until the owner commits it)
  scripts/
    lib.sh                 shared guards (region, approved account, account identity, fail-closed lookups)
    discover.sh            read-only auto-discovery → generated/discovered.json
    check-plan.sh          plan guard: no destroy, bounded roles at path /, GitHub trust only from each role's
                           protected environment, no external trust or resource policies
    bootstrap.sh           plan | apply of the approved plan (digest-bound), state migration, live protection check, outputs
    github-setup.sh        GitHub environments, main protection, --verify, --verify-environments, variables (dry run)
    verify-run.sh          00-bootstrap: plan run → artifact → approved digest binding; environment approval proof
  tests/                   offline script/workflow tests with stub aws, gh, terraform (make test-scripts)
  terraform/
    bootstrap/             state bucket + KMS, GitHub OIDC, 4 roles, permissions boundary, account guardrails
      tests/               offline `terraform test` suite, IAM policy evaluator, negative tests
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
make -C infra check                                             # offline: fmt, validate, test, test-scripts, tflint, checkov, shellcheck, actionlint
make -C infra bootstrap-plan  EXPECTED_ACCOUNT_ID=123456789012   # read-only against the approved Veda account
make -C infra bootstrap-apply EXPECTED_ACCOUNT_ID=123456789012 PLAN_FILE=generated/bootstrap.tfplan PLAN_SHA256=<digest>
                                                                 # applies that approved plan; asks to type the account ID
make -C infra github-environments                                # dry run; APPLY=1 to create (and protect main)
make -C infra github-verify                                      # read back; fails on drift
make -C infra github-variables                                   # dry run; APPLY=1 to set
```

## Safety rules

- **One approved account, one region:** the account is committed in `config/staging-account.json` and changed only
  by a reviewed pull request. Every script, the workflow and the Terraform validation check it. Discovery also checks
  the live account name and alias and refuses foreign resources. The provider pins `allowed_account_ids`, and the
  boundary refuses any region except ap-south-1.
- **No long-lived AWS keys in GitHub:** only the one-time bootstrap uses owner credentials, and it accepts
  temporary STS credentials only (`ASIA…` key with a session token). Everything after it uses OIDC roles pinned to
  one repository and one GitHub environment.
- **Apply only what was approved (RR-05):** `00-bootstrap` defaults to `plan`. Apply takes the plan run ID and the
  reviewed plan's SHA-256 (shown in the run name to the approver), and applies only a file with that digest, from a
  successful plan run of `00-bootstrap.yml` on `main` for the same commit, whose artifact matches the digest GitHub
  recorded and whose re-rendered text is the reviewed text. The plan guard refuses every destroy.
- **Environment protection is a prerequisite (RR-07):** apply refuses to start unless every GitHub environment is
  protected and `main` is protected; in the workflow a credential-free job checks this before the environment job
  starts, and the environment job proves its approval before reading a secret.
- **The boundary cannot be escaped:** every Veda role, and every role they create, carries `veda-boundary`; IAM
  writes outside `veda-*` at path `/` are refused; only `veda-gh-apply` creates roles or writes trust (RR-03).
- **Bootstrap state and its key are owner-only (RR-01, RR-02):** the state bucket policy and the state key's own key
  policy admit only the manifest's `bootstrap_principal_arns` and the account root to bootstrap state and to their
  administration; they are read back and compared after every apply.
- **Application data and secrets:** the plan, deploy and evidence roles cannot read Litestream/snapshot/anchor
  objects or `/veda/staging/app/*`. The apply role administers the account and is controlled by its approval, not by
  those denies (runbook §7).
- **Data-bearing and protective resources** (`prevent_destroy`): state bucket, state KMS key, account guardrails,
  OIDC provider; later the data volume and the Object Lock buckets.
