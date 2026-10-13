#!/usr/bin/env bash
# MTQ B1 site measurement preflight (B1-T11). Reads a rendered environment file (NAME="value" lines, as render-env.sh
# writes) and reports the site-measurement state in plain words, printing names, never values.
#
#   attachment-preflight.sh <rendered env file>
#
# - VEDA_MTQ_SITE_ENABLED absent or "false": site measurement intentionally disabled (every route answers 404); the
#   attachment settings are inert and not required, so a host may render before the attachment storage is applied.
# - "true": every attachment setting must be planned, the backend must be the private bucket (s3) and the scanner
#   clamd. The API refuses the same at start; this refuses before api.env is replaced.
# - anything else: refused (a flag is "true" or "false", never a guess).
set -euo pipefail
FILE="${1:?usage: attachment-preflight.sh <rendered env file>}"
REQUIRED=(VEDA_ATTACHMENT_BACKEND VEDA_ATTACHMENT_BUCKET VEDA_ATTACHMENT_KMS_KEY_ARN VEDA_ATTACHMENT_SCANNER
  VEDA_ATTACHMENT_CLAMD_ADDRESS VEDA_ATTACHMENT_UPLOAD_TTL_SECONDS)

value() { # value <NAME>: the rendered value without its quotes (empty when absent)
  sed -n "s/^$1=\"\{0,1\}\([^\"]*\)\"\{0,1\}$/\1/p" "$FILE" | tail -n 1
}

flag="$(value VEDA_MTQ_SITE_ENABLED)"
case "$flag" in
  "" | false)
    echo "site measurement: intentionally disabled (VEDA_MTQ_SITE_ENABLED is ${flag:-absent}; every site and attachment route answers 404)"
    exit 0
    ;;
  true) ;;
  *)
    echo "SITE FLAG INVALID: VEDA_MTQ_SITE_ENABLED must be true or false" >&2
    exit 1
    ;;
esac

missing=()
for s in "${REQUIRED[@]}"; do grep -q "^$s=" "$FILE" || missing+=("$s"); done
if ((${#missing[@]})); then
  echo "ATTACHMENT STORAGE NOT APPLIED: ${#missing[@]} setting(s) absent (apply staging-core first): ${missing[*]}" >&2
  exit 1
fi
if [[ "$(value VEDA_ATTACHMENT_BACKEND)" != s3 ]]; then
  echo "ATTACHMENT BACKEND UNSAFE: VEDA_ATTACHMENT_BACKEND must be s3 (the private bucket) when site measurement is on" >&2
  exit 1
fi
if [[ "$(value VEDA_ATTACHMENT_SCANNER)" != clamd ]]; then
  echo "SITE MEASUREMENT WITHOUT A SCANNER: VEDA_ATTACHMENT_SCANNER must be clamd when site measurement is on (fail closed)" >&2
  exit 1
fi
echo "site measurement: ENABLED with the private attachment bucket and the clamd scanner"
