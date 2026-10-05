# Deployment wiring (AUT-108/AUT-301 follow-up): the SSM document veda-deploy, the only way code reaches the host. The
# bootstrap's veda-gh-deploy role may run it (and only on the instance tagged project=veda-spaces, env=staging); the
# 12-deploy workflow calls it after building, pushing and scanning the image and uploading the bundle. Each step uses
# what the reviewed commit shipped: the bundle (api/deploy and infra/host) is verified by SHA-256, the image is pulled
# by digest, and the existing deploy.sh runs its floors, snapshot, migration and readiness gate (02 §12.4).

resource "aws_ssm_document" "deploy" {
  name            = "${var.name_prefix}-deploy"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Deploy a Veda release to the staging host (bundle verified by SHA-256, image by digest)"
    parameters = {
      releaseTag   = { type = "String", description = "Release tag (the image tag)", allowedPattern = "^[0-9a-f]{12}$|^r[0-9]+(\\.[0-9]+){0,2}$" }
      imageDigest  = { type = "String", description = "Image digest pushed by 12-deploy", allowedPattern = "^sha256:[0-9a-f]{64}$" }
      bundleSha256 = { type = "String", description = "SHA-256 of deploy/<tag>/bundle.tgz", allowedPattern = "^[0-9a-f]{64}$" }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "deploy"
      inputs = {
        timeoutSeconds = "1800"
        runCommand = [
          "set -euo pipefail",
          "TAG='{{ releaseTag }}' DIGEST='{{ imageDigest }}' SUM='{{ bundleSha256 }}'",
          "REL=/opt/veda/releases/$TAG; mkdir -p \"$REL\" /var/log/veda",
          "exec > >(tee -a /var/log/veda/deploy.log) 2>&1",
          "echo \"veda-deploy $TAG $(date -u +%FT%TZ)\"",
          "aws s3 cp --region ${var.region} \"s3://${var.artifacts_bucket}/deploy/$TAG/bundle.tgz\" \"$REL.tgz\"",
          "echo \"$SUM  $REL.tgz\" | sha256sum -c -",
          "tar -xzf \"$REL.tgz\" -C \"$REL\"",
          "install -d /opt/veda/host && install -m 0755 \"$REL\"/infra/host/*.sh /opt/veda/host/",
          "/opt/veda/host/host-setup.sh ${var.data_device} ${var.region} ${var.agent_config_parameter}",
          "/opt/veda/host/render-env.sh ${var.region}",
          "aws ecr get-login-password --region ${var.region} | docker login --username AWS --password-stdin ${split("/", var.repository_url)[0]}",
          "docker pull \"${var.repository_url}@$DIGEST\"",
          "docker tag \"${var.repository_url}@$DIGEST\" \"veda-api:$TAG\"",
          "cd \"$REL/api/deploy\" && ./deploy.sh \"$TAG\"",
        ]
      }
    }]
  })
}

# Evidence collection (AUT-401 foundation): veda-collect, run by the bootstrap's veda-gh-evidence role (13-evidence)
# on the staging host only. It records facts, never secrets or personal data: versions, image digests, container
# state, readiness and schema state (read inside the API container), listening sockets (only loopback listeners may
# exist), the data volume mount, disk use, the timers, the tail of the deploy log. The tarball and a manifest of
# SHA-256 hashes go to the evidence bucket (COMPLIANCE lock by default, AUT-103); /etc/veda/api.env is never read.
resource "aws_ssm_document" "collect" {
  name            = "${var.name_prefix}-collect"
  document_type   = "Command"
  document_format = "JSON"

  content = jsonencode({
    schemaVersion = "2.2"
    description   = "Collect Veda staging host evidence into the evidence bucket (no secrets, no personal data)"
    parameters = {
      label = { type = "String", description = "Evidence label (e.g. e2e-lead-flow)", allowedPattern = "^[a-z0-9][a-z0-9-]{0,39}$" }
    }
    mainSteps = [{
      action = "aws:runShellScript"
      name   = "collect"
      inputs = {
        timeoutSeconds = "600"
        runCommand = [
          "set -uo pipefail",
          "LABEL='{{ label }}'; TS=$(date -u +%Y%m%dT%H%M%SZ); D=$(mktemp -d); cd \"$D\"",
          "TOKEN=$(curl -sS -m 2 -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60'); IID=$(curl -sS -m 2 -H \"X-aws-ec2-metadata-token: $TOKEN\" http://169.254.169.254/latest/meta-data/instance-id)",
          "{ date -u +%FT%TZ; uname -a; cat /etc/os-release; rpm -q docker amazon-cloudwatch-agent amazon-ssm-agent; } >host.txt 2>&1",
          "{ docker version; docker compose version; docker images --digests; docker ps -a; } >containers.txt 2>&1",
          "API=$(docker ps -q -f name=api | head -1); if [ -n \"$API\" ]; then docker exec \"$API\" python -c 'import urllib.request;print(urllib.request.urlopen(\"http://127.0.0.1:8000/health/ready\",timeout=5).read().decode())' >ready.json 2>&1; docker exec \"$API\" python -m veda.cli schema-status >schema.json 2>&1; else echo 'api container not running' >ready.json; fi",
          "{ ss -lntu; } >listeners.txt 2>&1",
          "{ findmnt /var/lib/veda; df -h; } >storage.txt 2>&1",
          "{ systemctl list-timers veda-health.timer --no-pager; /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a status; } >services.txt 2>&1",
          "tail -n 200 /var/log/veda/deploy.log >deploy-log-tail.txt 2>/dev/null || echo 'no deploy yet' >deploy-log-tail.txt",
          "sha256sum *.txt *.json >MANIFEST.sha256",
          "tar -czf \"/tmp/$LABEL-$TS.tgz\" -C \"$D\" .",
          "SUM=$(sha256sum \"/tmp/$LABEL-$TS.tgz\" | cut -d' ' -f1); KEY=\"host/$(date -u +%Y-%m-%d)/$IID/$LABEL-$TS.tgz\"",
          "aws s3 cp --region ${var.region} \"/tmp/$LABEL-$TS.tgz\" \"s3://${var.evidence_bucket}/$KEY\" --metadata \"sha256=$SUM\"",
          "rm -rf \"$D\" \"/tmp/$LABEL-$TS.tgz\"",
          "echo \"evidence s3://${var.evidence_bucket}/$KEY sha256 $SUM\"",
        ]
      }
    }]
  })
}
