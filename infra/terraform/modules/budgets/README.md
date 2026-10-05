# modules/budgets (AUT-112)

One monthly **cost** budget for the staging account, with **forecast** email alerts at the owner's thresholds
(owner decision O16: 80% and 100%). Called from `envs/staging-core`; never applied on its own.

| Input | Source |
|---|---|
| `name`, `monthly_limit_usd`, `forecast_alert_thresholds_percent` | `infra/config/staging-budget.json` (reviewed pull request) |
| `alert_email` | Secret `BUDGET_ALERT_EMAIL` of the `staging-plan` environment, as `TF_VAR_budget_alert_email`. Never committed: the repository is public, and GitHub prints plain variables in the job log |

- Budgets is a global service: the resource has no region. `veda-boundary` lists `budgets:*` among the global actions;
  `veda-gh-apply` has `budgets:*`.
- No budget action (`aws_budgets_budget_action`): the plan guard refuses one. The budget only alerts.
- Forecast alerts need some billing history. AWS usually starts forecasting after a few weeks of usage, so a new account
  can overspend before the first forecast alert. An actual-spend alert would cover that; it is an owner choice (O16).
