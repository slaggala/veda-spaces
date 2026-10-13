# MTQ B1-T12 — protected-staging enablement and ten-site validation

**Status: PREPARED. Site measurement is OFF on staging and refused in production.** Enablement needs owner actions that this implementation cannot take: the independent review and merge of pull request #87, the attachment-storage plan and apply (B1-T11), a deploy, migration and rollback verification, and the owner's APPROVED enablement record. Nothing below has been run against staging by the implementation session.

**Validation status on 2026-10-13:**

| Track | Label | Evidence |
|---|---|---|
| Synthetic ten-site run through the real API | **SYNTHETIC_VALIDATED** | [evidence/ten-site-synthetic-2026-10-13.json](evidence/ten-site-synthetic-2026-10-13.json), produced by `tests/integration/test_mtq_ten_site.py` on SQLite and PostgreSQL with identical verdicts |
| Live ten-site validation on protected staging | **UNVALIDATED_NO_REFERENCE** | [evidence/ten-site-live-2026-10-13.json](evidence/ten-site-live-2026-10-13.json): no site has been surveyed, no reference measurement exists |
| Historical replay (closure §5) | 3 BHK references only; 2, 4, 5 BHK and independent house **UNVALIDATED_NO_HISTORICAL_REFERENCE** | [replay-reference-manifest.json](../../proposals/measurement-to-quotation/replay/replay-reference-manifest.json) |

SYNTHETIC_VALIDATED proves the capture pipeline and the validation rules end to end. It says nothing about field accuracy, and it is never reported as a live result.

## 1. The gate

The flag `VEDA_MTQ_SITE_ENABLED` can turn on in staging only when every layer agrees:

| Layer | Refuses |
|---|---|
| staging-core (`output "mtq_attachments"`) | `mtq_site.site_enabled` true unless the scanner is clamd and `infra/config/mtq-site-enablement-record.json` is APPROVED, staging-only, approved by someone other than its author, dated, with every evidence field filled (run ids numeric), and `mtq_site.enablement_record_sha256` equals the file's SHA-256. A digest without the flag is refused too |
| Host preflight (`infra/host/attachment-preflight.sh`) | A rendered flag-on environment without every attachment setting, without `s3`, without clamd, or without a 64-hex `VEDA_MTQ_SITE_ENABLEMENT_SHA256` |
| API start (`veda/config.py`) | In staging, flag on without the bucket, the data key, clamd and the 64-hex enablement digest. In production, the flag at all |
| Routes | Every site and attachment route answers 404 before authentication while the flag is off |

The committed record is a DRAFT template. The owner fills it; nobody fills it on the owner's behalf.

## 2. Owner sequence

Each step uses the existing workflows and their environment approvals. The expected result is stated so a different result stops the sequence.

1. **Review and merge pull request #87.** An independent reviewer certifies it. CI is green on the merged commit.
2. **Plan attachment storage.** `10-infra-plan` by `workflow_dispatch` on `main`; approve `staging-plan`. Expect 20 to add, 4 to change, 0 to destroy, as the pull-request plan 38352456157 showed: the attachment storage, eight parameters, the dashboard update, and the owner's alarm subscription that is missing from AWS ([B1-T11 §3.1](B1-T11-attachment-storage.md)). Any other difference stops the sequence.
3. **Apply.** `11-infra-apply` with that plan run and its SHA-256; approve `staging-infra`. Then a drift run with no changes.
4. **Deploy with the flag off.** `12-deploy` on `main`; approve `staging`. `deploy.sh` takes the snapshot, runs the expand-only migrations 0106 and 0200, and passes readiness. The preflight prints `site measurement: intentionally disabled`.
5. **Production-isolation check.** `GET https://api-staging.vedaspaces.com/api/v1/properties` answers 404 through Cloudflare Access. The workspace page `/site` shows "Site measurement is not enabled here."
6. **Migration verification.** The deploy log shows the migration to `0200_mtq_site` and `/health/ready` reports the expected migrations state. The run id goes into `evidence.migration_verification_run_id`.
7. **Rollback verification.** `deploy.sh --rollback <n-1-tag>` through an owner Session Manager session, as in [staging-platform-runbooks §1](../../operations/staging-platform-runbooks.md). The N-1 image runs on the migrated schema; readiness passes. Redeploy the merged commit afterwards. The run or session reference goes into `evidence.rollback_verification_run_id`.
8. **Approve enablement.** The owner fills `infra/config/mtq-site-enablement-record.json`: `status` APPROVED, `approved_by`, `approved_on`, and the six evidence fields. A reviewed pull request also sets `mtq_site.site_enabled` true and `mtq_site.enablement_record_sha256` to the record file's SHA-256 in `infra/config/staging-platform.json`.
9. **Plan, apply, deploy.** Expect exactly two in-place parameter changes: `VEDA_MTQ_SITE_ENABLED` and `VEDA_MTQ_SITE_ENABLEMENT_SHA256`. The deploy preflight prints `site measurement: ENABLED ...`.
10. **Smoke checks** (§3), then **live ten-site validation** (§4).

## 3. Smoke checks after enablement

| # | Check | Pass |
|---|---|---|
| M1 | A Surveyor signs in through Cloudflare Access and opens Site visits | The visit list loads; no public route exists |
| M2 | Create a property from a template, schedule and start a visit, open a set | 201 at each step; audit rows present |
| M3 | Capture a room in airplane mode, then reconnect | The queue shows the write pending, then synced; no duplicate on retry |
| M4 | Upload a photo | The POST goes to the attachments bucket origin; completion answers RECEIVED; scan CLEAN; variants served by the API only |
| M5 | Upload the EICAR test file renamed `.jpg` | Refused as an image or quarantined INFECTED; `attachment-infected` alarm if it reached the scanner |
| M6 | Submit, then verify as the capturing surveyor | 422 FOUR_EYES_REQUIRED |
| M7 | Verify as a second staff user | VERIFIED with a snapshot digest |
| M8 | Any page or API answer | No rate, amount or currency |

## 4. Live ten-site validation

**Sites:** five apartments covering 2, 3 and 4 BHK, and five independent houses. At least one 5 BHK is required in the dataset; the synthetic run covers it (S10). A live 5 BHK is included only if a real one is available, and its absence is recorded, never filled in.

**Each site:** the app survey by one surveyor, and an independent reference measurement by a second surveyor with a different instrument (tape against laser). At least one site uses Lite and at least one Full. At least one site has a second surveyor conflict, and at least one an offline retry, both observed and recorded.

**Evaluation:**

```
.venv/bin/python tools/mtq_ten_site.py --reference ref.json --measured measured.json --events events.json --out evidence.json
```

`ref.json` holds anonymous site ids S01 to S10 and the reference readings; it is owner data and stays private. `measured.json` holds each site's verified set and property, exported from staging by a staff user. The tool writes only dimensions and verdicts. It exits 0 only for LIVE_VALIDATED.

**Rules** (closure §2.2, as code in `veda/modules/mtq/tolerance.py`): per site, at least 95 % of walls PASS, no wall FAIL, every space area within tolerance, property total within 1 %. Gate: at least nine of ten sites PASS, and no two failures share a root cause. Fewer than ten referenced sites is UNVALIDATED_NO_REFERENCE, never a pass.

## 5. Rollback

- **Flag off:** a reviewed change sets `site_enabled` false and `enablement_record_sha256` null; plan and apply change the two parameters in place; the next deploy renders them. Every route answers 404 again. Data stays in the database and the bucket, unreadable through the API.
- **Image:** `deploy.sh --rollback <n-1-tag>`. The migrations are expand-only, so the N-1 image runs on the new schema with the new tables unused.
- **Storage:** see [B1-T11 §6](B1-T11-attachment-storage.md).

## 6. The synthetic run

[`synthetic-2026.10.json`](../../../api/tests/fixtures/mtq_ten_site/synthetic-2026.10.json) defines ten sites. The harness creates a lead and a property from the template for each, schedules and starts visits, and captures every in-scope space through the offline sync endpoint. It adds photos (overview, and furniture walls for Full), submits, and verifies as a second user. Readings are the reference plus a fixed error of at most 5 mm. Two sites plant deviations on purpose:

| Site | Configuration | Survey | What it exercises | Verdict |
|---|---|---|---|---|
| S01 | 2 BHK apartment | Lite | baseline | PASS |
| S02 | 2 BHK apartment | Full | every Full rule, photos, electrical points | PASS |
| S03 | 3 BHK apartment | Lite | offline retry: the whole queue resent, every write DUPLICATE | PASS |
| S04 | 3 BHK apartment | Lite | one wall 40 mm off with a recorded cause | PASS (1 EXPLAINED) |
| S05 | 4 BHK apartment | Lite | second surveyor conflict: CONFLICT on `length_mm`, never last-write-wins | PASS |
| S06 | Independent house, 3 BHK | Lite | baseline | PASS |
| S07 | Independent house, 3 BHK | Lite | one wall 130 mm off, root cause recorded | FAIL |
| S08 | Independent house, 3 BHK | Full | staircase geometry, terrace wall heights | PASS |
| S09 | Independent house, 3 BHK | Lite | offline retry | PASS |
| S10 | Independent house, 5 BHK | Lite | two bedrooms added to the template | PASS |

Gate: nine of ten PASS, one isolated failure. Label: SYNTHETIC_VALIDATED.
