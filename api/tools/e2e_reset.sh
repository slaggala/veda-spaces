#!/usr/bin/env bash
# Reset the local E2E database and bootstrap a Founder. Stop the API server first.
set -euo pipefail
cd "$(dirname "$0")/.."
. .venv/bin/activate
export VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db VEDA_COOKIE_SECURE=false VEDA_EMAIL_CAPTURE_DIR=var/mail \
       VEDA_ARGON2_MEMORY_KIB=19456 VEDA_ARGON2_TIME_COST=2 VEDA_PUBLIC_SITE_ORIGINS=http://localhost:8000
rm -f var/e2e.db var/e2e.db-wal var/e2e.db-shm && rm -rf var/mail
python -m veda.cli migrate >/dev/null 2>&1
python -m veda.cli bootstrap-founder --email founder@vedaspaces.test --name "Lakshmi Rao" | tail -1 > var/bootstrap.json
cat var/bootstrap.json
