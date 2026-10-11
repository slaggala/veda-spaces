#!/usr/bin/env bash
# Validate a candidate ClamAV image for the catalog V3 scanner on an arm64 host (CATALOG-V3-media-enablement.md §6).
# No credentials, no AWS, no staging: the image is pulled by digest from Docker Hub and run locally in three profiles.
#   A  the certified Compose profile (api/deploy/docker-compose.yml, service clamd) exactly as it stands
#   B  the proposed non-root profile: /init-unprivileged as uid 1000, no capability, read-only root, tmpfs (mode
#      1777) for /tmp, /run/clamav and /var/log/clamav, this directory's clamd.conf (ConcurrentDatabaseReload no)
#   C  profile B with ConcurrentDatabaseReload yes, for the reload-peak comparison
# Every profile records whether clamd answered, how long it took, health and the last log lines. B and C also record
# the process user, an EICAR stream (must be FOUND), a clean stream, the StreamMaxLength limit, freshclam's write to
# the signature volume, the signature build time and cgroup memory at load and during a RELOAD.
# This is evidence for the owner's decisions AD-1 and AD-2; it decides nothing and changes nothing outside the host.
#
#   infra/scanner-validation/validate.sh <name:tag@sha256:digest>
set -euo pipefail

IMAGE="${1:-}"
[[ "$IMAGE" =~ ^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$ ]] ||
  { echo "usage: $0 <name:tag@sha256:digest> (pinned by digest, as deploy.sh requires)"; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${SCANNER_VALIDATION_OUT:-$(mktemp -d)}"
RESULTS="$OUT/results.tsv"
: >"$RESULTS"
note() { echo "[$(date -u +%H:%M:%S)] $*"; }
rec() { printf '%s\t%s\n' "$1" "$2" >>"$RESULTS"; note "$1 = $2"; }
get() { awk -F'\t' -v k="$1" '$1 == k { v = $2 } END { print v }' "$RESULTS"; }
cleanup() {
  for c in sv-a sv-b sv-c; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  for v in sv-vol-a sv-vol-b sv-vol-c; do docker volume rm -f "$v" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT
cleanup

# --- the image ------------------------------------------------------------------------------------------------------
note "pull $IMAGE"
docker pull --quiet "$IMAGE" >/dev/null
rec image "$IMAGE"
rec platform "$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "$IMAGE")"
rec repo_digests "$(docker image inspect -f '{{join .RepoDigests ","}}' "$IMAGE")"
rec image_id "$(docker image inspect -f '{{.Id}}' "$IMAGE")"
rec image_size_bytes "$(docker image inspect -f '{{.Size}}' "$IMAGE")"
rec image_entrypoint "$(docker image inspect -f '{{join .Config.Entrypoint " "}}' "$IMAGE")"
rec image_user "$(docker image inspect -f '{{.Config.User}}' "$IMAGE")"
[[ "$(get platform)" == "linux/arm64" ]] || { echo "REFUSED: the image resolved to $(get platform), not linux/arm64"; exit 1; }
rec host "$(uname -m) $(uname -r)"
rec clamd_version "$(docker run --rm --entrypoint clamd "$IMAGE" --version)"
rec database_files "$(docker run --rm --entrypoint sh "$IMAGE" -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"')"
rec database_dir "$(docker run --rm --entrypoint stat "$IMAGE" -c '%A %u:%g' /var/lib/clamav)"
rec log_dir "$(docker run --rm --entrypoint stat "$IMAGE" -c '%A %u:%g' /var/log/clamav)"
rec clamdcheck_present "$(docker run --rm --entrypoint sh "$IMAGE" -c 'test -x /usr/local/bin/clamdcheck.sh && echo yes || echo no')"
rec init_unprivileged_present "$(docker run --rm --entrypoint sh "$IMAGE" -c 'test -x /init-unprivileged && echo yes || echo no')"
rec signature_daily_build "$(docker run --rm --entrypoint sigtool "$IMAGE" --info /var/lib/clamav/daily.cvd | sed -n 's/^Build time: *//p')"
rec image_stream_max_length "$(docker run --rm --entrypoint sh "$IMAGE" -c 'grep -E "^#?StreamMaxLength" /etc/clamav/clamd.conf | tr "\n" ";"')"

# --- helpers --------------------------------------------------------------------------------------------------------
HEALTH=(--health-cmd clamdcheck.sh --health-interval 60s --health-timeout 10s --health-start-period 600s --health-retries 3)
ready_wait() { # name limit-seconds
  local name=$1 limit=$2 t=0 st
  while (( t < limit )); do
    st="$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)"
    if [[ "$st" != running ]]; then
      rec "${name}_outcome" "container $st, exit code $(docker inspect -f '{{.State.ExitCode}}' "$name" 2>/dev/null || echo '?') after ${t}s"
      return 1
    fi
    if docker exec "$name" clamdcheck.sh >/dev/null 2>&1; then rec "${name}_outcome" "ready after ${t}s"; return 0; fi
    if docker logs "$name" 2>&1 | grep -qE "Can't initialize the internal logger|Failed to start clamd|Initialization error"; then
      rec "${name}_outcome" "clamd failed to start (see the log lines) after ${t}s"
      return 1
    fi
    sleep 5; t=$((t + 5))
  done
  rec "${name}_outcome" "not ready after ${limit}s (container still running)"
  return 1
}
logs_tail() { echo "--- last log lines of $1 ---"; docker logs --tail 20 "$1" 2>&1 | sed 's/^/    /'; echo "---"; }
mem() { docker exec "$1" sh -c 'printf "current=%s peak=%s anon=%s" "$(cat /sys/fs/cgroup/memory.current)" "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo n/a)" "$(awk "/^anon /{print \$2}" /sys/fs/cgroup/memory.stat)"'; }
mib() { awk -v b="$1" 'BEGIN { printf "%.0f", b / 1048576 }'; }
# clamdscan from a sidecar that shares the container's network namespace: the scanner has no host port.
sidecar() { docker run --rm --network "container:$1" --entrypoint sh "$IMAGE" -c "$2" sh "${@:3}"; }
scan() { # name what(eicar|<bytes>)
  # shellcheck disable=SC2016 # the sidecar's own shell expands these
  sidecar "$1" '
    printf "TCPSocket 3310\nTCPAddr 127.0.0.1\n" >/tmp/c.conf
    case "$1" in
      eicar) printf "%s%s" "X5O!P%@AP[4\\PZX54(P^)7CC)7}\$" "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!\$H+H*" >/tmp/f ;;
      *) head -c "$1" /dev/urandom >/tmp/f ;;
    esac
    out=$(clamdscan --config-file=/tmp/c.conf --stream --no-summary /tmp/f 2>&1); rc=$?
    printf "rc=%s %s" "$rc" "$(printf "%s" "$out" | tr "\n" " ")"' "$2"
}
reload_peak() { # name → max memory.current sampled every second for 120 s after RELOAD
  local name=$1 max=0 cur t
  sidecar "$name" 'printf "TCPSocket 3310\nTCPAddr 127.0.0.1\n" >/tmp/c.conf; clamdscan --config-file=/tmp/c.conf --reload' >/dev/null
  for t in $(seq 1 120); do
    cur="$(docker exec "$name" cat /sys/fs/cgroup/memory.current 2>/dev/null || echo 0)"
    (( cur > max )) && max=$cur
    sleep 1
  done
  echo "$max"
}
exercise() { # name: the checks on a ready profile
  local name=$1 m0 peak_reload m2 t
  rec "${name}_processes" "$(docker top "$name" -eo user,pid,comm | tail -n +2 | awk '{printf "%s:%s ", $1, $3}')"
  for t in $(seq 1 18); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "$name")" == healthy ]] && break; sleep 5
  done
  rec "${name}_health" "$(docker inspect -f '{{.State.Health.Status}}' "$name")"
  rec "${name}_eicar_stream" "$(scan "$name" eicar)"
  rec "${name}_clean_1MiB_stream" "$(scan "$name" 1048576)"
  rec "${name}_clean_20MiB_stream" "$(scan "$name" 20971520)"
  rec "${name}_oversize_31MiB_stream" "$(scan "$name" 32505856)"
  m0="$(mem "$name")"; rec "${name}_memory_loaded" "$m0"
  rec "${name}_memory_loaded_mib" "current=$(mib "${m0#*current=}") peak=$(mib "$(sed -n 's/.*peak=\([0-9]*\).*/\1/p' <<<"$m0")") anon=$(mib "${m0##*anon=}")"
  peak_reload="$(reload_peak "$name")"
  m2="$(mem "$name")"
  rec "${name}_memory_reload_sampled_max_mib" "$(mib "$peak_reload")"
  rec "${name}_memory_after_reload_mib" "current=$(mib "${m2#*current=}") peak=$(mib "$(sed -n 's/.*peak=\([0-9]*\).*/\1/p' <<<"$m2")") anon=$(mib "${m2##*anon=}")"
  rec "${name}_oom_killed" "$(docker inspect -f '{{.State.OOMKilled}}' "$name")"
  for t in $(seq 1 24); do
    docker exec "$name" sh -c 'grep -qiE "up-to-date|updated|is up to date" /var/log/clamav/freshclam.log 2>/dev/null' && break; sleep 5
  done
  rec "${name}_freshclam_log" "$(docker exec "$name" sh -c 'tail -n 3 /var/log/clamav/freshclam.log 2>/dev/null | tr "\n" " "' || echo 'no freshclam log')"
  rec "${name}_volume_after" "$(docker exec "$name" sh -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"')"
  rec "${name}_still_ready" "$(docker exec "$name" clamdcheck.sh 2>&1 | tr '\n' ' ')"
}

# --- profile A: the certified Compose profile -----------------------------------------------------------------------
note "profile A: certified Compose profile (root entrypoint /init, CHOWN+SETUID+SETGID, read-only, tmpfs /tmp /run/clamav)"
docker volume create sv-vol-a >/dev/null
docker run -d --name sv-a --read-only --cap-drop ALL --cap-add CHOWN --cap-add SETUID --cap-add SETGID \
  --security-opt no-new-privileges:true --tmpfs /tmp --tmpfs /run/clamav -v sv-vol-a:/var/lib/clamav \
  --memory 1536m --memory-reservation 1024m -e CLAMAV_NO_MILTERD=true -e CLAMD_STARTUP_TIMEOUT=1800 \
  "${HEALTH[@]}" "$IMAGE" >/dev/null
if ready_wait sv-a 300; then exercise sv-a; fi
logs_tail sv-a
docker rm -f sv-a >/dev/null

# --- profiles B and C: the proposed non-root profile ----------------------------------------------------------------
run_profile() { # name conf
  docker volume create "sv-vol-${1#sv-}" >/dev/null
  docker run -d --name "$1" --user 1000:1000 --entrypoint /init-unprivileged --read-only --cap-drop ALL \
    --security-opt no-new-privileges:true --tmpfs /tmp:mode=1777 --tmpfs /run/clamav:mode=1777 --tmpfs /var/log/clamav:mode=1777 \
    -v "sv-vol-${1#sv-}:/var/lib/clamav" -v "$2:/etc/clamav/clamd.conf:ro" \
    --memory 3g --memory-reservation 1g -e CLAMAV_NO_MILTERD=true -e CLAMD_STARTUP_TIMEOUT=1800 \
    "${HEALTH[@]}" "$IMAGE" >/dev/null
}
note "profile B: non-root /init-unprivileged, no capability, read-only, tmpfs mode 1777 for /tmp /run/clamav /var/log/clamav, clamd.conf (ConcurrentDatabaseReload no)"
run_profile sv-b "$HERE/clamd.conf"
if ready_wait sv-b 900; then exercise sv-b; fi
logs_tail sv-b
docker rm -f sv-b >/dev/null

note "profile C: profile B with ConcurrentDatabaseReload yes"
sed 's/^ConcurrentDatabaseReload no$/ConcurrentDatabaseReload yes/' "$HERE/clamd.conf" >"$OUT/clamd-concurrent.conf"
grep -q '^ConcurrentDatabaseReload yes$' "$OUT/clamd-concurrent.conf"
run_profile sv-c "$OUT/clamd-concurrent.conf"
if ready_wait sv-c 900; then exercise sv-c; fi
logs_tail sv-c
docker rm -f sv-c >/dev/null

# --- summary --------------------------------------------------------------------------------------------------------
{
  echo "{"
  while IFS=$'\t' read -r k v; do
    printf '  "%s": "%s",\n' "$k" "$(printf '%s' "$v" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')"
  done <"$RESULTS"
  printf '  "validated_at": "%s"\n}\n' "$(date -u +%FT%TZ)"
} >"$OUT/summary.json"
note "summary $OUT/summary.json sha256 $(sha256sum "$OUT/summary.json" | cut -d' ' -f1)"
cat "$OUT/summary.json"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "## Scanner image validation"; echo; echo "| Key | Value |"; echo "|---|---|"
    while IFS=$'\t' read -r k v; do printf '| %s | %s |\n' "$k" "$(printf '%s' "$v" | sed 's/|/\\|/g')"; done <"$RESULTS"
    echo; echo "summary.json sha256: $(sha256sum "$OUT/summary.json" | cut -d' ' -f1)"
  } >>"$GITHUB_STEP_SUMMARY"
fi
