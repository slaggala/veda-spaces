# Veda Spaces API runbooks (P0)

Procedures for the single-host SQLite deployment (ADR-008, 02 §12.4, 11 §8). They implement the certified design;
none has been rehearsed yet. RG-1, RG-2, RG-5 and RG-7 in the [gate registry](../architecture/gate-registry.md)
remain open until each procedure is executed on the real host with evidence.

Host layout: `/etc/veda/api.env` (environment, secrets from SSM), `/var/lib/veda` (encrypted EBS volume: `veda.db`,
WAL, `snapshots/`, `veda.db.api.lock`), the repository's `api/deploy/` directory (compose file, `litestream.yml`,
`deploy.sh`).

## 1. Deploy and migrate (02 §12.4)

1. **Pre-flight.**
   - CI is green for the commit, including the PostgreSQL 16 leg and the migration upgrade-with-data test.
   - Litestream lag is within the alert threshold (`litestream_*` metrics on `127.0.0.1:9090`).
2. `cd api/deploy && ./deploy.sh <image-tag>`. The script runs, in order:
   - `veda deploy-check`: the effective gunicorn configuration is one gthread worker;
   - a snapshot, whose manifest it saves next to the script;
   - stop worker and scheduler;
   - `veda migrate`, which re-validates the configuration and is expand-only;
   - start the API on the new image;
   - wait for `/health/ready`;
   - restart worker and scheduler.
3. **If readiness fails,** the script stops with worker and scheduler still paused. Continue with §2.

Every migration is expand-only and compatible with release N-1. A contract step (drop, NOT NULL tightening, rename)
ships only after the N-1 window. No down-migration exists: `alembic downgrade` is refused (`NotImplementedError`),
and the schema stays where it is.

## 2. Normal rollback: N-1 image on the migrated schema

1. Read the database revision: `sqlite3 /var/lib/veda/veda.db "select version_num from alembic_version"`.
2. Declare that revision compatible for the N-1 image: add `VEDA_SCHEMA_AHEAD_ACCEPTED=<revision>` to `/etc/veda/api.env`.
   - Readiness of an image that does not know the revision is `ahead_undeclared` (not ready) until this is set (AM-6).
   - Readiness when the database is *behind* the image is never accepted.
3. Run `./deploy.sh --rollback <n-1-tag>`. No migration runs; the API must pass `/health/ready` with `migrations: ahead`.
4. Remove `VEDA_SCHEMA_AHEAD_ACCEPTED` after the next forward deploy.

## 3. Disaster rollback: restore a snapshot

Use this only when a migration or a defect corrupted data.

1. **Maintenance mode.**
   - Stop the API: `docker compose stop api worker scheduler`.
   - The website's WhatsApp fallback carries enquiries in the meantime.
2. **Choose the restore point.** Use the pre-deploy snapshot from §1 step 2, or the Litestream generation recorded at that time.
3. **Restore.**
   - From Litestream: `litestream restore -o /var/lib/veda/veda.db.restore -timestamp <UTC> /var/lib/veda/veda.db`.
   - From a snapshot: copy `snapshots/veda-<stamp>.db` and check its SHA-256 against the `.json` manifest.
4. **Verify.** Run `VEDA_SNAPSHOT_DIR=<dir with the restored file> veda maintenance restore-verify`. It checks:
   - `integrity_check` and `foreign_key_check`;
   - schema revision and conformance;
   - the security-event chain.
5. **Swap.** Replace `veda.db` (keep the old file), remove the `-wal`/`-shm` files, deploy the N-1 image (§2) and start everything.
6. **Report the lost window.** It runs from the restore point to the stop time; derive it from `audit_log.performed_on` and the security events. Staff re-enter the WhatsApp enquiries received meanwhile.

## 4. Backups and restore verification (OPS-002, OPS-009)

| Job | Schedule (scheduler, IST) | What it proves |
|---|---|---|
| Litestream `replicate` | continuous | WAL shipped to S3 within the owner-approved RPO (OWNER-INPUT-001) |
| `veda maintenance snapshot` | 01:30 daily | `VACUUM INTO` copy + SHA-256 manifest; uploaded with Object Lock when `VEDA_SNAPSHOT_BUCKET` is set; `VEDA_SNAPSHOT_KEEP` local copies |
| `veda maintenance restore-verify` | 05:00 daily | the newest snapshot restores and passes integrity, FK, revision, conformance and chain checks (`RestoreVerified` metric) |
| `veda maintenance disk-usage` | every 5 min | `DiskUsed` percent of the database volume |

## 5. Security-event chain (05 §9.6)

| Job | Schedule | Behaviour |
|---|---|---|
| `veda maintenance anchor-chain` | 03:00 daily | Writes the chain head to the anchor store (S3 Object Lock in production, write-only role). A failure is CRITICAL (`ChainAnchorFailed`). |
| `veda maintenance verify-chain` | 02:30 daily | Recomputes the online chain against the latest anchor and every archive manifest in the store (read-only role). Detects modification, gaps, removal of the oldest rows, truncation below the anchor and a missing anchored row (`ChainVerificationFailed`, `SECURITY_LOG_CHAIN_BROKEN`). |
| `veda maintenance archive-security-events` | monthly, once OWNER-INPUT-002 sets retention | Exports the contiguous prefix older than retention, records its manifest in the store, deletes exactly that range. |

**When verification fails:**
1. Treat it as an incident (§8).
2. Preserve the database file and the anchor-store objects.
3. Compare the failing sequence with the last anchor.
4. Do not re-anchor until the cause is understood.

## 6. Key rotation (SEC-005)

| Key | Rotation |
|---|---|
| JWT ES256 (`VEDA_JWT_PRIVATE_KEY_PEM`, `VEDA_JWT_KID`) | New key and kid; move the old public key to `VEDA_JWT_PREVIOUS_PUBLIC_KEY_PEM`/`_KID` for one access-token lifetime (15 min), then remove it. |
| Chain key (`VEDA_CHAIN_KEY`, `VEDA_CHAIN_KEY_LABEL`) | New label and key. List the old one in `VEDA_CHAIN_KEYS_RETIRED` (`label:base64`) for as long as rows signed with it stay online. Then anchor. |
| Action-token key (`VEDA_ACTION_TOKEN_KEY`) | Rotation invalidates every open emailed link (AM-8), so announce it. |
| Recovery-code and email-hash HMAC keys | Rotation invalidates every stored recovery code, or the unknown-email throttle keys. Re-issue codes (a Founder decision). |
| KMS key (`VEDA_KMS_KEY_ARN`) | Use KMS automatic rotation. Wrapped data keys stay decryptable. |

All keys are at least 32 random bytes, base64. Staging and production refuse anything shorter (IR-09).

## 7. Break-glass (06 §7.5)

1. **Custodian session.** A custodian starts an SSM session to the host with their own IAM role.
   - The CLI reads the caller's identity from STS; `--principal-arn` is only an assertion that must match it.
   - Two different humans are required (IR-06).
2. **Request.**
   - Run `veda break-glass request --target <user-id> --founder-action GRANT_FOUNDER --reason "…"`.
   - It is refused while any eligible Founder other than the target exists (IR-05).
3. **Notification.**
   - Every active Founder and the target are emailed a cancel link.
   - The link opens `/approvals/cancel`, where one click cancels the request (IR-07).
4. **Approval.** A second custodian, in their own SSM session, runs `veda break-glass approve --request <id>`.
5. **Execution.** It runs automatically after `not_before` (24 h), unless the request was cancelled or an eligible Founder has reappeared meanwhile.

Break-glass stays unusable until OWNER-INPUT-004 names the custodians (`VEDA_BREAK_GLASS_CUSTODIANS`).

## 8. Incident response

| Signal | First actions |
|---|---|
| `SECURITY_LOG_CHAIN_BROKEN` / `ChainVerificationFailed` | §5; freeze the host; snapshot the volume. |
| `GovernanceInvariantFailures > 0` | Run `veda maintenance invariants` and read the problems. Founder state may need the Founder workflow; never edit rows directly. |
| `REFRESH_REUSE_DETECTED`, MFA guessing, credential stuffing (05 §9.8) | Check the security events for the subject. Revoke sessions (`POST /users/{id}/sessions/revoke`). Consider an MFA reset through dual control. |
| `OutboxDead > 0` | Read `last_error` on the dead events. Fix the cause (SES, templates), then re-queue (set `status=PENDING`, `attempts=0` through a maintenance session). Delivered messages are not re-sent (IR-30). |
| 5xx rate, readiness failing | Check the API logs by `request_id`; exceptions carry `error_type`, `error_fingerprint` and `stack` only. Roll back per §2. |

## 9. Metrics and alerts (LOG-006, 02 §9)

The application writes CloudWatch Embedded Metric Format lines (namespace `Veda/API`); the CloudWatch agent on the host
turns them into metrics. Configure these alarms in the deployment account. They route to the owner's SNS topic (email
and SMS) and are test-fired once each (RG-5).

| Metric (dimensions) | Alarm |
|---|---|
| `Requests`, `Latency` (Route, StatusClass) | 5xx share above threshold over 5 min; p95 latency above NFR-001 over 10 min |
| `SecurityEvents` (EventType, Outcome) | the 05 §9.8 rules (e.g. `REFRESH_REUSE_DETECTED` ≥ 1; `LOGIN`/FAILURE spikes; `MFA_CHALLENGE`/FAILURE spikes) |
| `SecurityEventWriterFailures` | ≥ 1 |
| `ChainVerificationFailed`, `ChainAnchorFailed` | ≥ 1 |
| `GovernanceInvariantFailures` / `NoEffectiveRecoveryAdmin` | ≥ 1 (CRITICAL / High) |
| `OutboxDead` / `OutboxOldestAge` | any dead event / age above threshold (degraded, never readiness) |
| `SnapshotCompleted` / `RestoreVerified` | missing for 26 h / value 0 |
| `DiskUsed` | > 80 % |
| Litestream lag (Prometheus `:9090`) | above the owner-approved RPO |
| `/health/ready` (external check) | failing twice in a row |

Sentry (`VEDA_SENTRY_DSN`, required in production) receives exceptions with values, request bodies, cookies and local
variables removed.

## 10. Environment added by the remediation

| Variable | Purpose |
|---|---|
| `VEDA_ENV` | Required: `local`, `test`, `staging` or `production`. Anything else refuses to start. |
| `VEDA_TRUSTED_PROXY_CIDRS` | Peers whose `CF-Connecting-IP` is believed (the tunnel or the Docker bridge in front of the API). Required in staging and production. |
| `VEDA_SCHEMA_AHEAD_ACCEPTED` | Revisions newer than the image that the operator declares compatible (§2). |
| `VEDA_BREAK_GLASS_IDENTITY` | `sts` (required in staging and production) or `asserted` (local/test only). |
| `VEDA_SNAPSHOT_DIR`, `VEDA_SNAPSHOT_BUCKET` (required in production), `VEDA_SNAPSHOT_KEEP`, `VEDA_SNAPSHOT_LOCK_DAYS` | §4 |
| `LITESTREAM_BUCKET`, `LITESTREAM_REGION`, `LITESTREAM_RETENTION` | `deploy/litestream.yml` |
