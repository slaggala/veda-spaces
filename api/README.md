# Veda Spaces API (P0)

Flask modular monolith implementing the certified P0 architecture in
[`docs/architecture/`](../docs/architecture/README.md) (02 §3). SQLite now (single instance,
ADR-008), PostgreSQL-ready: every database test runs on both engines.

## Layout

```
veda/
  app.py                 application factory, middleware order, CORS, headers, startup route check
  config.py              env-driven settings; VEDA_ENV must be local|test|staging|production; staging and
                         production refuse development secrets and unsafe settings (SEC-005, IR-09)
  kernel/                GUID/UTC/JSON types, audit contract base, ActorContext, audit hook,
                         unit of work (BEGIN IMMEDIATE), outbox, sequences, errors, HTTP pipeline,
                         DTO validators, JCS, rate limiting, Turnstile, conformance check, OpenAPI
  platform/
    identity/            app_user (User), user_credential, profile presentation
    auth/                login, sessions, JWT (ES256), refresh + grace, passwords (Argon2id),
                         MFA (TOTP, recovery, 4 enrollment paths, step-up), security_event_log chain
    rbac/                registry (permission catalog + matrix), resolver, guards G1–G13,
                         invariants I1–I3, dual control, Founder governance, break-glass, users/roles API
    audit/               audit-log and security-event viewers (PII masking)
    lookups/             reference data API
    notifications/       outbox worker, handlers, email adapters (SES / capture / log), templates
    maintenance.py       purge, erasure audit rewrite, retention, chain verify/anchor/archive, invariants
    anchor_store.py      external chain anchors and archive manifests (local directory or S3 Object Lock)
    backups.py           nightly VACUUM INTO snapshot, restore verification, disk usage
    health.py            /health/live, /health/ready (schema head / declared-ahead semantics, AM-6)
  modules/crm/leads/     lead, lead_note, lead_activity: repository, service, routes, events
  cli/                   migrate, bootstrap-founder, sync-permissions, worker, scheduler,
                         maintenance jobs, break-glass, conformance, openapi, deploy-check
migrations/versions/     0001_kernel … 0008_account_security, 0100_crm_leads, 0009_mfa_challenge_binding
tests/                   unit/ and integration/ (dual-engine)
tools/                   render_migrations.py, mypy_ratchet.py (+ mypy-baseline.json), openapi_check.py,
                         secret_scan.sh, e2e_reset.sh
openapi.snapshot.json    the committed API contract (CI fails on drift)
deploy/                  gunicorn (one gthread worker, enforced at start-up), Dockerfile (digest-pinned, hash-locked),
                         compose (api, worker, scheduler, litestream), litestream.yml, deploy.sh
requirements.in          declared runtime ranges → requirements.txt (pip-compile, hashes)
requirements-dev.in      tools → requirements-dev.txt (pip-compile, hashes)
```

## Run locally

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install --require-hashes -r requirements-dev.txt
export VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/veda.db VEDA_COOKIE_SECURE=false VEDA_EMAIL_CAPTURE_DIR=var/mail
mkdir -p var && python -m veda.cli migrate
python -m veda.cli bootstrap-founder --email you@vedaspaces.com --name "Your Name"   # prints a 1-hour invite link
flask --app wsgi run --port 5000          # API
python -m veda.cli worker                 # outbox worker (emails land in var/mail as .eml)
```

Then run the workspace (`../app`, `npm run dev`) and open the invite link. Local mode uses
development keys, the local KMS stand-in, the capture email adapter and a permissive Turnstile
verifier (tokens starting with `fail` are rejected).

## Tests

```bash
python -m pytest              # both engines when the embedded PostgreSQL (pixeltable-pgserver) is available
VEDA_TEST_ENGINES=sqlite python -m pytest
VEDA_TEST_ENGINES=postgresql VEDA_TEST_DATABASE_URL_PG=postgresql+psycopg://postgres:pw@localhost:5432/postgres python -m pytest
ruff check veda tests migrations tools && ruff format --check veda tests migrations tools
python tools/mypy_ratchet.py     # mypy; fails on any new finding (baseline: tools/mypy-baseline.json)
python tools/openapi_check.py    # API contract drift against openapi.snapshot.json
tools/secret_scan.sh             # detect-secrets against ../.secrets.baseline
python -m veda.cli conformance   # schema conformance (03 §2.7) against VEDA_DATABASE_URL
```

Browser journeys against a live local stack: `API_PYTHON=.venv/bin/python ../app/e2e/run-all.sh`.

## Staging and production configuration

See `veda/config.py` and [the runbooks](../docs/operations/api-runbooks.md). `VEDA_ENV=staging` and
`VEDA_ENV=production` refuse to start (API, CLI and migrations) without real JWT, HMAC (≥ 32 bytes), chain and
Turnstile secrets, a real AWS KMS key, SES, secure cookies, rate limits, OWASP-minimum Argon2 parameters, public
https origins, an absolute database path, STS custodian identity and the trusted proxy CIDRs; production also needs
Sentry, the anchor bucket and the snapshot bucket. Retention jobs stay disabled until the owner-approved values
(OWNER-INPUT-002) are configured.
