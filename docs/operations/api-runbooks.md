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
3. **If readiness fails,** the script stops with worker and scheduler still paused. Decide between forward fix and rollback with §2.

Every migration is expand-only and compatible with release N-1. A contract step (drop, NOT NULL tightening, rename)
ships only after the N-1 window. No down-migration exists: `alembic downgrade` is refused (`NotImplementedError`),
and the schema stays where it is.

## 2. Rollback (RR-17; proposed amendments AM-6, AM-11)

### 2.1 Rollback boundary

- Every release declares a **rollback floor**: the oldest schema revision that a rollback target image must know.
  `deploy.sh` holds it as `ROLLBACK_FLOOR` and refuses any target image that does not know it.
- **This release's floor is `0009_mfa_challenge_binding`.** The previous image (commit `9236aa3`) does not know it:
  it cannot pass readiness on the migrated schema, and it would reintroduce IR-01 (a BLOCKER). **Rollback to
  `9236aa3` is prohibited.** Until a later release exists, there is no valid N-1 image for this release.
- Raise the floor whenever a release ships a security fix that must not be undone. Never lower it.

### 2.2 When a forward fix is required

Use a forward fix (a new image built from a corrected commit, deployed with §1) when any of these holds:

- there is no image at or above the rollback floor other than the failing one (the case for this release);
- the defect is in a migration that already ran (every migration is expand-only; no down-migration exists);
- the defect is a security issue that the N-1 image also has.

Use a snapshot restore (§3) only when data was corrupted or lost. It is always followed by a forward-fixed image,
never by an image below the floor.

### 2.3 Normal rollback to an image at or above the floor

Preconditions (database compatibility):

- The target image knows the rollback floor.
- The schema changes since the target image are expand-only. They are, by policy (02 §12.4); check the release notes.

Steps:

1. **Maintenance mode is not needed.** The API keeps serving until the swap. `deploy.sh` pauses the worker and scheduler.
2. **Read the database revision inside the container of the target image:**
   `VEDA_IMAGE_TAG=<n-1-tag> docker compose run --rm --no-deps api python -m veda.cli schema-status`.
   - The host cannot see readiness details: through the Docker bridge the peer is not loopback.
   - The output is `{current, image_head, state}`.
3. **If `state` is `ahead_undeclared`,** declare the revision compatible: add
   `VEDA_SCHEMA_AHEAD_ACCEPTED=<current>` to `/etc/veda/api.env`. `deploy.sh` checks the declared value, not just
   that the variable is present.
4. **Run `./deploy.sh --rollback <n-1-tag>`.** It:
   - takes the pre-deploy snapshot, which is the backup/restore dependency;
   - refuses a target below the floor;
   - runs no migration;
   - waits for readiness, read inside the container, with `migrations: ahead` (or `head`).
5. **Post-rollback validation.** All of these must pass:
   - readiness `ok` with the expected migrations state;
   - `veda maintenance verify-chain` exits 0;
   - `veda maintenance invariants` reports i1, i2 and i3 true;
   - a sign-in with MFA works;
   - the outbox drains (`outbox_dead` is 0);
   - the scheduler emits `ScheduledJobFailed = 0` for the next frequent-job cycle.
6. **Remove `VEDA_SCHEMA_AHEAD_ACCEPTED`** after the next forward deploy.

Evidence to record: the `schema-status` output, the `deploy.sh` transcript, the readiness body, and the post-rollback checks.

- **Owner category:** Operations. The decision to roll back rather than forward-fix is the Architecture Owner's for any security-relevant defect.
- **Status:** this procedure has not been rehearsed (RG-7 open).

## 3. Disaster rollback: restore a snapshot

Use this only when a migration or a defect corrupted data. **The restored database must then be served by a fixed
image at or above the rollback floor. For this release that means a forward-fixed image, never `9236aa3`.**

1. **Maintenance mode.**
   - Stop the API: `docker compose stop api worker scheduler`.
   - The website's WhatsApp fallback carries enquiries in the meantime. The public intake API is not enabled in P0.
2. **Choose the restore point.** Use the pre-deploy snapshot recorded by `deploy.sh` (§1 step 2), or the Litestream
   generation recorded at that time. Snapshots live in `VEDA_SNAPSHOT_DIR` on the persistent volume; staging and
   production refuse to start otherwise (RR-14).
3. **Restore.**
   - From Litestream: `litestream restore -o /var/lib/veda/veda.db.restore -timestamp <UTC> /var/lib/veda/veda.db`.
   - From a snapshot: copy `snapshots/veda-<stamp>.db` and check its SHA-256 against the `.json` manifest.
4. **Verify.** Run `VEDA_SNAPSHOT_DIR=<dir with the restored file> veda maintenance restore-verify`. It checks:
   - `integrity_check` and `foreign_key_check`;
   - schema revision and conformance;
   - the security-event chain.

   Known gaps are tracked as RR-15, a staging blocker: restore-verify of a Litestream-restored file,
   stopping Litestream before the swap, and verifying the off-host replica.
5. **Swap.**
   - Replace `veda.db`, keeping the old file.
   - Remove the `-wal` and `-shm` files.
   - Deploy the fixed image with §1.
   - Start everything.
6. **Post-restore validation.** Run the checks of §2.3 step 5.
7. **Report the lost window.** It runs from the restore point to the stop time. Derive it from `audit_log.performed_on` and the security events.

- **Owner category:** Operations with the Architecture Owner.
- **Evidence:** the snapshot manifest, the restore-verify output, the validation checks, and the lost-window report.
- **Status:** not rehearsed (RG-1, RG-2 and RG-7 open).

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
| `veda maintenance verify-chain` | 02:30 daily | Recomputes the online chain against the latest anchor and every *finalised* archive manifest (read-only role). Each manifest must be contiguous from sequence 1, match its write-once export (SHA-256, count, range, recomputed row hashes chained from the previous segment to `last_row_hash`), and be announced by its `SECURITY_LOG_ARCHIVED` event (RR-05). Detects modification, gaps, removal of the oldest rows, truncation below the anchor, a missing anchored row, a forged or altered manifest or export, a committed archive that was never finalised, and an unreadable anchor store (`ChainVerificationFailed`, `SECURITY_LOG_CHAIN_BROKEN`). |
| `veda maintenance archive-security-events` | monthly, once OWNER-INPUT-002 sets retention | Order (RR-06): export + *pending* manifest to write-once storage → one DB transaction appends `SECURITY_LOG_ARCHIVED` and deletes exactly that range → *archive* manifest. A failure before the commit leaves the rows online (the pending manifest is ignored); a failure after it shows as `archive not finalised` until the next run finalises it. Retries are idempotent. `SecurityLogArchivedRows`, `SecurityLogArchiveFailed`. |

Writer and verifier roles: in staging and production the anchor bucket must grant the application host `PutObject`
only and the verifier `GetObject`/`ListBucket` only, with Object Lock in COMPLIANCE mode. **Object Lock behaviour has
not been verified against real S3**: the tests use a stub client. Staging evidence is required (RR-A13, SEVT-007).

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

All keys are at least 32 random bytes, base64. Staging and production refuse anything shorter (IR-09). They also refuse constant or two-symbol fillers, the development-derived keys, the same bytes used for two keys, and a signing key that is not an unencrypted P-256 private key (RR-10).

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
| `ChainVerificationFailed`, `ChainAnchorFailed`, `SecurityLogArchiveFailed` | ≥ 1 |
| `MaintenanceJobFailed` (Job), `ScheduledJobFailed` (Job) | ≥ 1 for any job; missing data for 26 h (the scheduler stopped). CLI, worker and scheduler processes configure the same JSON logging as the API (RR-07). |
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
| `VEDA_TRUSTED_PROXY_CIDRS` | Peers whose `CF-Connecting-IP` is believed (the tunnel or the Docker bridge gateway in front of the API). Required in staging and production; each entry at most /24 (IPv4) or /64 (IPv6) (RR-10). |
| `VEDA_SCHEMA_AHEAD_ACCEPTED` | Revisions newer than the image that the operator declares compatible (§2). |
| `VEDA_BREAK_GLASS_IDENTITY` | `sts` (required in staging and production) or `asserted` (local/test only). |
| `VEDA_SNAPSHOT_DIR` (required in staging and production: absolute, inside the database volume, RR-14), `VEDA_SNAPSHOT_BUCKET` (required in production), `VEDA_SNAPSHOT_KEEP`, `VEDA_SNAPSHOT_LOCK_DAYS` | §4 |
| `LITESTREAM_BUCKET`, `LITESTREAM_REGION`, `LITESTREAM_RETENTION` | `deploy/litestream.yml` |
