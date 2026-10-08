#!/usr/bin/env bash
# Reset the local E2E database and bootstrap a Founder. Stop the API server first.
#   PYTHON=<interpreter> tools/e2e_reset.sh     (default: .venv/bin/python)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-.venv/bin/python}"
export VEDA_ENV=local VEDA_DATABASE_URL=sqlite:///var/e2e.db VEDA_COOKIE_SECURE=false VEDA_EMAIL_CAPTURE_DIR=var/mail \
       VEDA_ARGON2_MEMORY_KIB=19456 VEDA_ARGON2_TIME_COST=2 VEDA_PUBLIC_SITE_ORIGINS=http://localhost:8000
mkdir -p var
rm -f var/e2e.db var/e2e.db-wal var/e2e.db-shm var/e2e.db.api.lock && rm -rf var/mail var/anchors
"$PY" -m veda.cli migrate >/dev/null 2>&1
# Budgetary Estimate (ADR-012): the SYNTHETIC rate card only (never commercial rates).
"$PY" -m veda.cli estimator load-card tests/fixtures/estimator/synthetic-rate-card.json >/dev/null
"$PY" -m veda.cli estimator activate-card --version SYNTHETIC-2 --approval "E2E synthetic card (no commercial rates)" >/dev/null
# The customer specification master (ADR-012 T9): the SYNTHETIC specification only.
"$PY" -m veda.cli estimator load-spec tests/fixtures/estimator/synthetic-customer-spec.json >/dev/null
"$PY" -m veda.cli estimator activate-spec --spec SYNTHETIC-ESSENTIAL-1.0 --approval "E2E synthetic specification" >/dev/null
"$PY" -m veda.cli bootstrap-founder --email founder@vedaspaces.test --name "Lakshmi Rao" | tail -1 > var/bootstrap.json
cat var/bootstrap.json
