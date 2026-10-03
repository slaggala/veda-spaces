#!/usr/bin/env bash
# Install, or verify, the pinned tools of `make -C infra check` (RD-02).
#
#   infra/scripts/install-tools.sh [--dir infra/.tools]      # download, check SHA-256, install
#   infra/scripts/install-tools.sh --verify [--dir …]        # the tools on PATH are exactly the pinned versions
#
# Versions and SHA-256 digests: infra/tools/tools.lock (terraform, tflint, shellcheck, actionlint) and
# infra/tools/requirements-checkov.txt (checkov and every dependency, hash-locked; Python 3.13). A download whose
# digest differs is refused and nothing is installed from it. CI (linux/amd64) and a workstation (linux or macOS,
# amd64 or arm64) therefore run the same tools, so a pass in CI is reproducible on a clean workstation.
#
# Installs into <dir>/bin (gitignored); `make -C infra` puts that directory first on PATH. Needs curl, tar, unzip
# and python3 (3.13 for checkov). It touches no AWS, GitHub or Cloudflare account.
set -euo pipefail
# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

LOCK="$INFRA_DIR/tools/tools.lock"
CHECKOV_REQUIREMENTS="$INFRA_DIR/tools/requirements-checkov.txt"
DIR="$INFRA_DIR/.tools"
VERIFY=0
while (($#)); do
  case "$1" in
    --dir) DIR="${2:-}"; shift 2 ;;
    --verify) VERIFY=1; shift ;;
    -h | --help) sed -n '2,14p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

# The pinned version of a tool, from the lock.
pinned() { awk -v t="$1" '$1 == t { print $2; exit }' "$LOCK"; }

# The version a tool on PATH reports, normalised to the lock's form ("" if missing or unreadable).
installed_version() {
  local out
  case "$1" in
    terraform) out="$(terraform version -json 2>/dev/null | jq -r '.terraform_version // empty' 2>/dev/null)" ;;
    tflint) out="$(tflint --version 2>/dev/null | sed -nE 's/^TFLint version ([0-9.]+).*/\1/p' | head -n 1)" ;;
    shellcheck) out="$(shellcheck --version 2>/dev/null | sed -nE 's/^version: ([0-9.]+).*/\1/p')" ;;
    actionlint) out="$(actionlint -version 2>/dev/null | head -n 1)" ;;
    checkov) out="$(checkov --version 2>/dev/null | tail -n 1)" ;;
  esac
  printf '%s' "${out:-}"
}

TOOLS="terraform tflint shellcheck actionlint checkov"

if ((VERIFY)); then
  require_tools jq
  [[ -d "$DIR/bin" ]] && export PATH="$DIR/bin:$PATH"
  problems=()
  for t in $TOOLS; do
    want="$(pinned "$t")"
    [[ -n "$want" ]] || { problems+=("$t: not in $LOCK"); continue; }
    have="$(installed_version "$t")"
    if [[ -z "$have" ]]; then
      problems+=("$t: not installed (want $want)")
    elif [[ "$have" != "$want" ]]; then
      problems+=("$t: $have installed, $want pinned")
    else
      log "$t $have (pinned)"
    fi
  done
  if ((${#problems[@]})); then
    for p in "${problems[@]}"; do log "TOOL: $p"; done
    die "the infra check tools are not the pinned versions (${#problems[@]} problem(s)); run infra/scripts/install-tools.sh"
  fi
  log "every infra check tool is the pinned version"
  exit 0
fi

require_tools curl tar unzip python3
case "$(uname -s)" in
  Linux) OS=linux ;;
  Darwin) OS=darwin ;;
  *) die "unsupported OS $(uname -s): use linux or macOS" ;;
esac
case "$(uname -m)" in
  x86_64 | amd64) ARCH=amd64 ;;
  arm64 | aarch64) ARCH=arm64 ;;
  *) die "unsupported architecture $(uname -m): use amd64 or arm64" ;;
esac

sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

mkdir -p "$DIR/bin"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for t in terraform tflint shellcheck actionlint; do
  read -r version sum url < <(awk -v t="$t" -v o="$OS" -v a="$ARCH" '$1 == t && $3 == o && $4 == a { print $2, $5, $6 }' "$LOCK")
  [[ -n "${url:-}" ]] || die "$t: no pinned download for $OS/$ARCH in $LOCK"
  if [[ "$(installed_version "$t")" == "$version" && -x "$DIR/bin/$t" ]]; then
    log "$t $version already installed"
    continue
  fi
  file="$WORK/$(basename "$url")"
  log "$t $version: downloading $url"
  curl -fsSL --retry 3 -o "$file" "$url" || die "$t: download failed"
  got="$(sha256 "$file")"
  [[ "$got" == "$sum" ]] || die "$t: SHA-256 $got does not match the pinned $sum; refusing to install"
  mkdir -p "$WORK/$t"
  case "$file" in
    *.zip) unzip -q -o "$file" -d "$WORK/$t" ;;
    *.tar.gz) tar -xzf "$file" -C "$WORK/$t" ;;
    *) die "$t: unknown archive type $file" ;;
  esac
  bin="$(find "$WORK/$t" -type f -name "$t" | head -n 1)"
  [[ -n "$bin" ]] || die "$t: binary not found in $file"
  install -m 0755 "$bin" "$DIR/bin/$t"
  log "$t $version installed (SHA-256 verified)"
done

want="$(pinned checkov)"
py="${PYTHON:-python3}"
"$py" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)' ||
  die "checkov's lock is for Python 3.13; set PYTHON to a 3.13 interpreter (got $("$py" --version 2>&1))"
if [[ "$(PATH="$DIR/bin:$PATH" installed_version checkov)" != "$want" ]]; then
  log "checkov $want: installing from the hash-locked requirements"
  "$py" -m venv "$DIR/checkov"
  "$DIR/checkov/bin/python" -m pip install --quiet --disable-pip-version-check --no-deps --require-hashes \
    -r "$CHECKOV_REQUIREMENTS" || die "checkov: hash-locked install failed"
  ln -sf "../checkov/bin/checkov" "$DIR/bin/checkov"
fi
log "tools installed in $DIR/bin; verifying"
exec "$0" --verify --dir "$DIR"
