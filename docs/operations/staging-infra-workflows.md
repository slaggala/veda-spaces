# Staging infrastructure workflows (AUT-301)

How the staging stacks are planned and applied after the bootstrap (AUT-002, applied 2026-10-03). Every run uses
GitHub OIDC: no AWS key is stored in GitHub, and no owner credential is used.

- **Status:** written and tested offline. `10-infra-plan` is live: its first run plans the empty `staging-core` root.
  **`11-infra-apply` is disabled**: every run is refused until owner decision OD-B7 and gate N-04-S are recorded in
  [`infra/config/apply-gate.json`](../../infra/config/apply-gate.json).
- **Code:**
  - workflows [`10-infra-plan.yml`](../../.github/workflows/10-infra-plan.yml) and [`11-infra-apply.yml`](../../.github/workflows/11-infra-apply.yml);
  - scripts [`stack.sh`](../../infra/scripts/stack.sh), [`oidc-session.sh`](../../infra/scripts/oidc-session.sh) and [`verify-run.sh`](../../infra/scripts/verify-run.sh) (`--stack`);
  - the root [`envs/staging-core`](../../infra/terraform/envs/staging-core).
- **Review:** [AUT-301 review package](../implementation/staging/AUT-301-review-package.md);
  [AUT-112 review package](../implementation/staging/AUT-112-review-package.md) (the first stack: the budget).

## 1. What runs where

| Workflow | Trigger | Environment (reviewer) | AWS role (OIDC) | Can |
|---|---|---|---|---|
| `10-infra-plan` | Pull request touching the stack, its modules, `infra/scripts` or `infra/config`; push to `main` touching the stack or modules; manual | `staging-plan` (required, any branch) | `veda-gh-plan` | Read the account (minus data); read `staging/*` state; write only `staging/*.tflock` |
| `11-infra-apply` | Manual only, from `main` | `staging-infra` (required, main only) | `veda-gh-apply` | Create the staging stacks within `veda-boundary` (runbook staging-bootstrap §7) |

Each role trusts exactly `repo:slaggala@37840263/veda-spaces@1392733148:environment:<its environment>`: immutable
GitHub subject ID trust, by owner and repository numeric ID (bootstrap, RR-03; RR-A closed by the re-apply of
2026-10-04). A job outside that environment, or a renamed, transferred or re-registered repository, cannot get the
role, and a fork's pull request gets no OIDC token.

## 2. Plan (`10-infra-plan`)

1. The job waits for the `staging-plan` reviewer. Then it proves the approval (`verify-run.sh approval`) and that every
   environment and `main` are still protected, with every required check.
2. It installs the pinned Terraform (SHA-256 verified) and assumes `veda-gh-plan` (`oidc-session.sh --role plan`). The
   session must be that role in the approved account; secret and token are masked.
3. `stack.sh plan --stack core` proves the session is confined to Mumbai (a us-east-1 read must be denied, by
   `veda-boundary`), then:
   - initialises the backend: `veda-tfstate-<account>`, key `staging/core.tfstate`, the state key, native lock;
   - plans into a saved file;
   - runs the plan guard (`check-plan.sh`: no destroy, Mumbai only, roles bounded at path `/`, no GitHub or external trust).

   The plan reads two inputs besides the code: the reviewed budget decision `infra/config/staging-budget.json` and
   the alert recipient, from the `staging-plan` environment secret `BUDGET_ALERT_EMAIL` (§6). It stops while either
   is missing.

   The plan text goes to a file, **never to the job log**. The job prints only the change summary ("No changes" or
   `Plan: …`) and the plan's SHA-256.
4. **Plan text and artifact (gate N-04-S).** The repository is public, so everyone can read job logs and artifacts. The
   plan file, its text and its metadata are uploaded as `core-plan-<run>` only from a private repository or once the
   owner accepts publishing them. Until then a plan run is a dry run: no apply can use it.

## 3. Apply (`11-infra-apply`), disabled until OD-B7

Once the gates are decided, the procedure is:
1. Run `10-infra-plan` manually on `main` (workflow_dispatch). Read its plan text (the artifact) and note its run ID and
   the plan SHA-256 in its summary.
2. Run `11-infra-apply` with `plan_run_id` and `plan_sha256`. The run name shows both, so the `staging-infra` reviewer
   approves that exact digest.
3. The **preflight** job holds no environment, secret or token. It checks:
   - the apply gates (`stack.sh gate`);
   - the inputs, the approved repository (name and ID), `main` and this workflow file;
   - environment protection;
   - the binding of the approved plan (`verify-run.sh plan-run --stack core`). The plan run must be a successful
     workflow_dispatch run of `10-infra-plan` on `main` for this commit. The artifact's bytes must match the digest GitHub
     recorded at upload, the plan file must match the approved digest, and the metadata must name that run, commit and
     workflow.
4. The **apply** job, behind the `staging-infra` reviewer:
   - checks the gates again and proves its approval;
   - fetches and verifies the plan again;
   - assumes `veda-gh-apply`.

   `stack.sh apply` then refuses unless every one of these holds:
   - the session is `veda-gh-apply`, confined to Mumbai;
   - the run is `11-infra-apply` on `main`;
   - the metadata matches the stack, account, repository, commit, plan workflow, plan run and Terraform version;
   - the plan text, rendered again from the file, is the reviewed text;
   - the plan guard passes again.

   It applies that file only. Terraform refuses it if the state changed since.

**Gates.** [`apply-gate.json`](../../infra/config/apply-gate.json) lists:
- **OD-B7**, the `veda-gh-apply` trust-writing gap: `CLOSED` or `ACCEPTED`;
- **N-04-S**, plan text in a public repository: `ACCEPTED` or `PRIVATE_REPOSITORY`.

Each needs a `record`: a decision document committed in the repository. Missing, malformed, undecided or unrecorded
gates refuse the run in the preflight, in the apply job and in `stack.sh`. Changing the file is a reviewed pull request.

## 4. Running the first plan (proof of AUT-301)

On the AUT-301 pull request, `10-infra-plan` starts automatically and waits for the `staging-plan` reviewer. Approve it
(Actions → the run → **Review deployments** → `staging-plan` → Approve). Expected:
- the approval proof passes, and the environments verify;
- the OIDC session is `arn:aws:sts::813238078849:assumed-role/veda-gh-plan/gh-<run>-<attempt>-plan`;
- the Mumbai confinement holds: us-east-1 is denied by the boundary;
- the backend is `s3://veda-tfstate-813238078849/staging/core.tfstate`;
- `plan summary: No changes.`, then the plan guard passes, then `plan mode: nothing was created`.

The summary says the plan text is not published (N-04-S). A pull-request run uploads no artifact, so it proves the
OIDC session, the region confinement and the plan guards, but **not** artifact digest binding: that needs a plan on
`main` with an uploaded artifact (N-04-S decided) and an apply run (OD-B7 decided). Proof of 2026-10-04: review package
§8. No resource is created, and no state object is written; only
a lock file appears while the plan runs and is removed after it. CloudTrail records `AssumeRoleWithWebIdentity` and
read calls only.

## 5. Recovery

| Situation | Action |
|---|---|
| `AssumeRoleWithWebIdentity` refused | The job is not in the role's environment, the repository no longer issues the immutable subject (`make -C infra github-verify`), or the repository or role changed. Check `vars.AWS_ROLE_ARN_*` against the bootstrap outputs. Never widen the trust from a workflow |
| "the session can act in us-east-1" | The role lost `veda-boundary`. Stop: investigate with CloudTrail before any further run |
| Plan guard refuses | The plan wants something the rules forbid (destroy, other region, unbounded role, external trust). Fix the code; never bypass the guard |
| "Error acquiring the state lock" | Another plan or apply is running; wait. A stale `staging/core.tfstate.tflock` after a crashed run: confirm nothing runs, then remove it with an owner session |
| Apply refused by the gates | Expected until OD-B7 and N-04-S are decided (§3) |
| Apply refused: digest, run, commit or text mismatch | Plan again on the current `main` commit and approve the new digest |

## 6. Inputs of the staging-core plan (AUT-112)

| Input | Where | Who changes it |
|---|---|---|
| Budget name, monthly limit (USD), forecast alert thresholds | [`infra/config/staging-budget.json`](../../infra/config/staging-budget.json) | A reviewed pull request (owner decision O16). `monthly_limit_usd: null` means undecided: the plan stops with the O16 message |
| Alert recipient | Secret `BUDGET_ALERT_EMAIL` of the **`staging-plan` environment** | The owner, once: `gh secret set BUDGET_ALERT_EMAIL --env staging-plan --repo slaggala/veda-spaces` (it prompts for the value; nothing is echoed) |

The recipient is not a credential. It is a secret only so that GitHub masks it: the repository is public, and GitHub
prints a step's plain variables (`vars.*`) in the job log. It is the workflows' only stored secret; AWS access stays
OIDC only. Terraform marks it sensitive, so the plan text shows `(sensitive value)`. The saved plan file holds it, as it
holds every planned value: if N-04-S is decided as `ACCEPTED` (publish the plan artifact from the public repository),
the address becomes public with the artifact. `PRIVATE_REPOSITORY` avoids that.

Changing the recipient: update the secret, then plan and apply again (an in-place update of the budget).

