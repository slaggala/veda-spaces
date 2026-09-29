#!/usr/bin/env bash
# Secret scan of every tracked or new file (12 §5, IR-14). Fails on any candidate not in the reviewed
# baseline (.secrets.baseline at the repository root). Lockfiles, the OpenAPI snapshot and images are skipped.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
git ls-files -co --exclude-standard \
  | grep -vE '(package-lock\.json|requirements(-dev)?\.txt|openapi\.snapshot\.json|\.(jpg|jpeg|png|avif|ico|webp))$' \
  | xargs detect-secrets-hook --baseline .secrets.baseline
echo "secret scan: no new candidates"
