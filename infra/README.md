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
| AUT-002 Terraform bootstrap | `terraform/bootstrap/`: **applied to `veda-staging` (813238078849) on 2026-10-03**; evidence in `docs/release-evidence/AUT-002/` |
| AUT-003 bootstrap workflow | `scripts/` run locally (Option A) for the first bootstrap; `.github/workflows/00-bootstrap.yml` **not run** (public repository) |
| AUT-301 infra workflows | `.github/workflows/10-infra-plan.yml` (OIDC plan, live) and `11-infra-apply.yml` (**disabled** until OD-B7: `config/apply-gate.json`); `scripts/stack.sh`, `scripts/oidc-session.sh`; runbook `docs/operations/staging-infra-workflows.md` |
| AUT-112 budget | `terraform/modules/budgets/` in `envs/staging-core/`: monthly cost budget, forecast alerts at 80% and 100% (O16); decision in `config/staging-budget.json` (**limit undecided**), recipient from the `staging-plan` secret `BUDGET_ALERT_EMAIL`. Written and tested offline; **not applied** |
| AUT-101 … AUT-111 | not started (see `terraform/modules/README.md`) |

## Layout

```
infra/
  Makefile                 make -C infra help
  .tflint.hcl              tflint + AWS ruleset (pinned)
  config/
    staging-account.json   the approved staging account and the owners of its bootstrap state (reviewed change only;
                           null/empty until the owner commits it)
    staging-budget.json    AUT-112 budget decision (O16): name, monthly limit, forecast thresholds; no recipient
  scripts/
    lib.sh                 shared guards (region, approved account, account identity, fail-closed lookups)
    discover.sh            read-only auto-discovery → generated/discovered.json
    check-plan.sh          plan guard: no destroy, bounded roles at path /, GitHub trust only from each role's
                           protected environment, no external trust or resource policies
    bootstrap.sh           plan | apply of the approved plan (digest-bound), state migration, live protection check, outputs
    github-setup.sh        GitHub environments, main protection, --verify, --verify-environments, variables (dry run)
    verify-run.sh          plan run → artifact → approved digest binding (00-bootstrap, or --stack for 10/11); approval proof
    stack.sh               staging stack plan | apply of the approved digest | gate (AUT-301, OIDC sessions only)
    oidc-session.sh        GitHub OIDC token → veda-gh-plan / veda-gh-apply session, masked, into $GITHUB_ENV
    install-tools.sh       pinned, SHA-256-verified check tools (tools/tools.lock); --only terraform for the workflows
  tests/                   offline script/workflow tests with stub aws, gh, terraform (make test-scripts)
  terraform/
    bootstrap/             state bucket + KMS, GitHub OIDC, 4 roles, permissions boundary, account guardrails
      tests/               offline `terraform test` suite, IAM policy evaluator, negative tests
    modules/               AUT-101 … AUT-112, AUT-201 … AUT-205
    envs/staging-core/     AWS root (AUT-1xx): backend at init (staging/core.tfstate), provider pinned to the manifest account
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
| shellcheck / actionlint / checkov | 0.11.0 / 1.7.12 / 3.3.21 |
| actions/checkout, hashicorp/setup-terraform, actions/upload-artifact | pinned by commit SHA |

The check tools are pinned with their SHA-256 in [`tools/tools.lock`](tools/tools.lock) (linux and macOS, amd64 and
arm64) and checkov with every dependency in [`tools/requirements-checkov.txt`](tools/requirements-checkov.txt)
(hash-locked, Python 3.13). `make -C infra tools` installs exactly these into `infra/.tools`; `make -C infra check`
refuses to run with any other version.

**CI (RD-02):** the `infra` job of `.github/workflows/ci.yml` installs the same tools, verifies the bootstrap
prerequisites that need no AWS access (approved repository by name and ID, complete manifest, protected environments,
`main` protected with every required check) and runs `make -C infra check`. It holds no AWS credential. `infra` is a
required status check on `main`, so a failure blocks the merge; `github-setup.sh` keeps the required checks equal to
the jobs of `ci.yml`.

## Commands

```sh
make -C infra tools                                             # install the pinned check tools (SHA-256 verified) into infra/.tools
make -C infra check                                             # offline: tool versions, manifest complete, fmt, validate, test, test-scripts, tflint, checkov, shellcheck, actionlint
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
