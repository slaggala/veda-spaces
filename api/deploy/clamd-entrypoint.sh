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
# FRESHCLAM_CHECKS (signature checks per day) and CLAMAV_NO_FRESHCLAMD only (CLAMAV_DB_DIR and FRESHCLAM_CONF exist
# for the unit test that runs this script with stub daemons; the image's paths are the defaults).
set -eu

DB="${CLAMAV_DB_DIR:-/var/lib/clamav}"
FRESHCLAM_CONF="${FRESHCLAM_CONF:-/etc/clamav/freshclam.conf}"
# A volume with no signatures (never one Docker initialised from the image, which ships them): download once before
# clamd starts, as /init-unprivileged does; clamd refuses to start without a database.
if [ ! -f "$DB/main.cvd" ] && [ ! -f "$DB/main.cld" ]; then
  echo "veda-clamd-init: no signature database under $DB; downloading before clamd starts"
  sed -e 's|^\(TestDatabases \)|#\1|' -e '$a TestDatabases no' -e 's|^\(NotifyClamd \)|#\1|' \
    "$FRESHCLAM_CONF" >/tmp/freshclam-initial.conf
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

# The flag is set by the trap itself, never inferred from an exit status: clamd killed by a signal also ends with a
# status above 128, and that case must stop freshclam and exit (the fourth validation run caught the inference bug).
signalled=0
# shellcheck disable=SC2329 # invoked by the trap below
stop() {
  signalled=1
  echo "veda-clamd-init: stop requested; terminating clamd and freshclam"
  kill -TERM "$clamd_pid" 2>/dev/null || true
  if [ -n "$freshclam_pid" ]; then kill -TERM "$freshclam_pid" 2>/dev/null || true; fi
}
trap stop TERM INT

rc=0
wait "$clamd_pid" || rc=$?
# A trapped signal interrupts wait: wait once more for clamd itself to end (its own status is the exit status).
if [ "$signalled" -eq 1 ]; then rc=0; wait "$clamd_pid" || rc=$?; fi
echo "veda-clamd-init: clamd exited with status $rc; exiting so that Docker's restart policy applies"
if [ -n "$freshclam_pid" ]; then
  # clamd ended on its own (crash, ExitOnOOM, the OOM killer): stop freshclam; after a trapped signal it was told already.
  if [ "$signalled" -eq 0 ]; then kill -TERM "$freshclam_pid" 2>/dev/null || true; fi
  wait "$freshclam_pid" 2>/dev/null || true
fi
exit "$rc"
