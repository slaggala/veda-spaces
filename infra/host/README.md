# host

Scripts the `veda-deploy` SSM document runs on the staging host, as root, from the deploy bundle of the reviewed
commit (12-deploy uploads `api/deploy` and `infra/host` with their SHA-256; the document verifies it):

| Script | What it does |
|---|---|
| `host-setup.sh` | Mounts the encrypted data volume at `/var/lib/veda` (formats it only when it carries no filesystem), installs the pinned Docker Compose plugin (SHA-256 verified), loads the CloudWatch agent configuration from SSM, installs the health heartbeat timer. Idempotent |
| `render-env.sh` | Renders `/etc/veda/api.env` (0600) from `/veda/staging/config/*` and the owner-seeded `/veda/staging/app/*` (AUT-302); refuses while a required secret is missing |
| `cloudwatch-agent.json` | The CloudWatch agent configuration (memory, the two disks, the host logs), loaded by `host-setup.sh` from the verified bundle. Not an SSM parameter: the plan role may read only `/veda/staging/config` (review R2) |
| `health.sh` | Every minute: `Veda/Host HealthReady` = 1 when `/health/ready` answers on `127.0.0.1:8000`, else 0 |

The boot script (cloud-init `user_data`, `modules/compute`) installs Docker and the CloudWatch agent and writes the
Docker daemon configuration: address pool `172.30.0.0/16` (so the Compose network gateway, the peer the API sees,
is `172.30.0.1`: `VEDA_TRUSTED_PROXY_CIDRS`) and the non-blocking `awslogs` driver. `api/deploy/` is used unchanged;
nothing here edits it. `cloudflared` arrives with AUT-201.
