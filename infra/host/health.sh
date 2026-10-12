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
# Catalog V3 media scanner (targeted media enablement; CATALOG-V3-scanner-implementation.md): the clamd container's
# restart count and whether Docker reports it healthy, only when it exists (the scanner service starts only after the
# owner's scanner decision). Repeated restarts alarm (scanner-restarts); a running container that stops answering
# alarms (scanner-unhealthy). ScannerHealthy is 1 when the container runs and its health check passes, else 0.
state="$(docker inspect -f '{{.RestartCount}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' deploy-clamd-1 2>/dev/null || true)"
read -r restarts status health <<<"$state"
if [[ "${restarts:-}" =~ ^[0-9]+$ ]]; then
  aws cloudwatch put-metric-data --region "${AWS_REGION:-ap-south-1}" --namespace Veda/Host --metric-name ScannerRestarts \
    --dimensions "InstanceId=$INSTANCE" --value "$restarts" --unit Count
  healthy=0
  [[ "$status" == running && "$health" == healthy ]] && healthy=1
  aws cloudwatch put-metric-data --region "${AWS_REGION:-ap-south-1}" --namespace Veda/Host --metric-name ScannerHealthy \
    --dimensions "InstanceId=$INSTANCE" --value "$healthy" --unit Count
fi
