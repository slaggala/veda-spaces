# host

Files placed on the staging EC2 host by cloud-init (AUT-109): `cloud-init.yaml`, `docker-daemon.json`
(address pool 172.30.0.0/16 so the compose gateway is 172.30.0.1; awslogs driver, non-blocking),
`cwagent.json`, `cloudflared.service`, `render-env.sh`, `pull-and-tag.sh`. Not created yet.
`api/deploy/` is used unchanged; nothing here edits it.
