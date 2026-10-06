#!/usr/bin/env bash
# Render the Cloudflare tunnel (AUT-201) from SSM /veda/staging/edge, which the owner seeds (never Terraform):
#   CLOUDFLARED_TOKEN   SecureString (data key)  the token of the locally managed tunnel veda-staging
#   ACCESS_TEAM_NAME    String                   the Cloudflare Zero Trust team name (<team>.cloudflareaccess.com)
#   ACCESS_AUD          String                   the Application Audience (AUD) tag of the staging Access application
# Writes /etc/veda/cloudflared/tunnel.env (0600, the token) and config.yml (0644, from cloudflared.yml, for the API
# host of /etc/veda/api.env). None seeded: removes both, so deploy.sh keeps the tunnel stopped. Some but not all, an
# unexpected name or a malformed value: refuses and leaves the previous files in place. Run as root by render-env.sh.
set -euo pipefail
REGION="${1:?region}"
EDGE_PATH=/veda/staging/edge
ETC=/etc/veda
OUT_DIR="$ETC/cloudflared"
TEMPLATE="$(dirname "$0")/cloudflared.yml"

params="$(aws ssm get-parameters-by-path --region "$REGION" --path "$EDGE_PATH" --recursive --with-decryption --output json)"
names="$(jq -r '[.Parameters[].Name | split("/") | last] | sort | join(" ")' <<<"$params")"
value() { jq -r --arg n "$EDGE_PATH/$1" '.Parameters[] | select(.Name == $n) | .Value' <<<"$params"; }

if [[ -z "$names" ]]; then
  rm -f "$OUT_DIR/tunnel.env" "$OUT_DIR/config.yml"
  echo "edge not configured: no parameter under $EDGE_PATH; the tunnel stays stopped"
  exit 0
fi
for n in $names; do
  [[ "$n" =~ ^(CLOUDFLARED_TOKEN|ACCESS_TEAM_NAME|ACCESS_AUD)$ ]] || { echo "refusing: unexpected parameter $EDGE_PATH/$n" >&2; exit 1; }
done
[[ "$names" == "ACCESS_AUD ACCESS_TEAM_NAME CLOUDFLARED_TOKEN" ]] ||
  { echo "refusing: $EDGE_PATH needs CLOUDFLARED_TOKEN, ACCESS_TEAM_NAME and ACCESS_AUD (has: $names)" >&2; exit 1; }
[[ "$(jq -r --arg n "$EDGE_PATH/CLOUDFLARED_TOKEN" '.Parameters[] | select(.Name == $n) | .Type' <<<"$params")" == SecureString ]] ||
  { echo "refusing: $EDGE_PATH/CLOUDFLARED_TOKEN must be a SecureString" >&2; exit 1; }

TOKEN="$(value CLOUDFLARED_TOKEN)" TEAM="$(value ACCESS_TEAM_NAME)" AUD="$(value ACCESS_AUD)"
[[ "$TOKEN" =~ ^[A-Za-z0-9+/=_-]{40,}$ ]] || { echo "refusing: CLOUDFLARED_TOKEN is not a tunnel token" >&2; exit 1; }
[[ "$TEAM" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] || { echo "refusing: ACCESS_TEAM_NAME must be the team name only (no domain)" >&2; exit 1; }
[[ "$AUD" =~ ^[0-9a-f]{64}$ ]] || { echo "refusing: ACCESS_AUD must be the 64-hex Application Audience tag" >&2; exit 1; }
API_URL="$(sed -nE 's/^VEDA_API_BASE_URL="?([^"]*)"?$/\1/p' "$ETC/api.env" 2>/dev/null || true)"
[[ "$API_URL" =~ ^https://([a-z0-9.-]+\.vedaspaces\.com)$ ]] ||
  { echo "refusing: VEDA_API_BASE_URL in $ETC/api.env is not an https vedaspaces.com host (got '$API_URL')" >&2; exit 1; }
HOST="${BASH_REMATCH[1]}"

umask 077
mkdir -p "$OUT_DIR"
tmp_env="$(mktemp "$OUT_DIR/tunnel.env.XXXXXX")" tmp_cfg="$(mktemp "$OUT_DIR/config.yml.XXXXXX")"
trap 'rm -f "$tmp_env" "$tmp_cfg"' EXIT
printf 'TUNNEL_TOKEN=%s\n' "$TOKEN" >"$tmp_env"
sed -e "s/__API_HOST__/$HOST/" -e "s/__ACCESS_TEAM_NAME__/$TEAM/" -e "s/__ACCESS_AUD__/$AUD/" "$TEMPLATE" >"$tmp_cfg"
# The rendered configuration must still require Access on the API host and end with the 404 catch-all.
if ! grep -q "^        required: true$" "$tmp_cfg" || grep -q "__[A-Z_]*__" "$tmp_cfg" ||
  ! tail -n 1 "$tmp_cfg" | grep -q "service: http_status:404"; then
  echo "refusing: the rendered tunnel configuration does not require Access" >&2
  exit 1
fi
chmod 0600 "$tmp_env"
chmod 0644 "$tmp_cfg"
mv "$tmp_env" "$OUT_DIR/tunnel.env"
mv "$tmp_cfg" "$OUT_DIR/config.yml"
trap - EXIT
echo "rendered the tunnel for $HOST (Access required: team $TEAM)"
