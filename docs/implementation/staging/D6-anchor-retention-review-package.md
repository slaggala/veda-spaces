# D6: configurable anchor retention (review package)

- **Date:** 2026-10-06
- **Decision:** D6 option B ([owner decisions](STAGING-PLATFORM-owner-decisions.md)): the application's anchor
  retention becomes configurable, and staging uses **30 days**.
- **Scope:** D6 only. Nothing here touches AUT-201 to AUT-204, applies Terraform or deploys. `deploy.enabled` stays
  `false` and public intake stays disabled.

## 1. What changes

| Area | Change |
|---|---|
| Setting | `VEDA_ANCHOR_RETENTION_DAYS` (`api/veda/config.py`): a whole number of days, `anchor_retention_days` in `Settings`. Unset means the default, **3650** (`ANCHOR_RETENTION_DEFAULT_DAYS`). A value that is not a whole number (`30d`, `-1`, `1.5`, `3e3`) **refuses to load**, so a typo can never fall back to a default |
| Validation (`validate_environment`) | Every environment: 1 to 36,500 days (S3 Object Lock's ceiling). **Staging:** required (`VEDA_ANCHOR_RETENTION_DAYS is required in staging (D6)`). **Production:** at least **3650** (`ANCHOR_RETENTION_PRODUCTION_MIN_DAYS`); unset is accepted because the default is 3650 |
| Anchor store | `S3AnchorStore.put` and `put_blob` lock each object until `clock.now() + settings().anchor_retention`. The fixed `RETENTION` constant is removed. The local directory store is unchanged |
| Infrastructure | `staging-core` adds `VEDA_ANCHOR_RETENTION_DAYS = tostring(local.platform.anchor_retention.application_retention_days)` to the configuration map: one new plain `String` parameter, `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` = `30`. Not applied |
| Gate | `infra/tests/run.sh` refuses `deploy.enabled: true` unless all of the following hold: the application reads the setting, both S3 writes use it, `staging-core` maps it from the decision, and the planned parameter equals the decision |
| Documentation | Owner-decision record (D6), runbook §0 (gate) and §1 (the `deploy.enabled` apply adds the parameter), runbook §6.3 (secret seeding with the data key), API runbook §10 (the variable) |

## 2. Why each rule

- **COMPLIANCE retention is irreversible.** Nobody, the root user included, can shorten or remove it once an object is
  written.
- **Staging must state its value.** If it were unset, every anchor would silently get the ten-year default.
- **Production can't go below ten years.** The ledger's anchors keep their full retention.
- **A malformed value refuses to load.** It is never read as "unset".
- **The deploy gate holds the order.** No anchor can be written before the configured retention is in place.

## 3. Tests

| Suite | Added or changed | Result |
|---|---|---|
| `api/tests/unit/test_anchor_retention.py` (new) | 29 cases (listed below) | Pass |
| `api/tests/unit/test_config_environments.py` | The shared deployed-environment fixture sets `VEDA_ANCHOR_RETENTION_DAYS=30` for staging, as `staging-core` does | Pass |
| `infra/terraform/envs/staging-core/tests/core.tftest.hcl` | `anchor_retention_parameter_is_the_decision`: the mapped value is `30`, and every configuration value, this one included, is planned under `/veda/staging/config/` | Pass |
| `infra/tests/run.sh` | 7 D6 checks plus the D6 deploy gate. They replace the earlier check, which compared the old `RETENTION` constant | Pass |
| `infra/tests/fixtures/aut107-ssm-plan.json` | Regenerated with the same sandbox plan (local mock, test account) that produced it. Before regenerating, the procedure reproduced the committed fixture byte for byte. The only difference is the new parameter | — |

The 29 cases in `test_anchor_retention.py`:
- default of 3,650 days in local and test;
- staging at 30 days;
- staging refuses an unset value;
- production accepts unset, 3650, 3651 and 36500;
- production refuses 1, 30 and 3649;
- 0 and 36501 refused in test, staging and production;
- seven malformed values refuse to load;
- surrounding whitespace is tolerated;
- the S3 store locks both writes until exactly now + 30, + 3650 (unset) and + 3650 days;
- the store keeps no fixed retention of its own.

**Full runs:**

| Suite | Result |
|---|---|
| API (SQLite) | 716 passed, 0 failed |
| ruff check and format | Clean |
| mypy ratchet | 157 errors, unchanged from the baseline of 157 |
| OpenAPI | Matches the snapshot |
| `make -C infra check` | Format, validate, 107 Terraform tests (106 before, plus the new root test), 767 script checks, tflint, checkov, shellcheck, actionlint: all pass |
| Sandbox plan of `staging-core` | **159 to add, 0 to change, 0 to destroy.** The one addition is the parameter; the plan guard passes |

The PostgreSQL leg runs in CI. The change is independent of the database engine.

**Secret scan.** It found one new candidate: the parameter name `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` in
the regenerated fixture. Its characters fit the base64 pattern, so the scanner flags it as high-entropy, just as the
baseline already records every other parameter name in that file. `.secrets.baseline` was updated with
`detect-secrets scan --baseline`: one entry added, none removed, and the existing entries' line numbers moved. The
scan then reports no new candidates.

## 4. Mutation check

Each mutation was made in a fresh copy of the working tree, then the suite that should notice was run:
- **API:** `pytest` of the D6, configuration and chain-integrity tests;
- **infra:** `infra/tests/run.sh`;
- **Terraform:** `terraform test` of `staging-core`.

**Every D6 control is detected.** The table also includes one control run, which shows the gate isn't simply always
closed.

| # | Control removed | Suite | Detected by |
|---|---|---|---|
| M1 | Staging no longer requires a retention | API | `test_D6_staging_refuses_an_unset_retention` |
| M1s | (same) | infra | `D6 staging refuses an unset retention, production anything below 3650 days` |
| M2 | Production minimum lowered to 30 days | API | `test_D6_production_refuses_less_than_ten_years` (all 3 cases) |
| M2s | (same) | infra | `D6 staging refuses an unset retention, production anything below 3650 days` |
| M3 | Store ignores the setting (fixed ten years) | API | `test_D6_s3_store_locks_each_object_for_the_configured_retention` (all 3 cases) |
| M3s | (same) | infra | `D6 both anchor writes lock for the configured retention`; `D6 the anchor store keeps no fixed retention of its own` |
| M4 | A malformed value silently falls back to the default | API | `test_D6_a_retention_that_is_not_whole_days_refuses_to_load` (all 7 cases) |
| M5 | Range check removed | API | `test_D6_out_of_range_retention_is_reported_in_every_environment` (all 6 cases) |
| M6 | Parameter mapping removed from `staging-core` | Terraform | `anchor_retention_parameter_is_the_decision` (8 passed, 1 failed) |
| M6s | (same) | infra | `D6 staging-core maps the parameter from the decision` |
| M7 | Decision changed to 3650 without re-planning | infra | `committed decision D6`; `D6 the planned parameter is the decided retention` |
| M8 | `deploy.enabled: true` while the store ignores the setting | infra | **`D6 gate: deploy.enabled only once the configured anchor retention is implemented and planned`**, plus the two store checks and the committed `deploy.enabled` check |
| M9 (control) | `deploy.enabled: true` with D6 in place | infra | Only the committed `deploy.enabled` check fails; **the D6 gate passes** |

In a first run, M1s was not detected: the check then matched only the staging message, not its condition. The check
now matches the conditions as well, the D6 gate also requires the staging condition, and M1s is detected.

## 5. What applying it will do (not done here)

1. **The `deploy.enabled` plan** adds `/veda/staging/config/VEDA_ANCHOR_RETENTION_DAYS` = `30` and turns on the
   deployment alarm actions (review R4), with 0 destroy (runbook §1 step 2).
2. **On the host,** `render-env.sh` copies the parameter into `/etc/veda/api.env`. The API then locks every anchor
   for 30 days.
3. **If the parameter were missing,** the API would refuse to start in staging rather than lock for ten years.
