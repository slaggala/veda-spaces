# Post-validation hardening A1: dead outbox events and invite-token hygiene (R1, R2, R3)

**Scope:** follow-ups R1, R2 and R3 of the AUT-202 to AUT-204 evidence
([record](../../release-evidence/AUT-202-204-STAGING-FRONTENDS/README.md) §6). Application and runbook changes only:
no infrastructure, no change to public intake, Cloudflare Access or the trust boundary.

## 1. Problems

| # | Problem | Risk |
|---|---|---|
| R3 | A dead outbox event can only be cleared by editing the database. The staging invite event died before the SES fix, so `veda-stg-outbox-dead` is stuck in ALARM; CloudWatch notifies only on a state change, so **a new dead event, such as a lead notification, would not alert** | High (active) |
| R2 | `bootstrap-founder` prints the invite link (a credential) to stdout; the container's stdout is shipped to the log group (incident I2) | High (latent: every later bootstrap) |
| R1 | Nothing stopped a deployed bootstrap from printing the link; the only channel was stdout or `--email-link` | Medium |

## 2. Changes

| Area | Change |
|---|---|
| `veda/platform/notifications/dead_letters.py` (new) | `list_dead()` (id, type, aggregate type, attempts, `last_error`, created; **never the payload**), `retire(id, reason)` (DEAD → DONE, `last_error = "RETIRED: <reason>"`, never runs), `requeue(id, reason)` (DEAD → PENDING, attempts 0, `last_error = "REQUEUED: <reason>"`). DEAD events only; reason ≥ 10 characters; malformed or unknown ids refused; a warning log line per action; actor context `CLI` with the reason |
| `veda cli outbox dead / retire / requeue` | Wraps the above; refusals exit 2 with `refused: …` |
| `veda cli bootstrap-founder` | In staging and production the link is **never printed**: `--email-link` (stdout says `"invite": "emailed"`) or `--link-file <path>` (new file, mode 0600, `O_EXCL`; an existing file refuses and the bootstrap rolls back). Without either, it refuses **before** creating anything. Local and test still print it (`tools/e2e_reset.sh`) |
| `veda/kernel/logging.py` | Defence in depth: `token`, `code`, `key`, `secret`, `signature`, `sig` URL parameters (query or fragment) are masked in every logged string field and message |
| Runbooks | `api-runbooks.md`: the outbox alarm row uses the CLI (was a manual database edit). `staging-platform-runbooks.md` §3: clearing dead events, and why every one must be cleared; new §6.7: the Founder bootstrap |

**Design choices:**
- **Retired events become DONE, with the reason in `last_error`.** A new `RETIRED` status would change a CHECK constraint
  (a table rebuild on SQLite) for no behavioural gain: DONE events are never claimed again, and the reason keeps them
  distinguishable.
- **The audit record is the event's own `last_error` plus a log line.** The table is `EVENT_ONLY`, so no row audit. The
  operator's SSM Run Command or session is also in CloudTrail. No new security-event type was added: the catalogue is
  for authentication and authorization events.

## 3. Tests

| Test | Proves | Fails without the change |
|---|---|---|
| `test_outbox_dead_letters.py`: listed without payloads | No token or payload in the listing | — (new) |
| … retire clears the dead count | Status DONE, reason recorded, `outbox_stats` dead 0, depth 0 | Yes (mutation: retire leaves DEAD) |
| … requeue from the first attempt | PENDING, attempts 0, reason recorded | — |
| … only DEAD events (PENDING, FAILED, DONE refused) | No accidental re-run or retire of live events | Yes (mutation: status check removed) |
| … a reason is required | | — |
| … CLI: list, `--id` required, unknown id refused, retire | | — |
| `test_founder_governance.py`: deployed without a channel refused | Nothing created, no `BOOTSTRAP_FOUNDER` event | Yes (mutation: link always printed) |
| … `--email-link` prints no token, enqueues `user.invited` | | Yes |
| … `--link-file` writes a 0600 file, prints no token | | Yes |
| … an existing link file is never overwritten; the bootstrap rolls back | | Yes |
| … only local and test print the link (`local`, `test`, `staging`, `production`) | | Yes (mutation: always allowed) |
| `test_logging_pii.py`: token links masked in messages and fields | Invite, reset and MFA links; stdlib and structlog | Yes (mutation: masking removed) |
| … ordinary URLs kept | No over-masking | — |

## 4. Validation

- Full API suite on SQLite and PostgreSQL; ruff and format; mypy ratchet (results in the pull request).
- Mutation checks as above, run locally.
- `make -C infra check` is unaffected (no infrastructure files changed).

## 5. Rollout

1. Merge, then `12-deploy`. No plan or apply.
2. Retire the spent invite event on staging (Run Command):
   `outbox dead`, then `outbox retire --id <id> --reason "invite already accepted through the link (AUT-204 I2)"`.
3. Check: `/health/ready` reports `outbox_dead: 0`; `veda-stg-outbox-dead` returns to OK.

## 6. Residual risk

- The spent invite token stays in `/veda/staging/app` until the 30-day retention ends. It is dead (accepted), so it
  cannot be used.
- The masking backstop applies to log lines produced by the application. A raw `print` by a future command would
  bypass it; the CLI therefore never prints the link in deployed environments, and the tests pin that.
