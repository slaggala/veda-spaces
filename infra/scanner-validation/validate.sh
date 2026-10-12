#!/usr/bin/env bash
# Validate the catalog V3 scanner on an arm64 host (CATALOG-V3-media-enablement.md §6; CATALOG-V3-scanner-implementation.md).
# No credentials, no AWS, no staging: the image is pulled by digest from Docker Hub and run locally, at the memory
# limit the deploy bundle configures (SCANNER_VALIDATION_MEMORY, default 2048m), in three profiles:
#   compose  the deploy bundle itself: api/deploy/docker-compose.yml, service clamd, started as deploy.sh step 4c
#            starts it (--profile scanner up -d --no-deps clamd), with the bundle's clamd.conf and entrypoint. Besides
#            the checks below it records the rendered hardening (user, capabilities, tmpfs, mounts, ports, limits),
#            then measures restart and recovery: a Compose restart, clamd killed inside the container, the container
#            killed, and a Compose stop (which must stay stopped).
#   B        the same non-root settings as a plain `docker run` with the image's own /init-unprivileged, for
#            comparison with the phase-1 measurements (which ran this profile under a 3 GiB limit)
#   C        profile B with ConcurrentDatabaseReload yes, for the reload-peak comparison under the same limit
# Every profile records whether clamd answered, how long it took, health, the process user, an EICAR stream (must be
# FOUND), clean streams, the StreamMaxLength limit (an oversized stream is an error, never CLEAN), freshclam's write
# to the signature volume, cgroup memory at load and during a RELOAD, and whether the kernel OOM-killed the container.
# This is evidence for the owner's decisions AD-1 and AD-2 and for the review of the scanner implementation; it
# decides nothing and changes nothing outside the host.
#
#   infra/scanner-validation/validate.sh <name:tag@sha256:digest>
#   SCANNER_VALIDATION_MEMORY=3072m infra/scanner-validation/validate.sh <image>    (another limit)
set -euo pipefail

IMAGE="${1:-}"
[[ "$IMAGE" =~ ^[a-z0-9./_-]+(:[A-Za-z0-9._-]+)?@sha256:[0-9a-f]{64}$ ]] ||
  { echo "usage: $0 <name:tag@sha256:digest> (pinned by digest, as deploy.sh requires)"; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DEPLOY="$REPO/api/deploy"
MEMORY="${SCANNER_VALIDATION_MEMORY:-2048m}"
[[ "$MEMORY" =~ ^[0-9]+[mg]$ ]] || { echo "SCANNER_VALIDATION_MEMORY must be like 2048m or 3g"; exit 2; }
OUT="${SCANNER_VALIDATION_OUT:-$(mktemp -d)}"
mkdir -p "$OUT"
RESULTS="$OUT/results.tsv"
: >"$RESULTS"
note() { echo "[$(date -u +%H:%M:%S)] $*"; }
rec() { printf '%s\t%s\n' "$1" "$2" >>"$RESULTS"; note "$1 = $2"; }
get() { awk -F'\t' -v k="$1" '$1 == k { v = $2 } END { print v }' "$RESULTS"; }
# The Compose project is named like the host's (the deploy directory), so the container is deploy-clamd-1, the name
# infra/host/health.sh inspects. The compose file's env_file (/etc/veda/api.env, the host's rendered configuration)
# must exist for Compose to load the file at all; an empty one is created when the host has none (a runner).
COMPOSE=(docker compose -p deploy -f "$DEPLOY/docker-compose.yml" --profile scanner)
CC=deploy-clamd-1
cleanup() {
  "${COMPOSE[@]}" rm -s -f clamd >/dev/null 2>&1 || true
  docker volume rm -f deploy_clamav-db >/dev/null 2>&1 || true
  for c in sv-b sv-c; do docker rm -f "$c" >/dev/null 2>&1 || true; done
  for v in sv-vol-b sv-vol-c; do docker volume rm -f "$v" >/dev/null 2>&1 || true; done
}
trap cleanup EXIT
cleanup

# --- the image ------------------------------------------------------------------------------------------------------
note "pull $IMAGE"
docker pull --quiet "$IMAGE" >/dev/null
rec image "$IMAGE"
rec memory_limit "$MEMORY"
# shellcheck disable=SC2016 # the literal ${VEDA_CLAMD_MEM_LIMIT:-...} text of the compose file is matched
rec compose_mem_limit_default "$(sed -n 's/.*mem_limit: \${VEDA_CLAMD_MEM_LIMIT:-\([0-9a-z]*\)}.*/\1/p' "$DEPLOY/docker-compose.yml")"
rec platform "$(docker image inspect -f '{{.Os}}/{{.Architecture}}' "$IMAGE")"
rec repo_digests "$(docker image inspect -f '{{join .RepoDigests ","}}' "$IMAGE")"
rec image_id "$(docker image inspect -f '{{.Id}}' "$IMAGE")"
rec image_size_bytes "$(docker image inspect -f '{{.Size}}' "$IMAGE")"
rec image_entrypoint "$(docker image inspect -f '{{join .Config.Entrypoint " "}}' "$IMAGE")"
rec image_user "$(docker image inspect -f '{{.Config.User}}' "$IMAGE")"
[[ "$(get platform)" == "linux/arm64" ]] || { echo "REFUSED: the image resolved to $(get platform), not linux/arm64"; exit 1; }
rec host "$(uname -m) $(uname -r)"
rec docker_version "$(docker version -f '{{.Server.Version}}') compose $(docker compose version --short)"
rec clamd_version "$(docker run --rm --entrypoint clamd "$IMAGE" --version)"
rec database_files "$(docker run --rm --entrypoint sh "$IMAGE" -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"')"
rec database_dir "$(docker run --rm --entrypoint stat "$IMAGE" -c '%A %u:%g' /var/lib/clamav)"
rec log_dir "$(docker run --rm --entrypoint stat "$IMAGE" -c '%A %u:%g' /var/log/clamav)"
rec clamav_uid_gid "$(docker run --rm --entrypoint id "$IMAGE" clamav)"
rec clamdcheck_present "$(docker run --rm --entrypoint sh "$IMAGE" -c 'test -x /usr/local/bin/clamdcheck.sh && echo yes || echo no')"
rec init_unprivileged_present "$(docker run --rm --entrypoint sh "$IMAGE" -c 'test -x /init-unprivileged && echo yes || echo no')"
rec init_unprivileged_pid1 "$(docker run --rm --entrypoint sh "$IMAGE" -c 'grep -E "^\s*exec tail" /init-unprivileged | tr -s " "')"
rec signature_daily_build "$(docker run --rm --entrypoint sigtool "$IMAGE" --info /var/lib/clamav/daily.cvd | sed -n 's/^Build time: *//p')"
rec image_stream_max_length "$(docker run --rm --entrypoint sh "$IMAGE" -c 'grep -E "^#?StreamMaxLength" /etc/clamav/clamd.conf | tr "\n" ";"')"
rec image_freshclam_conf "$(docker run --rm --entrypoint sh "$IMAGE" -c 'grep -vE "^(#|$)" /etc/clamav/freshclam.conf | tr "\n" ";"')"
rec bundle_clamd_conf_sha256 "$(sha256sum "$DEPLOY/clamd.conf" | cut -d' ' -f1)"
rec bundle_entrypoint_sha256 "$(sha256sum "$DEPLOY/clamd-entrypoint.sh" | cut -d' ' -f1)"
rec bundle_compose_sha256 "$(sha256sum "$DEPLOY/docker-compose.yml" | cut -d' ' -f1)"

# --- helpers --------------------------------------------------------------------------------------------------------
HEALTH=(--health-cmd clamdcheck.sh --health-interval 30s --health-timeout 10s --health-start-period 300s --health-retries 3)
ready_wait() { # name limit-seconds [key]: records <key>_outcome (default <name>_outcome)
  local name=$1 limit=$2 key=${3:-$1} t=0 st
  while (( t < limit )); do
    st="$(docker inspect -f '{{.State.Status}}' "$name" 2>/dev/null || echo missing)"
    if [[ "$st" != running && "$st" != restarting ]]; then
      rec "${key}_outcome" "container $st, exit code $(docker inspect -f '{{.State.ExitCode}}' "$name" 2>/dev/null || echo '?') after ${t}s"
      return 1
    fi
    if [[ "$st" == running ]] && docker exec "$name" clamdcheck.sh >/dev/null 2>&1; then rec "${key}_outcome" "ready after ${t}s"; return 0; fi
    if docker logs --since 10m "$name" 2>&1 | grep -qE "Can't initialize the internal logger|Failed to start clamd|Initialization error"; then
      rec "${key}_outcome" "clamd failed to start (see the log lines) after ${t}s"
      return 1
    fi
    sleep 5; t=$((t + 5))
  done
  rec "${key}_outcome" "not ready after ${limit}s (container $st)"
  return 1
}
logs_tail() { echo "--- last log lines of $1 ---"; docker logs --tail 25 "$1" 2>&1 | sed 's/^/    /'; echo "---"; }
mem() { docker exec "$1" sh -c 'printf "current=%s peak=%s anon=%s" "$(cat /sys/fs/cgroup/memory.current)" "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo n/a)" "$(awk "/^anon /{print \$2}" /sys/fs/cgroup/memory.stat)"'; }
mib() { awk -v b="$1" 'BEGIN { if (b ~ /^[0-9]+$/) printf "%.0f", b / 1048576; else printf "%s", b }'; }
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
memrec() { # name key: current/peak/anon in MiB
  local m; m="$(mem "$1")"
  rec "$2" "$(awk -v s="$m" 'BEGIN { n = split(s, f, " "); for (i = 1; i <= n; i++) { split(f[i], kv, "="); v = kv[2]; if (v ~ /^[0-9]+$/) v = sprintf("%.0f", v / 1048576); printf "%s%s=%s", (i > 1 ? " " : ""), kv[1], v } }')"
}
exercise() { # name: the checks on a ready profile
  local name=$1 peak_reload t
  rec "${name}_processes" "$(docker top "$name" -eo user,pid,comm | tail -n +2 | awk '{printf "%s:%s ", $1, $3}')"
  for t in $(seq 1 18); do
    [[ "$(docker inspect -f '{{.State.Health.Status}}' "$name")" == healthy ]] && break; sleep 5
  done
  rec "${name}_health" "$(docker inspect -f '{{.State.Health.Status}}' "$name")"
  rec "${name}_eicar_stream" "$(scan "$name" eicar)"
  rec "${name}_clean_1MiB_stream" "$(scan "$name" 1048576)"
  rec "${name}_clean_20MiB_stream" "$(scan "$name" 20971520)"
  rec "${name}_oversize_31MiB_stream" "$(scan "$name" 32505856)"
  memrec "$name" "${name}_memory_loaded_mib"
  peak_reload="$(reload_peak "$name")"
  rec "${name}_memory_reload_sampled_max_mib" "$(mib "$peak_reload")"
  memrec "$name" "${name}_memory_after_reload_mib"
  rec "${name}_oom_killed" "$(docker inspect -f '{{.State.OOMKilled}}' "$name")"
  rec "${name}_restart_count" "$(docker inspect -f '{{.RestartCount}}' "$name")"
  for t in $(seq 1 24); do
    docker exec "$name" sh -c 'grep -qiE "up-to-date|updated|is up to date" /var/log/clamav/freshclam.log 2>/dev/null' && break; sleep 5
  done
  rec "${name}_freshclam_log" "$(docker exec "$name" sh -c 'tail -n 3 /var/log/clamav/freshclam.log 2>/dev/null | tr "\n" " "' || echo 'no freshclam log')"
  rec "${name}_volume_after" "$(docker exec "$name" sh -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"')"
  rec "${name}_still_ready" "$(docker exec "$name" clamdcheck.sh 2>&1 | tr '\n' ' ')"
}

# --- profile compose: the deploy bundle's clamd service ---------------------------------------------------------------
note "profile compose: $DEPLOY/docker-compose.yml service clamd, as deploy.sh step 4c starts it, image $IMAGE"
if [[ ! -e /etc/veda/api.env ]]; then
  note "no /etc/veda/api.env on this host (not the staging host): creating an empty, readable one so Compose can load the file"
  sudo install -d -m 0755 /etc/veda && sudo install -m 0644 /dev/null /etc/veda/api.env
fi
export VEDA_CLAMD_IMAGE="$IMAGE"
if [[ "$MEMORY" != "$(get compose_mem_limit_default)" ]]; then export VEDA_CLAMD_MEM_LIMIT="$MEMORY"; fi
"${COMPOSE[@]}" config --quiet
rec compose_config "valid"
rec compose_rendered_clamd "$("${COMPOSE[@]}" config --format json | python3 -c '
import json, sys
c = json.load(sys.stdin)["services"]["clamd"]
print(json.dumps({k: c.get(k) for k in ("user", "entrypoint", "cap_drop", "cap_add", "privileged", "read_only", "security_opt", "tmpfs", "pids_limit", "mem_limit", "mem_reservation", "ports", "expose", "restart", "network_mode")}, separators=(",", ":")))')"
"${COMPOSE[@]}" up -d --no-deps clamd >/dev/null
rec compose_inspect "$(docker inspect -f 'user={{.Config.User}} entrypoint={{join .Config.Entrypoint " "}} cap_add={{.HostConfig.CapAdd}} cap_drop={{.HostConfig.CapDrop}} privileged={{.HostConfig.Privileged}} read_only={{.HostConfig.ReadonlyRootfs}} security_opt={{.HostConfig.SecurityOpt}} tmpfs={{.HostConfig.Tmpfs}} memory={{.HostConfig.Memory}} memory_reservation={{.HostConfig.MemoryReservation}} pids_limit={{.HostConfig.PidsLimit}} restart={{.HostConfig.RestartPolicy.Name}} network_mode={{.HostConfig.NetworkMode}} port_bindings={{.HostConfig.PortBindings}} published={{.NetworkSettings.Ports}}' "$CC")"
rec compose_mounts "$(docker inspect -f '{{range .Mounts}}{{.Type}}:{{.Source}}->{{.Destination}}:rw={{.RW}} {{end}}' "$CC" | sed "s|$REPO|<repo>|g")"
if ready_wait "$CC" 600 compose; then
  rec compose_identity "$(docker exec "$CC" id)"
  rec compose_dir_modes "$(docker exec "$CC" stat -c '%n=%a:%u:%g' /tmp /run/clamav /var/log/clamav /var/lib/clamav | tr '\n' ' ')"
  rec compose_tmpfs_mounts "$(docker exec "$CC" sh -c 'grep " tmpfs " /proc/mounts | grep -E " /(tmp|run/clamav|var/log/clamav) " | awk "{printf \"%s(%s) \", \$2, \$4}"')"
  rec compose_root_readonly "$(docker exec "$CC" sh -c 'if touch /etc/probe >/dev/null 2>&1; then echo WRITABLE; else echo "read-only root"; fi')"
  rec compose_conf_readonly "$(docker exec "$CC" sh -c 'if sh -c ">>/etc/clamav/clamd.conf" >/dev/null 2>&1; then echo WRITABLE; else echo read-only; fi')"
  rec compose_effective_conf "$(docker exec "$CC" sh -c 'grep -E "^(StreamMaxLength|MaxScanSize|MaxFileSize|MaxRecursion|ConcurrentDatabaseReload|ExitOnOOM|LogRotate|LogFileMaxSize|TemporaryDirectory)" /etc/clamav/clamd.conf | tr "\n" ";"')"
  rec compose_capabilities "$(docker exec "$CC" sh -c 'grep -E "^Cap(Eff|Prm|Bnd)" /proc/1/status | tr -s "\t" "=" | tr "\n" " "')"
  rec compose_no_new_privs "$(docker exec "$CC" sh -c 'grep NoNewPrivs /proc/1/status | tr -s "\t" "="')"
  exercise "$CC"
  # Restart behaviour: a Compose restart (what an operator does), measured to readiness.
  note "compose: restart (docker compose restart clamd)"
  t0=$(date +%s); "${COMPOSE[@]}" restart clamd >/dev/null
  if ready_wait "$CC" 300 compose_restart; then rec compose_restart_seconds "$(( $(date +%s) - t0 ))"; fi
  rec compose_restart_count_after_restart "$(docker inspect -f '{{.RestartCount}}' "$CC")"
  # Recovery: clamd killed inside the container (what ExitOnOOM, a crash or the kernel's OOM killer does). The
  # entrypoint must exit, Docker must restart the container, clamd must answer again.
  note "compose: kill -KILL clamd inside the container"
  before="$(docker inspect -f '{{.RestartCount}}' "$CC")"; t0=$(date +%s)
  docker exec "$CC" sh -c 'for p in /proc/[0-9]*; do [ "$(cat "$p/comm" 2>/dev/null)" = clamd ] && kill -KILL "${p#/proc/}"; done; true'
  sleep 15
  if ready_wait "$CC" 300 compose_after_clamd_killed; then rec compose_after_clamd_killed_seconds "$(( $(date +%s) - t0 ))"; fi
  rec compose_after_clamd_killed_restart_count "before=$before after=$(docker inspect -f '{{.RestartCount}}' "$CC") status=$(docker inspect -f '{{.State.Status}}' "$CC")"
  rec compose_after_clamd_killed_log "$(docker logs --since 5m "$CC" 2>&1 | grep -E "veda-clamd-init: clamd exited|starting clamd" | tail -n 3 | tr '\n' '|')"
  # Recovery: PID 1 killed from the host with SIGKILL (what the kernel's OOM killer or a crash of the entrypoint
  # looks like to Docker: an unexpected exit, not an operator stop); restart: unless-stopped must bring it back.
  note "compose: kill -KILL PID 1 from the host"
  before="$(docker inspect -f '{{.RestartCount}}' "$CC")"; t0=$(date +%s)
  sudo kill -KILL "$(docker inspect -f '{{.State.Pid}}' "$CC")"
  sleep 10
  if ready_wait "$CC" 300 compose_after_pid1_killed; then rec compose_after_pid1_killed_seconds "$(( $(date +%s) - t0 ))"; fi
  rec compose_after_pid1_killed_restart_count "before=$before after=$(docker inspect -f '{{.RestartCount}}' "$CC") status=$(docker inspect -f '{{.State.Status}}' "$CC")"
  # Operator kill through the Docker API: Docker records it as a manual stop, so the restart policy does not apply
  # (the same as docker stop); the health heartbeat then reports ScannerHealthy 0 and scanner-unhealthy alarms.
  note "compose: docker kill (SIGKILL through the Docker API; an operator action)"
  before="$(docker inspect -f '{{.RestartCount}}' "$CC")"
  docker kill "$CC" >/dev/null; sleep 20
  rec compose_after_docker_kill "status=$(docker inspect -f '{{.State.Status}}' "$CC") exit_code=$(docker inspect -f '{{.State.ExitCode}}' "$CC") restart_count before=$before after=$(docker inspect -f '{{.RestartCount}}' "$CC")"
  "${COMPOSE[@]}" up -d --no-deps clamd >/dev/null
  ready_wait "$CC" 300 compose_after_docker_kill_start || true
  # Rollback-shaped stop: a Compose stop (deploy.sh step 4c with scanner none runs rm -s -f) must stay stopped.
  note "compose: docker compose stop clamd (must not restart)"
  "${COMPOSE[@]}" stop clamd >/dev/null; sleep 20
  rec compose_after_stop "status=$(docker inspect -f '{{.State.Status}}' "$CC") exit_code=$(docker inspect -f '{{.State.ExitCode}}' "$CC")"
  rec compose_volume_after_stop "$(docker volume inspect -f '{{.Name}} {{.Driver}}' deploy_clamav-db 2>/dev/null || echo missing)"
  note "compose: start again (the volume is reused; signatures already updated)"
  t0=$(date +%s); "${COMPOSE[@]}" up -d --no-deps clamd >/dev/null
  if ready_wait "$CC" 300 compose_after_start; then rec compose_after_start_seconds "$(( $(date +%s) - t0 ))"; fi
  rec compose_after_start_volume "$(docker exec "$CC" sh -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"' 2>/dev/null || echo n/a)"
  rec compose_final_health "$(docker inspect -f '{{.State.Health.Status}}' "$CC")"
  rec compose_final_oom_killed "$(docker inspect -f '{{.State.OOMKilled}}' "$CC")"
  memrec "$CC" compose_final_memory_mib
fi
logs_tail "$CC"
"${COMPOSE[@]}" rm -s -f clamd >/dev/null 2>&1 || true
docker volume rm -f deploy_clamav-db >/dev/null 2>&1 || true

# --- profiles B and C: the non-root settings as a plain docker run, with the image's /init-unprivileged -----------
run_profile() { # name conf
  docker volume create "sv-vol-${1#sv-}" >/dev/null
  docker run -d --name "$1" --user 1000:1000 --entrypoint /init-unprivileged --read-only --cap-drop ALL \
    --security-opt no-new-privileges:true --tmpfs /tmp:mode=1777 --tmpfs /run/clamav:mode=1777 --tmpfs /var/log/clamav:mode=1777 \
    -v "sv-vol-${1#sv-}:/var/lib/clamav" -v "$2:/etc/clamav/clamd.conf:ro" \
    --memory "$MEMORY" --memory-reservation 1g -e CLAMAV_NO_MILTERD=true -e CLAMD_STARTUP_TIMEOUT=1800 \
    "${HEALTH[@]}" "$IMAGE" >/dev/null
}
note "profile B: /init-unprivileged as 1000:1000, no capability, read-only, tmpfs mode 1777, the bundle's clamd.conf (ConcurrentDatabaseReload no), limit $MEMORY"
run_profile sv-b "$DEPLOY/clamd.conf"
if ready_wait sv-b 900; then exercise sv-b; fi
logs_tail sv-b
docker rm -f sv-b >/dev/null

note "profile C: profile B with ConcurrentDatabaseReload yes, limit $MEMORY"
sed 's/^ConcurrentDatabaseReload no$/ConcurrentDatabaseReload yes/' "$DEPLOY/clamd.conf" >"$OUT/clamd-concurrent.conf"
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
    echo "## Scanner validation ($MEMORY)"; echo; echo "| Key | Value |"; echo "|---|---|"
    while IFS=$'\t' read -r k v; do printf '| %s | %s |\n' "$k" "$(printf '%s' "$v" | sed 's/|/\\|/g')"; done <"$RESULTS"
    echo; echo "summary.json sha256: $(sha256sum "$OUT/summary.json" | cut -d' ' -f1)"
  } >>"$GITHUB_STEP_SUMMARY"
fi
