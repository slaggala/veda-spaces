# Budgetary Estimate: staging validation plan

**Purpose:** validate the estimator end to end on staging, **behind Cloudflare Access**, before any decision about
public use.

**Not in scope (stays disabled):**
- public intake (ADR-011 E7);
- public, anonymous use of the estimator;
- any production change. Production refuses `VEDA_ESTIMATOR_ENABLED`.

**Owner:** the repository owner. Steps marked **[owner]** need the owner's AWS or Cloudflare access, or the private
rate card.

## 1. Preconditions (all must hold before step 1)

| # | Precondition | Check |
|---|---|---|
| P1 | PR #47 merged after the owner's sign-off, CI green on `main` | GitHub checks on the merge commit |
| P2 | `12-deploy` has run that commit on staging; migration head `0101_estimator` | `12-deploy` log; `/health/ready` is healthy |
| P3 | Cloudflare Access protects `staging.vedaspaces.com`, `app.staging…` and `api.staging…` (unchanged) | An anonymous request gets `302` to Access |
| P4 | The private card `ESS-2026-10-PRIVATE-DRAFT-4` is saved by the owner outside the repository | The owner has the file and its SHA-256 |
| P5 | The SES sandbox recipients used for the test are verified | SES console |

**Private card `ESS-2026-10-PRIVATE-DRAFT-4`:**
- **Scope:** Essential only, 3 BHK apartments only, 18 products, the six-component package, allowance 5–15 %,
  validity 30 days.
- **Typical sizes:** the 3 BHK medians.
- **Rates:** from the Veda Spaces quotation workbooks. **It is never committed.**

## 2. Steps

| # | Step | Who | How |
|---|---|---|---|
| 1 | **Enable the API flag on staging only** | PR author, then **[owner]** approves the apply | A separate, reviewed infra PR adds `VEDA_ESTIMATOR_ENABLED = "true"` (and `VEDA_WARRANTY_POLICY_URL` once the policy page exists) to `local.app_config` in `infra/terraform/envs/staging-core/main.tf`. Then `10-infra-plan`, **[owner]** approval, `11-infra-apply`, then `12-deploy` (the host re-reads SSM) |
| 2 | **Validate the card** | **[owner]** | On the host, as in runbook §6.8: `veda estimator validate-card <file>` prints the version and SHA-256 only. It must show `ESS-2026-10-PRIVATE-DRAFT-4` and refuse nothing |
| 3 | **Load and activate the card** | **[owner]** | `veda estimator load-card`, then `activate-card --version ESS-2026-10-PRIVATE-DRAFT-4 --approval "<owner approval, date>"`. Delete the file from the host afterwards. `list-cards` shows it ACTIVE |
| 4 | **Switch the staging site on** | **[owner]** | In the Pages project `veda-staging-site` set `STAGING_ESTIMATOR=on`, `STAGING_ESTIMATOR_PACKAGES=ESSENTIAL`, `STAGING_ESTIMATOR_HOME_SIZES=3BHK` and `STAGING_ESTIMATOR_PROPERTY_TYPES=APARTMENT`, then retry the deployment |
| 5 | **Run the test cases (§3)** | **[owner]**, signed in through Access | Desktop browser plus a phone at about 360 px |
| 6 | **Capture evidence** | **[owner]** | `13-evidence` with label `estimator-staging`; screenshots of the cases in §3 |
| 7 | **Decide** | **[owner]** | Pass: record the result and keep the estimator on staging. Fail: roll back (§5) |

## 3. Test cases and pass criteria

| ID | Case | Pass criterion |
|---|---|---|
| V1 | Open `/estimate` | Only **3 BHK** and **Apartment** are offered, with the scope note. No 1/2/4 BHK, Custom or Villa |
| V2 | Quotation-A-like home: kitchen, three bedrooms with wardrobes, living TV unit, false ceiling, profile lighting, a pooja unit, measurements entered | The estimate shows: <ul><li>the title and disclaimer;</li><li>a range, with GST separate;</li><li>room subtotals rounded to ₹1,000;</li><li>the **Project Preparation & Protection Package** as one value with six inclusions and no hardware;</li><li>the **Custom Features Allowance** as its own range;</li><li>the timeline and warranty summary;</li><li>validity 30 days.</li></ul> No rate, line or quantity is visible |
| V3 | The same with "Use a typical size" everywhere | Each assumed size is listed, and the range is wider than in V2 |
| V4 | **Calibration spot check** | For each of the private quotations A, B and C, entered as in E6: the actual pre-GST total lies inside the range, and the base is within ±10 %. Expected: +4.6 %, −3.8 %, −0.5 % |
| V5 | Premium | Shown as "pricing coming soon" and cannot be chosen |
| V6 | Luxury | No price. "Request a design consultation" goes to the enquiry, and the confirmation has no estimate reference. The lead shows "Luxury design consultation requested", and so does the notification |
| V7 | "Get my detailed quotation" after V2 | A customer reference only. The lead shows the Budgetary Estimate panel. The notification carries the estimate summary |
| V8 | Staff panel on the V7 lead | Every line with its rate. Soft-close lines in the kitchen, wardrobe and TV unit. The package components. The allowance band, basis and midpoint. Duplicate, revise (change a typical area), consultation copy, site measurement and quotation process all work; a failed revision shows its error |
| V9 | Refusals | <ul><li>A forged Turnstile token gets `422`;</li><li>a Luxury estimate request to the API gets `422 PACKAGE_UNAVAILABLE`;</li><li>a Villa or 2 BHK request gets `422`;</li><li>anonymous requests get `302` to Access</li></ul> |
| V10 | Accessibility and mobile | Keyboard-only run of V2 and V6. Focus moves to each step heading and to the confirmation. No horizontal scroll at 360 px |
| V11 | Retention and expiry (time-boxed) | `veda estimator list-cards` is unchanged. The daily `estimate-retention` job runs without error. Expiry is covered by CI tests; no clock change on staging |
| V12 | Production untouched | No production resource changed. The production site's `/estimate` shows "coming soon" |

## 4. Stop conditions

Stop and roll back (§5) at once if:
- a public, unauthenticated request reaches the estimator;
- a customer view shows a rate, line, quantity or package component;
- a Luxury price is shown;
- an unsupported size or type is offered;
- an enquiry is lost or rejected because of its estimate;
- any secret or private rate appears in logs or evidence.

## 5. Rollback

1. **Site:** set `STAGING_ESTIMATOR` to empty in Pages and retry. The page shows "coming soon".
2. **API:** a reviewed infra change sets `VEDA_ESTIMATOR_ENABLED = "false"` (or removes it), then apply and
   `12-deploy`. Both public endpoints answer `404`.
3. **Card:** `veda estimator rollback-card --approval "<reason>"`. With no previous card, the estimator answers
   `503 ESTIMATOR_UNAVAILABLE`.
4. **Data:** none to undo. Estimates hold no personal data, and unlinked ones are removed after 90 days.

## 6. Exit: what a pass enables

A pass records that the estimator works on staging behind Access. It does **not** enable public use. That still needs:
- E7, the ADR-011 intake hostname with an edge rate limit (review S4);
- the U7 accessibility follow-up;
- approved data for any further home size or property type;
- a fourth, independent historical quotation;
- the owner's explicit enablement, recorded as a decision.
