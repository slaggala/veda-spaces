# Review package: AUT-112 (staging cost budget)

- **For:** independent review, the same process as AUT-001…003 and AUT-301.
- **Scope:** the first resource of the `staging-core` root: one monthly AWS cost budget with forecast email alerts to
  the owner. Code, tests, plan guard and documentation only. **Nothing is applied and no AWS resource is created by
  this change.** Applies stay disabled until OD-B7 and N-04-S are decided (`infra/config/apply-gate.json`).
- **Owner decision (O16, 2026-10-05):** forecast alerts at **80%** and **100%** of the monthly limit, by email to the
  owner's address; **monthly limit 25 USD** (alerts at forecast spend above 20 USD and 25 USD).
- **Base:** `main` after PR #17 (AUT-301).
- **Runbook:** [`staging-infra-workflows.md`](../../operations/staging-infra-workflows.md) §6.

## 1. Files

| File | What it is |
|---|---|
| `infra/terraform/modules/budgets/` (`main.tf`, `variables.tf`, `outputs.tf`, `versions.tf`, `README.md`) | One `aws_budgets_budget`: `COST`, `MONTHLY`, USD, one `FORECASTED` / `GREATER_THAN` / `PERCENTAGE` notification per threshold, one email subscriber. No budget action, no SNS topic, no provider configuration |
| `infra/terraform/envs/staging-core/main.tf`, `variables.tf`, `outputs.tf` | Calls the module with the reviewed decision and the sensitive variable `budget_alert_email`; output `budget` whose precondition stops the plan while the limit is undecided |
| `infra/config/staging-budget.json` | The decision: name `veda-staging-monthly-cost`, `monthly_limit_usd: 25`, `forecast_alert_thresholds_percent: [80, 100]`. **No email address** |
| `infra/terraform/envs/staging-core/tests/core.tftest.hcl`, `tests/fixtures/budget*.json` | 5 new offline Terraform tests (§5) |
| `infra/scripts/check-plan.sh` | Plan guard: budget rules (§3) |
| `.github/workflows/10-infra-plan.yml` | The plan step sets `TF_VAR_budget_alert_email` from `BUDGET_ALERT_EMAIL`, stored on the `staging-plan` environment (B3); a push to `main` that changes the budget decision is planned |
| `infra/Makefile` | tflint and checkov also scan `terraform/modules/*` (checkov does not follow local module calls from a root) |
| `infra/tests/run.sh` | 25 new checks (§5) |
| `docs/operations/staging-infra-workflows.md`, `infra/README.md`, `envs/staging-core/README.md`, `modules/README.md`, `staging-critical-path-plan.md` | Runbook §6 (inputs), status, O16 |

## 2. Design decisions for review

| # | Decision | Why |
|---|---|---|
| B1 | A **cost** budget, **monthly**, in **USD**, with **forecast** alerts only (80%, 100%) | Owner decision O16. See residual risk R1 for what forecast-only alerts do not cover |
| B2 | Email subscriber directly on the budget; **no SNS topic** | The smallest set of resources (one), and no monitoring infrastructure (out of scope; AUT-110 owns SNS) |
| B3 | The recipient is **never committed**. It is the `staging-plan` **environment secret** `BUDGET_ALERT_EMAIL`, passed as `TF_VAR_budget_alert_email`, and a **sensitive** Terraform variable | The repository is public. GitHub prints a step's plain variables (`vars.*`) in the public job log, but masks secrets. The address is not a credential; the secret store is used only for masking. AWS access stays OIDC only. This is the workflows' **only** stored secret, scoped to the reviewer-protected environment and to the plan step |
| B4 | The decided values (name, limit, thresholds) live in a **reviewed JSON file**, not in workflow variables | Every change to the budget is a pull request, and a push to `main` changing it triggers a plan |
| B5 | An **undecided limit stops the plan** (`limit: null` → output precondition, O16 message), and the plan guard refuses a budget without a known USD limit | No invented amount; nothing is planned or applied without the owner's number |
| B6 | Budgets is a **global** service: the resource has no `region` (confirmed in the AWS provider 6.66 schema) | The guard's Mumbai rule accepts a resource without a region as global. `veda-boundary` already lists `budgets:*` among the global actions, and `veda-gh-apply` already has `budgets:*`: **no bootstrap change** |
| B7 | **No budget action**, and the guard refuses `aws_budgets_budget_action` | A budget action applies IAM or SCP policies or stops instances automatically. `veda-gh-apply`'s `budgets:*` would allow creating one; the guard closes that |

## 3. Plan guard (`check-plan.sh`) additions

Refused on create or update:
- any `aws_budgets_budget_action`;
- a budget not named `veda-*`, or whose name is unknown at plan time;
- a budget for another account (`account_id` known and not the approved account);
- a budget on a billing view (`billing_view_arn` set or unknown): a view can span other accounts;
- a budget without a known limit in USD;
- a budget without a notification (it alerts no one);
- a notification to an SNS topic outside the approved account and ap-south-1.

Unchanged: no destroy; Mumbai only for every regional resource; IAM, trust and resource-policy rules.

## 4. Residual risks

| # | Risk | Level | Handling |
|---|---|---|---|
| R1 | **Forecast alerts need billing history.** AWS forecasts only after some weeks of usage, so a new account can overspend before the first forecast alert fires. An actual-spend alert would cover that | Medium (cost) | Owner choice: keep O16 as decided, or add an `ACTUAL` alert at 100% (a one-line change to the decision file and the module) |
| R2 | The saved plan file holds the address (Terraform stores every planned value) | Low | It is uploaded only from a private repository or if N-04-S is `ACCEPTED`. `ACCEPTED` in a public repository would publish the address with the artifact; `PRIVATE_REPOSITORY` avoids it (runbook §6) |
| R3 | After the first apply, the plan role must read the budget on refresh (`budgets:ViewBudget`, `budgets:ListTagsForResource`) through `ReadOnlyAccess` | Low | Proven by the first plan after the apply: "No changes", no AccessDenied (§7, step 6) |
| R4 | Budget email subscribers need no confirmation, so a mistyped address fails silently; delivery also depends on the mailbox (spam filtering) | Low | The owner sets the secret themselves and checks the first alert, or the alert history in the AWS Budgets console |
| R5 | A missing or mistyped secret stops the plan | Accepted (fails closed) | The variable validation names the secret; nothing is planned |

## 5. Tests

**`terraform test` (`envs/staging-core`): 7 passed** (2 from AUT-301, 5 new; the provider is mocked):

| Run | Proves |
|---|---|
| `budget_monthly_cost_with_forecast_alerts` | Name from the decision; limit `50.00` USD (fixture); thresholds exactly 80 and 100 |
| `budget_alerts_are_forecasts_by_email_only` | Exactly two alerts; each `FORECASTED`, `GREATER_THAN`, `PERCENTAGE`, one email address, no SNS topic |
| `budget_with_an_undecided_limit_refused` | `monthly_limit_usd: null` stops the plan (output precondition) |
| `budget_without_a_recipient_refused` | An empty recipient (secret not set) stops the plan |
| `budget_with_two_recipients_refused` | A list of addresses is refused: one recipient only |

**`infra/tests/run.sh`: 465 passed, 0 failed** (440 on `main`; 25 new):
- **Plan guard:** the decided budget passes as a global resource; refused: a budget action, a name outside `veda-*`,
  another account, a billing view, no limit, another currency, no notification, an SNS topic in another account, an
  SNS topic outside Mumbai; the account's own topic in Mumbai passes.
- **Committed decision:** thresholds `[80,100]`; name `veda-*`; limit `25` (O16); no email
  address in the decision, the module or the root.
- **Wiring:** the root calls the module; the recipient variable is sensitive; the module creates no budget action;
  `make check` lints and scans the module.
- **Workflow contract:** the plan step reads the recipient from `secrets.BUDGET_ALERT_EMAIL`; it is the only stored
  secret in either workflow, used once; it never reaches a plain variable; the apply workflow has no secret; a change
  of the budget decision is planned on `main`.

**Mutation check:** each control was removed on its own, in a copy of the repository tree, and the suites re-run
(§6).

## 6. Mutation results

All 13 are detected.

| # | Control removed | Detected by |
|---|---|---|
| M1 | Guard refuses a budget action | 1 check |
| M2 | Guard requires a `veda-*` budget name | 1 check |
| M3 | Guard refuses a budget for another account | 1 check |
| M4 | Guard refuses a billing view | 1 check |
| M5 | Guard requires a known USD limit | 2 checks |
| M6 | Guard refuses a budget without a notification | 1 check |
| M7 | Guard limits SNS subscribers to the account in Mumbai | 2 checks |
| M8 | Recipient from the environment secret (mutated to a plain `vars.` variable) | 3 checks |
| M9 | Recipient variable marked sensitive | 1 check |
| M10 | Forecast alerts (mutated to `ACTUAL`) | 2 Terraform tests |
| M11 | Plan stops while the limit is undecided (output precondition always true) | 1 Terraform test |
| M12 | Recipient validation (always true) | 1 Terraform test |
| M13 | Committed thresholds 80/100 (mutated to 90/100) | 1 check |

## 7. Plan proof expectations

Inputs: the monthly limit (25 USD) is committed in `infra/config/staging-budget.json`, and `BUDGET_ALERT_EMAIL` is set
on the `staging-plan` environment (2026-10-05, at the owner's request; the value is not recorded here). A
`10-infra-plan` run (pull request or `main`) must show:

| Check | Expected |
|---|---|
| OIDC session | `assumed-role/veda-gh-plan/gh-<run>-<attempt>-plan`; confined to ap-south-1 |
| Backend | `s3://veda-tfstate-813238078849/staging/core.tfstate` |
| Plan summary | **`Plan: 1 to add, 0 to change, 0 to destroy.`** |
| The one resource | `module.budget.aws_budgets_budget.this` (create): name `veda-staging-monthly-cost`, `budget_type = "COST"`, `time_unit = "MONTHLY"`, `limit_amount = "25.00"`, `limit_unit = "USD"`, two notifications (`FORECASTED`, `GREATER_THAN`, 80 and 100, `PERCENTAGE`), subscriber shown as `(sensitive value)`, the default tags |
| Plan guard | passes ("no destroy, everything in ap-south-1, …") |
| Plan mode | `nothing was created` |

Fail-closed behaviour (offline tests): a `null` limit fails the plan with the O16 message, and a missing or malformed
recipient fails it with the recipient message. Both create nothing.

**After OD-B7 and N-04-S are decided** (not part of this change), the first apply is:
1. `10-infra-plan` by workflow_dispatch on `main`; review the artifact's plan text; note run ID and plan SHA-256.
2. `11-infra-apply` with that run and digest; approve in `staging-infra`.
3. Expected: `Apply complete! Resources: 1 added, 0 changed, 0 destroyed.`
4. Evidence: CloudTrail `CreateBudget` and the notification calls by `veda-gh-apply` (Budgets is global: look in the
   us-east-1 event history); the budget in the console with its two alerts.
5. This is the **first live proof of artifact digest binding** (left open by AUT-301 §8).
6. A new plan on `main` shows "No changes" (refresh through `veda-gh-plan` works, R3).

## 8. Owner decisions this review needs

| Decision | Options | Needed for |
|---|---|---|
| ~~O16, monthly limit~~ | **Decided 2026-10-05: 25 USD** | — |
| ~~O16, recipient secret~~ | **Set 2026-10-05** on `staging-plan` | — |
| **O16, actual-spend alert** (R1) | Keep forecast-only, or add `ACTUAL` at 100% | Optional; before the first apply |
| **OD-B7** | Close (SCP, RR-C) or accept the `veda-gh-apply` trust-writing gap | The first apply |
| **N-04-S** | `PRIVATE_REPOSITORY` (recommended here, R2) or `ACCEPTED` | The first apply |
