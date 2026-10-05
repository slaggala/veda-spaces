#!/usr/bin/env bash
# Render /etc/veda/api.env (AUT-107, deployment wiring) from SSM: the non-secret configuration under
# /veda/staging/config and the secrets the owner seeded under /veda/staging/app (AUT-302). Run as root by veda-deploy.
# Refuses (and leaves the previous file in place) when a required secret is missing. Values with newlines (the PEM
# key) are written double-quoted with escapes, which Docker Compose env files read back.
set -euo pipefail
REGION="${1:?region}"
PATH_ROOT=/veda/staging
OUT=/etc/veda/api.env
REQUIRED_SECRETS=(VEDA_JWT_PRIVATE_KEY_PEM VEDA_JWT_KID VEDA_CHAIN_KEY VEDA_CHAIN_KEY_LABEL VEDA_RECOVERY_CODE_HMAC_KEY
  VEDA_EMAIL_HASH_HMAC_KEY VEDA_ACTION_TOKEN_KEY VEDA_TURNSTILE_SECRET)

fetch() { # fetch <path> [--with-decryption]: NAME<TAB>base64(value) per parameter
  aws ssm get-parameters-by-path --region "$REGION" --path "$1" --recursive "${@:2}" --output json |
    jq -r '.Parameters[] | [(.Name | split("/") | last), (.Value | @base64)] | @tsv'
}

umask 077
mkdir -p /etc/veda
TMP="$(mktemp /etc/veda/api.env.XXXXXX)"
trap 'rm -f "$TMP"' EXIT
{
  echo "# Rendered $(date -u +%FT%TZ) from SSM $PATH_ROOT/config and $PATH_ROOT/app (do not edit; re-run veda-deploy)"
  { fetch "$PATH_ROOT/config"; fetch "$PATH_ROOT/app" --with-decryption; } | sort | while IFS=$'\t' read -r name b64; do
    [[ "$name" =~ ^(VEDA|LITESTREAM)_[A-Z0-9_]+$ ]] || { echo "unexpected parameter name $name" >&2; exit 1; }
    value="$(printf '%s' "$b64" | base64 -d)"
    escaped="$(printf '%s' "$value" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' | awk 'BEGIN{ORS="\\n"} {print}' | sed 's/\\n$//')"
    printf '%s="%s"\n' "$name" "$escaped"
  done
} >"$TMP"
missing=()
for s in "${REQUIRED_SECRETS[@]}"; do grep -q "^$s=" "$TMP" || missing+=("$s"); done
if ((${#missing[@]})); then
  echo "refusing: secrets not seeded under $PATH_ROOT/app (AUT-302): ${missing[*]}" >&2
  exit 1
fi
# Keep a declared schema-ahead acceptance across renders (deploy.sh rollback, runbook §2).
if [[ -f "$OUT" ]] && grep -q '^VEDA_SCHEMA_AHEAD_ACCEPTED=' "$OUT"; then grep '^VEDA_SCHEMA_AHEAD_ACCEPTED=' "$OUT" >>"$TMP"; fi
chmod 0600 "$TMP"
mv "$TMP" "$OUT"
trap - EXIT
echo "rendered $OUT ($(grep -c '=' "$OUT") settings)"
