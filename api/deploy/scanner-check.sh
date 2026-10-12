#!/usr/bin/env bash
# Catalog V3 scanner probe (CATALOG-V3-scanner-implementation.md): readiness and health of the clamd service, read on
# the host from the deploy directory. Changes nothing. Exit 0 only when the container runs, Docker reports it healthy
# and clamd answers PING; every other state is named in plain words and exits 1.
#   ./scanner-check.sh
set -uo pipefail
cd "$(dirname "$0")" || exit 1
COMPOSE=(docker compose -f docker-compose.yml --profile scanner)
id="$("${COMPOSE[@]}" ps -a -q clamd 2>/dev/null | head -n 1)"
if [[ -z "$id" ]]; then
  echo "scanner: no clamd container (VEDA_CATALOG_MEDIA_SCANNER is not clamd, or deploy.sh has not started it)"
  exit 1
fi
docker inspect -f 'container={{.Name}} status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restarts={{.RestartCount}} oom_killed={{.State.OOMKilled}} started={{.State.StartedAt}}
image={{.Config.Image}}
user={{.Config.User}} read_only={{.HostConfig.ReadonlyRootfs}} privileged={{.HostConfig.Privileged}} cap_add={{.HostConfig.CapAdd}} cap_drop={{.HostConfig.CapDrop}} memory_limit_bytes={{.HostConfig.Memory}} published_ports={{.NetworkSettings.Ports}}' "$id"
status="$(docker inspect -f '{{.State.Status}}' "$id")"
health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$id")"
if [[ "$status" != running ]]; then
  echo "scanner: NOT RUNNING ($status); Docker restarts it unless it was stopped on purpose (restart: unless-stopped)"
  exit 1
fi
# Readiness: PING over the TCP socket the API uses (clamd:3310), from inside the container's network namespace.
if ! pong="$(docker exec "$id" sh -c 'printf "zPING\0" | nc -w 5 localhost 3310' 2>/dev/null | tr -d '\0\n ')" || [[ "$pong" != PONG ]]; then
  echo "scanner: NOT READY (no PONG from clamd:3310; health=$health); uploads would stay FAILED and are never served"
  exit 1
fi
echo "ready: PONG"
echo "version: $(docker exec "$id" sh -c 'printf "zVERSION\0" | nc -w 5 localhost 3310' 2>/dev/null | tr -d '\0\n')"
echo "memory: $(docker exec "$id" sh -c 'printf "current=%s peak=%s" "$(cat /sys/fs/cgroup/memory.current)" "$(cat /sys/fs/cgroup/memory.peak 2>/dev/null || echo n/a)"' 2>/dev/null)"
echo "signatures: $(docker exec "$id" sh -c 'ls -l /var/lib/clamav | awk "/\\.c[vl]d\$/ {printf \"%s=%s \", \$NF, \$5}"' 2>/dev/null)"
echo "freshclam: $(docker exec "$id" sh -c 'tail -n 2 /var/log/clamav/freshclam.log 2>/dev/null | tr "\n" " "' 2>/dev/null)"
if [[ "$health" != healthy ]]; then
  echo "scanner: answering but Docker health is $health (starting, or clamdcheck.sh failing); check again in a minute"
  exit 1
fi
echo "healthy"
