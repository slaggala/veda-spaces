# host

Scripts the `veda-deploy` SSM document runs on the staging host, as root, from the deploy bundle of the reviewed
commit (12-deploy uploads `api/deploy` and `infra/host` with their SHA-256; the document verifies it):

| Script | What it does |
|---|---|
| `host-setup.sh` | Mounts the encrypted data volume at `/var/lib/veda` (formats it only when it carries no filesystem), installs the pinned Docker Compose plugin (SHA-256 verified), loads the CloudWatch agent configuration from SSM, installs the health heartbeat timer. Idempotent |
| `render-env.sh` | Renders `/etc/veda/api.env` (0600) from `/veda/staging/config/*` and the owner-seeded `/veda/staging/app/*` (AUT-302); refuses while a required secret is missing |
| `cloudwatch-agent.json` | The CloudWatch agent configuration (memory, the two disks, the host logs), loaded by `host-setup.sh` from the verified bundle. Not an SSM parameter: the plan role may read only `/veda/staging/config` (review R2) |
| `render-edge.sh` | Called by `render-env.sh`. Renders the Cloudflare tunnel (AUT-201) from the owner-seeded `/veda/staging/edge` parameters: `/etc/veda/cloudflared/tunnel.env` (0600, the token) and `config.yml` (from `cloudflared.yml`, for the API host of `api.env`). With none seeded it removes both; partial or malformed refuses |
| `cloudflared.yml` | The tunnel ingress: the API host to `http://127.0.0.1:8000` with **Cloudflare Access required** at the origin (team and AUD tag), every other host 404, metrics on `127.0.0.1:20241` |
| `health.sh` | Every minute: `Veda/Host HealthReady` = 1 when `/health/ready` answers on `127.0.0.1:8000`, else 0 |

The boot script (cloud-init `user_data`, `modules/compute`) installs Docker and the CloudWatch agent and writes the
Docker daemon configuration: address pool `172.30.0.0/16` (so the Compose network gateway, the peer the API sees,
is `172.30.0.1`: `VEDA_TRUSTED_PROXY_CIDRS`) and the non-blocking `awslogs` driver. `api/deploy/` is used unchanged;
nothing here edits it, except that AUT-201 adds the opt-in `cloudflared` service (profile `edge`, host network,
image pinned by digest) and `deploy.sh` step 7, which starts it only from a rendered configuration requiring Access.
