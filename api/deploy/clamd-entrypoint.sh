#!/bin/sh
# Catalog V3 scanner entrypoint (docker-compose.yml, service clamd; CATALOG-V3-scanner-implementation.md). Bind-mounted
# read-only into the official ClamAV image and run as uid 1000 (the image's clamav user). It follows the image's own
# /init-unprivileged step for step: no chown, no configuration rewrite, no capability, freshclam as a daemon, clamd in
# the foreground, the one-time signature download when the volume has none. One difference: /init-unprivileged ends in
# `exec tail -f /dev/null`, so a clamd that dies (ExitOnOOM, a crash, the kernel's OOM killer) leaves the container
# running and unhealthy for ever and Docker's restart policy never fires. This script stays PID 1, waits on clamd and
# exits with clamd's status, so `restart: unless-stopped` restarts the scanner, the restart count feeds Veda/Host
# ScannerRestarts and the health check reports the recovery. SIGTERM (docker stop) is forwarded to both daemons.
# Settings come from the bind-mounted clamd.conf and the image's freshclam.conf; the environment is read for
# FRESHCLAM_CHECKS (signature checks per day) and CLAMAV_NO_FRESHCLAMD only.
set -eu

DB=/var/lib/clamav
# A volume with no signatures (never one Docker initialised from the image, which ships them): download once before
# clamd starts, as /init-unprivileged does; clamd refuses to start without a database.
if [ ! -f "$DB/main.cvd" ] && [ ! -f "$DB/main.cld" ]; then
  echo "veda-clamd-init: no signature database under $DB; downloading before clamd starts"
  sed -e 's|^\(TestDatabases \)|#\1|' -e '$a TestDatabases no' -e 's|^\(NotifyClamd \)|#\1|' \
    /etc/clamav/freshclam.conf >/tmp/freshclam-initial.conf
  freshclam --foreground --stdout --config-file=/tmp/freshclam-initial.conf
  rm -f /tmp/freshclam-initial.conf
fi
rm -f /tmp/clamd.sock

freshclam_pid=""
if [ "${CLAMAV_NO_FRESHCLAMD:-false}" != "true" ]; then
  echo "veda-clamd-init: starting freshclam (daemon, ${FRESHCLAM_CHECKS:-1} check(s) per day)"
  freshclam --checks="${FRESHCLAM_CHECKS:-1}" --daemon --foreground --stdout &
  freshclam_pid=$!
fi
echo "veda-clamd-init: starting clamd (foreground; configuration /etc/clamav/clamd.conf)"
clamd --foreground &
clamd_pid=$!

# shellcheck disable=SC2329 # invoked by the trap below
stop() {
  echo "veda-clamd-init: stop requested; terminating clamd and freshclam"
  kill -TERM "$clamd_pid" 2>/dev/null || true
  if [ -n "$freshclam_pid" ]; then kill -TERM "$freshclam_pid" 2>/dev/null || true; fi
}
trap stop TERM INT

rc=0
wait "$clamd_pid" || rc=$?
# A trapped signal interrupts wait (status above 128): wait once more for clamd itself to end.
if [ "$rc" -gt 128 ]; then rc=0; wait "$clamd_pid" || rc=$?; fi
echo "veda-clamd-init: clamd exited with status $rc; exiting so that Docker's restart policy applies"
if [ -n "$freshclam_pid" ]; then
  kill -TERM "$freshclam_pid" 2>/dev/null || true
  wait "$freshclam_pid" 2>/dev/null || true
fi
exit "$rc"
