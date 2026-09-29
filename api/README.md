# Veda Spaces API (P0)

Flask modular monolith implementing the certified P0 architecture in
[`docs/architecture/`](../docs/architecture/README.md) (02 §3). SQLite now (single instance,
ADR-008), PostgreSQL-ready: every database test runs on both engines.

## Layout

```
veda/
  app.py                 application factory, middleware order, CORS, headers, startup route check
  config.py              env-driven settings; production refuses dev secrets (SEC-005)
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
    health.py            /health/live, /health/ready
  modules/crm/leads/     lead, lead_note, lead_activity: repository, service, routes, events
  cli/                   migrate, bootstrap-founder, sync-permissions, worker, scheduler,
                         maintenance jobs, break-glass, conformance, openapi, deploy-check
migrations/versions/     0001_kernel … 0008_account_security, 0100_crm_leads
tests/                   unit/ and integration/ (dual-engine)
tools/render_migrations.py   renders explicit Alembic DDL from the models
deploy/                  gunicorn (one gthread worker), Dockerfile, compose (api, worker, scheduler, litestream)
```

## Run locally

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export VEDA_DATABASE_URL=sqlite:///var/veda.db VEDA_COOKIE_SECURE=false VEDA_EMAIL_CAPTURE_DIR=var/mail
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
ruff check veda tests migrations tools
python -m veda.cli conformance   # schema conformance (03 §2.7) against VEDA_DATABASE_URL
```

## Production configuration

See `veda/config.py`. `VEDA_ENV=production` refuses to start without real JWT, HMAC, chain and
Turnstile secrets, AWS KMS, SES, secure cookies and OWASP-minimum Argon2 parameters. Retention jobs stay
disabled until the owner-approved values (OWNER-INPUT-002) are configured.
