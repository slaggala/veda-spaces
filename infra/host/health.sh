#!/usr/bin/env bash
# Health heartbeat (AUT-110): 1 when the API answers /health/ready on the loopback, else 0. The alarm treats a missing
# value as an outage, so a stopped timer or host also alarms.
set -uo pipefail
TOKEN="$(curl -sS -m 2 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')"
INSTANCE="$(curl -sS -m 2 -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/instance-id)"
value=0
curl -fsS -m 5 -o /dev/null http://127.0.0.1:8000/health/ready && value=1
aws cloudwatch put-metric-data --region "${AWS_REGION:-ap-south-1}" --namespace Veda/Host --metric-name HealthReady \
  --dimensions "InstanceId=$INSTANCE" --value "$value" --unit Count
# Catalog V3 media scanner (targeted media enablement): the clamd container's restart count, only when it runs (the
# scanner service starts only after the owner's scanner decision). Repeated restarts alarm (scanner-restarts).
restarts="$(docker inspect -f '{{.RestartCount}}' deploy-clamd-1 2>/dev/null || true)"
if [[ "$restarts" =~ ^[0-9]+$ ]]; then
  aws cloudwatch put-metric-data --region "${AWS_REGION:-ap-south-1}" --namespace Veda/Host --metric-name ScannerRestarts \
    --dimensions "InstanceId=$INSTANCE" --value "$restarts" --unit Count
fi
