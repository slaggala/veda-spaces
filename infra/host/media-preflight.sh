#!/usr/bin/env bash
# Catalog V3 media deployment preflight (pre-plan closure, phase 7). Reads a rendered environment file (NAME="value"
# lines, as render-env.sh writes) and reports the media and V3 state in plain words, printing names, never values.
# Exit 0: safe to deploy. Exit 1: refused, nothing has been changed on the host.
#
#   media-preflight.sh <rendered env file>
#
#   MEDIA INFRASTRUCTURE NOT APPLIED   a common media setting is missing (apply staging-core before deploying)
#   SCANNER SETTINGS INCOMPLETE        clamd is selected without an image pinned by digest
#   PARTIAL ACTIVATION                 some V3 flags on, others off (refused at plan too)
#   APPROVAL DIGEST NOT BOUND          every V3 flag on but VEDA_CATALOG_APPROVAL_SHA256 is not a SHA-256
#   V3 ACTIVATION REQUESTED            every V3 flag on: deploy.sh then requires a current APPROVED approval record
#   scanner not selected / V3 intentionally disabled   informational; the deploy continues
set -euo pipefail
FILE="${1:?usage: media-preflight.sh <rendered env file>}"
COMMON=(VEDA_CATALOG_MEDIA_BACKEND VEDA_CATALOG_MEDIA_BUCKET VEDA_CATALOG_MEDIA_KMS_KEY_ARN VEDA_CATALOG_MEDIA_SOURCE_PREFIX
  VEDA_CATALOG_MEDIA_VARIANT_PREFIX VEDA_CATALOG_MEDIA_SCANNER VEDA_CATALOG_MEDIA_DELIVERY_ENABLED VEDA_CATALOG_3D_ENABLED
  VEDA_CATALOG_VIDEO_ENABLED VEDA_CATALOG_ESTIMATOR_ENABLED VEDA_CATALOG_ADMIN_ENABLED VEDA_CATALOG_CLAMD_ADDRESS
  VEDA_CATALOG_CLAMD_IMAGE)
# VEDA_CATALOG_APPROVAL_SHA256 (activation remediation) is not in COMMON: a host deployed before the staging-core apply
# that plans it has none, which is the inactive value while V3 is off. It is required only for an activation.
value() { sed -n "s/^$1=//p" "$FILE" | tail -1 | sed -e 's/^"//' -e 's/"$//'; }

missing=()
for name in "${COMMON[@]}"; do grep -q "^$name=" "$FILE" || missing+=("$name"); done
if ((${#missing[@]})); then
  echo "MEDIA INFRASTRUCTURE NOT APPLIED: ${#missing[@]} setting(s) absent under /veda/staging/config: ${missing[*]}"
  echo "  Apply staging-core (reviewed plan, approved apply) before this deployment; nothing was changed."
  exit 1
fi
for name in VEDA_CATALOG_3D_ENABLED VEDA_CATALOG_VIDEO_ENABLED; do
  [[ "$(value "$name")" == "false" ]] || { echo "REFUSED: $name must be false (3D and video stay disabled)"; exit 1; }
done
scanner="$(value VEDA_CATALOG_MEDIA_SCANNER)"
case "$scanner" in
  none) echo "scanner not selected: uploads stay PENDING and nothing is served" ;;
  clamd)
    [[ "$(value VEDA_CATALOG_CLAMD_IMAGE)" =~ ^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$ ]] ||
      { echo "SCANNER SETTINGS INCOMPLETE: clamd is selected but its image is not pinned by digest"; exit 1; }
    echo "scanner: clamd (pinned image)" ;;
  *) echo "REFUSED: VEDA_CATALOG_MEDIA_SCANNER is neither none nor clamd"; exit 1 ;;
esac
on=0
for name in VEDA_CATALOG_ESTIMATOR_ENABLED VEDA_CATALOG_ADMIN_ENABLED VEDA_CATALOG_MEDIA_DELIVERY_ENABLED; do
  [[ "$(value "$name")" == "true" ]] && on=$((on + 1))
done
case "$on" in
  0) echo "V3 intentionally disabled: every V3 and media-delivery flag is false" ;;
  3)
    [[ "$scanner" == "clamd" ]] || { echo "REFUSED: V3 activation without the clamd scanner"; exit 1; }
    [[ "$(value VEDA_CATALOG_APPROVAL_SHA256)" =~ ^[0-9a-f]{64}$ ]] ||
      { echo "APPROVAL DIGEST NOT BOUND: VEDA_CATALOG_APPROVAL_SHA256 is not the SHA-256 of an approval record"; exit 1; }
    echo "V3 ACTIVATION REQUESTED: deploy.sh requires a current APPROVED V3 staging approval record in the image" ;;
  *) echo "PARTIAL ACTIVATION: $on of 3 V3 flags are on; refused (they turn on together or not at all)"; exit 1 ;;
esac
