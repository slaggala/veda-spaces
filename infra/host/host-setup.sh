#!/usr/bin/env bash
# Veda staging host setup (AUT-108, deployment wiring). Run as root by the veda-deploy SSM document before every
# deploy; idempotent. Arguments: <data volume device, e.g. /dev/sdf> <region> <cloudwatch agent configuration file>.
# 1. Mounts the encrypted data volume at /var/lib/veda (formats it only when it carries no filesystem).
# 2. Installs the pinned Docker Compose plugin (SHA-256 verified).
# 3. Loads the CloudWatch agent configuration shipped in the deploy bundle (infra/host/cloudwatch-agent.json) and starts
#    the agent. A file, not an SSM parameter: the plan role may read only /veda/staging/config (review R2).
# 4. Installs the health heartbeat (every minute: /health/ready -> Veda/Host HealthReady).
set -euo pipefail
DEVICE="${1:?data volume device}" REGION="${2:?region}" AGENT_CONFIG="${3:?agent configuration file}"
[[ -f "$AGENT_CONFIG" ]] || { echo "agent configuration $AGENT_CONFIG not found" >&2; exit 2; }
[[ "$DEVICE" =~ ^/dev/sd[f-p]$ ]] || { echo "invalid data device: $DEVICE" >&2; exit 2; }
COMPOSE_VERSION="v5.6.0"
COMPOSE_SHA256="733ec76717ceb59052a9609b9dadfb523b2df8eab57a54212872d10a58078ea2" # docker-compose-linux-aarch64 (published checksum)  # pragma: allowlist secret
MOUNT=/var/lib/veda
APP_UID=10001 # the veda user of the API image (api/deploy/Dockerfile)

mkdir -p /var/log/veda "$MOUNT"
exec > >(tee -a /var/log/veda/host-setup.log) 2>&1
echo "host-setup $(date -u +%FT%TZ) device=$DEVICE"

# 1. Data volume: the attachment device name, which Amazon Linux links to the NVMe device. Never the root disk.
for _ in $(seq 1 30); do [[ -e "$DEVICE" ]] && break; sleep 2; done
[[ -e "$DEVICE" ]] || { echo "data volume $DEVICE is not attached" >&2; exit 1; }
ROOT_DISK="$(lsblk -no PKNAME "$(findmnt -no SOURCE /)")"
[[ "$(basename "$(readlink -f "$DEVICE")")" != "$ROOT_DISK" ]] || { echo "$DEVICE is the root disk; refusing" >&2; exit 1; }
if ! blkid "$DEVICE" >/dev/null 2>&1; then
  echo "formatting the new data volume"
  mkfs.xfs -L veda-data "$DEVICE"
fi
UUID="$(blkid -s UUID -o value "$DEVICE")"
grep -q "UUID=$UUID" /etc/fstab || echo "UUID=$UUID $MOUNT xfs defaults,nofail,noatime 0 2" >>/etc/fstab
mountpoint -q "$MOUNT" || mount "$MOUNT"
mkdir -p "$MOUNT/snapshots"
chown "$APP_UID:$APP_UID" "$MOUNT" "$MOUNT/snapshots"

# 2. Docker Compose plugin, pinned.
PLUGIN=/usr/local/lib/docker/cli-plugins/docker-compose
if [[ ! -x "$PLUGIN" ]] || ! echo "$COMPOSE_SHA256  $PLUGIN" | sha256sum -c --status; then
  mkdir -p "$(dirname "$PLUGIN")"
  curl -fsSL -o "$PLUGIN.download" "https://github.com/docker/compose/releases/download/$COMPOSE_VERSION/docker-compose-linux-aarch64"
  echo "$COMPOSE_SHA256  $PLUGIN.download" | sha256sum -c --status || { echo "compose plugin checksum mismatch" >&2; rm -f "$PLUGIN.download"; exit 1; }
  install -m 0755 "$PLUGIN.download" "$PLUGIN" && rm -f "$PLUGIN.download"
fi
docker compose version

# 3. CloudWatch agent.
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c "file:$AGENT_CONFIG"

# 4. Health heartbeat.
install -m 0755 /opt/veda/host/health.sh /usr/local/bin/veda-health
cat >/etc/systemd/system/veda-health.service <<UNIT
[Unit]
Description=Veda staging health heartbeat (AUT-110)
[Service]
Type=oneshot
Environment=AWS_REGION=$REGION
ExecStart=/usr/local/bin/veda-health
UNIT
cat >/etc/systemd/system/veda-health.timer <<'UNIT'
[Unit]
Description=Veda staging health heartbeat every minute
[Timer]
OnBootSec=2min
OnUnitActiveSec=1min
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now veda-health.timer
echo "host-setup done"
