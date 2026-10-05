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
