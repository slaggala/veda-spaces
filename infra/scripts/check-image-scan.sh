#!/usr/bin/env bash
# Image scan gate (12-deploy; runbook docs/operations/staging-platform-runbooks.md §1). Reads the output of
# `aws ecr describe-image-scan-findings` and refuses the image unless every HIGH or CRITICAL finding is covered by a
# reviewed exception for this environment.
#
#   infra/scripts/check-image-scan.sh --findings <json file> --environment staging|production \
#       [--exceptions infra/config/image-scan-exceptions.json] [--today YYYY-MM-DD]
#
# An exception covers a finding only when all of these hold:
#   - its environment is the one being deployed, and it is "staging": production has no exceptions, ever;
#   - the vulnerability ID is the finding's name, exactly;
#   - the package name and version are the finding's package_name and package_version attributes, exactly;
#   - it is not expired: today is before its expiry date (an exception expiring 2026-12-31 last covers 2026-12-30);
#   - it is complete and lasts at most 90 days from its approval.
# Any malformed exception, any HIGH or CRITICAL finding left uncovered, or severity counts that disagree with the
# findings refuse the image. An exception that matches nothing is reported, so it can be removed.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

FINDINGS="" ENVIRONMENT="" TODAY="" EXCEPTIONS="$INFRA_DIR/config/image-scan-exceptions.json"
while (($#)); do
  case "$1" in
    --findings) FINDINGS="${2:-}"; shift 2 ;;
    --environment) ENVIRONMENT="${2:-}"; shift 2 ;;
    --exceptions) EXCEPTIONS="${2:-}"; shift 2 ;;
    --today) TODAY="${2:-}"; shift 2 ;;
    -h | --help) sed -n '2,17p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done
require_tools jq
[[ "$ENVIRONMENT" == staging || "$ENVIRONMENT" == production ]] || die "--environment must be staging or production"
[[ -f "$FINDINGS" ]] || die "--findings must be the scan findings JSON"
[[ -f "$EXCEPTIONS" ]] || die "image scan exceptions file not found: $EXCEPTIONS"
TODAY="${TODAY:-$(date -u +%F)}"
[[ "$TODAY" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] || die "--today must be YYYY-MM-DD"
jq -e 'type == "object"' "$FINDINGS" >/dev/null 2>&1 || die "the scan findings are not a JSON object"
jq -e 'type == "object" and (.exceptions | type) == "array"' "$EXCEPTIONS" >/dev/null 2>&1 ||
  die "$EXCEPTIONS is not a JSON object with an exceptions array"

# Every exception must be well formed, staging-only, and at most 90 days long.
problems="$(jq -r '
  def date: test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$");
  def days($a; $b): (($b + "T00:00:00Z" | fromdateiso8601) - ($a + "T00:00:00Z" | fromdateiso8601)) / 86400;
  .exceptions | to_entries[] | .key as $i | .value as $e
  | ["environment", "vulnerability", "package", "version", "severity", "reason", "approved_on", "expires"] as $req
  | ($req | map(select(($e[.] // "") | type != "string" or length == 0))) as $missing
  | if ($missing | length) > 0 then "exception \($i): missing \($missing | join(", "))"
    elif $e.environment != "staging" then "exception \($i) (\($e.vulnerability)): environment \($e.environment); only staging may have exceptions"
    elif ($e.vulnerability | test("^(CVE-[0-9]{4}-[0-9]{4,}|GHSA(-[0-9a-z]{4}){3})$") | not) then "exception \($i): \($e.vulnerability) is not a CVE or GHSA ID"
    elif ($e.severity | IN("HIGH", "CRITICAL") | not) then "exception \($i) (\($e.vulnerability)): severity must be HIGH or CRITICAL"
    elif (($e.approved_on | date) and ($e.expires | date) | not) then "exception \($i) (\($e.vulnerability)): dates must be YYYY-MM-DD"
    elif days($e.approved_on; $e.expires) > 90 or days($e.approved_on; $e.expires) < 1 then "exception \($i) (\($e.vulnerability)): must expire 1 to 90 days after approval"
    elif (($e.compensating_controls // []) | length) == 0 then "exception \($i) (\($e.vulnerability)): compensating_controls are required"
    else empty end' "$EXCEPTIONS")" || die "cannot read $EXCEPTIONS"
if [[ -n "$problems" ]]; then
  while IFS= read -r p; do log "EXCEPTION: $p"; done <<<"$problems"
  die "malformed image scan exceptions; refusing"
fi

# Decide every HIGH or CRITICAL finding.
result="$(jq -c --slurpfile ex "$EXCEPTIONS" --arg env "$ENVIRONMENT" --arg today "$TODAY" '
  def attr($k): ([.attributes[]? | select(.key == $k) | .value] | first) // "";
  [.imageScanFindings.findings[]? | select(.severity == "HIGH" or .severity == "CRITICAL")
   | {id: .name, severity, package: attr("package_name"), version: attr("package_version")}] as $blocking
  | ($ex[0].exceptions | map(select(.environment == $env))) as $mine
  | ($mine | map(select($today < .expires))) as $live
  | {
      counted: (((.imageScanFindings.findingSeverityCounts.HIGH // 0) + (.imageScanFindings.findingSeverityCounts.CRITICAL // 0))),
      listed: ($blocking | length),
      covered: [$blocking[] | . as $f | select(any($live[]; .vulnerability == $f.id and .package == $f.package and .version == $f.version))],
      uncovered: [$blocking[] | . as $f
        | select(any($live[]; .vulnerability == $f.id and .package == $f.package and .version == $f.version) | not)
        | . + {expired: any($mine[]; .vulnerability == $f.id and .package == $f.package and .version == $f.version and ($today < .expires | not))}],
      unused: [$live[] | . as $e | select(any($blocking[]; .id == $e.vulnerability and .package == $e.package and .version == $e.version) | not) | .vulnerability]
    }' "$FINDINGS")"

counted="$(jq -r .counted <<<"$result")" listed="$(jq -r .listed <<<"$result")"
[[ "$counted" == "$listed" ]] ||
  die "the scan counts $counted HIGH or CRITICAL findings but lists $listed; refusing"
while IFS= read -r f; do
  [[ -n "$f" ]] && log "covered by a reviewed $ENVIRONMENT exception: $f"
done < <(jq -r '.covered[] | "\(.severity) \(.id) \(.package)::\(.version)"' <<<"$result")
while IFS= read -r u; do
  [[ -n "$u" ]] && warn "image scan exception $u matches no finding: remove it"
done < <(jq -r '.unused[]' <<<"$result")
if [[ "$(jq '.uncovered | length' <<<"$result")" != 0 ]]; then
  while IFS= read -r f; do log "BLOCKING: $f"; done < <(jq -r '.uncovered[] |
    "\(.severity) \(.id) \(.package)::\(.version)\(if .expired then " (its exception has expired)" else "" end)"' <<<"$result")
  die "the image has HIGH or CRITICAL findings not covered by a reviewed $ENVIRONMENT exception; refusing to deploy it"
fi
log "image scan gate ($ENVIRONMENT): $listed HIGH or CRITICAL finding(s), all covered by reviewed exceptions"
