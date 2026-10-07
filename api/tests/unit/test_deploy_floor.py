"""FC-12: deploy.sh enforces the release floor and the schema floor in every mode (runbook §2.1).

docker and curl are replaced by shims on PATH: each fake image answers `veda schema-status` the way a real image of
that release would. Nothing here deploys anything; no rollback rehearsal is claimed (RG-7 stays open).
"""

import json
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[2] / "deploy" / "deploy.sh"

# tag → how its `schema-status --require-known 0009_mfa_challenge_binding` answers
IMAGES = {
    "at-floor": {"release": 3, "floor_known": True, "state": "head"},
    "above-floor": {"release": 4, "floor_known": True, "state": "head"},
    "2f6b59a": {"legacy": True},  # predates schema-status: argparse error, exit 2
    "9236aa3": {"legacy": True},
    "old-release": {"release": 2, "floor_known": True, "state": "head"},
    "schema-unknown": {"release": 3, "floor_known": False, "state": "ahead_undeclared"},
    "no-release": {"release": None, "floor_known": True, "state": "head"},
    "string-release": {"release": "3", "floor_known": True, "state": "head"},
    "garbage": {"raw": "not json at all"},
}

DOCKER = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    args = sys.argv[1:]
    log = open(os.environ["SHIM_LOG"], "a"); log.write(" ".join(args) + "\\n"); log.close()
    image = json.loads(os.environ["SHIM_IMAGES"])[os.environ["VEDA_IMAGE_TAG"]]
    if "schema-status" in args:
        if image.get("legacy"):
            print("veda: error: argument command: invalid choice: 'schema-status'", file=sys.stderr); sys.exit(2)
        if "raw" in image:
            print(image["raw"]); sys.exit(0)
        out = {"current": "0009_mfa_challenge_binding", "image_head": "x", "state": image["state"], "release": image["release"]}
        if "--require-known" in args:
            out["floor_known"] = image["floor_known"]
        print(json.dumps(out)); sys.exit(0 if image["floor_known"] or "--require-known" not in args else 4)
    if "generations" in args:
        print("name  generation  lag  start  end")
        for g in filter(None, os.environ.get("SHIM_GENERATIONS", "").split(",")):
            print(f"s3    {g}  0s   2026-10-01T00:00:00Z  2026-10-06T00:00:00Z")
        sys.exit(int(os.environ.get("SHIM_GENERATIONS_EXIT", "0")))
    if "exec" in args:
        print('{"status": "ok", "checks": {"migrations": "head"}}'); sys.exit(0)
    print("{}")
    """
)


@pytest.fixture
def deploy(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "docker").write_text(DOCKER)
    # Litestream metrics answer only once it has been started (SHIM_LITESTREAM_UP=1 says it already runs).
    (bin_dir / "curl").write_text(
        '#!/bin/sh\ncase "$*" in *20241/ready*)\n'
        '  [ "$SHIM_TUNNEL" = ready ] && { echo \'{"status":200,"readyConnections":4}\'; exit 0; }\n'
        '  echo \'{"status":503,"readyConnections":0}\'; exit 22 ;;\nesac\n'
        'if [ "$SHIM_LITESTREAM_UP" = 1 ] || grep -q "up -d --no-deps litestream" "$SHIM_LOG" 2>/dev/null; then\n'
        '  [ "$SHIM_LITESTREAM_BROKEN" = 1 ] && exit 7; echo "litestream_db_size 1"; exit 0\nfi\nexit 7\n'
    )
    (bin_dir / "mountpoint").write_text('#!/bin/sh\nexit "${SHIM_MOUNTED_EXIT:-0}"\n')
    (bin_dir / "sleep").write_text("#!/bin/sh\nexit 0\n")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    work = tmp_path / "deploy"
    work.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    edge = tmp_path / "edge"
    edge.mkdir()
    # The copy works on a scratch data volume instead of /var/lib/veda (no runtime override exists).
    script = DEPLOY.read_text()
    assert (
        script.count("readonly DATA_DIR=/var/lib/veda") == 1
        and script.count("readonly EDGE_DIR=/etc/veda/cloudflared") == 1
    )
    script = script.replace("readonly DATA_DIR=/var/lib/veda", f"readonly DATA_DIR={data}")
    (work / "deploy.sh").write_text(
        script.replace("readonly EDGE_DIR=/etc/veda/cloudflared", f"readonly EDGE_DIR={edge}")
    )
    log = tmp_path / "docker.log"

    def run(*args, env_extra=None, first=False, tunnel_config=None, tunnel_token=True):
        db = data / "veda.db"
        if first:
            db.unlink(missing_ok=True)
        else:
            db.write_text("")
        for f in edge.iterdir():
            f.unlink()
        if tunnel_config is not None:
            (edge / "config.yml").write_text(tunnel_config)
            if tunnel_token:
                (edge / "tunnel.env").write_text("TUNNEL_TOKEN=x\n")
        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "SHIM_IMAGES": json.dumps(IMAGES),
            "SHIM_LOG": str(log),
            "SHIM_LITESTREAM_UP": "1",
            **(env_extra or {}),
        }
        r = subprocess.run(
            ["bash", str(work / "deploy.sh"), *args], env=env, capture_output=True, text=True, timeout=60
        )
        calls = log.read_text() if log.exists() else ""
        log.unlink(missing_ok=True)
        return r, calls

    return run


def _deployed(calls):
    return "up -d --no-deps api" in calls


@pytest.mark.parametrize("tag", ["at-floor", "above-floor"])
@pytest.mark.parametrize("mode", [[], ["--rollback"]])
def test_FC12_images_at_or_above_the_floor_deploy(deploy, tag, mode):
    r, calls = deploy(*mode, tag)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _deployed(calls)


@pytest.mark.parametrize(
    "tag", ["2f6b59a", "9236aa3", "old-release", "schema-unknown", "no-release", "string-release", "garbage"]
)
@pytest.mark.parametrize("mode", [[], ["--rollback"]])
def test_FC12_images_below_the_floor_or_unversioned_are_refused_in_every_mode(deploy, tag, mode):
    r, calls = deploy(*mode, tag)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "Refusing" in r.stdout
    assert not _deployed(calls), "nothing was started"
    assert "migrate" not in calls and "stop worker" not in calls, "refused before any change"


def test_FC12_no_override_exists(deploy):
    env = {"RELEASE_FLOOR": "0", "ROLLBACK_FLOOR": "0001_kernel", "VEDA_RELEASE_FLOOR": "0", "FORCE": "1"}
    r, calls = deploy("old-release", env_extra=env)
    assert r.returncode == 1 and not _deployed(calls)
    r, _ = deploy("--force", "old-release")
    assert r.returncode != 0
    script = DEPLOY.read_text()
    assert "readonly RELEASE_FLOOR=3" in script and 'readonly ROLLBACK_FLOOR="0009_mfa_challenge_binding"' in script


def test_FC12_image_reports_its_release_sequence():
    from veda.release import RELEASE_SEQUENCE

    assert RELEASE_SEQUENCE >= 3


# --- The first deploy: no database yet, so Litestream starts after the migration creates it -----------------------


def _order(calls, *steps):
    lines = calls.splitlines()
    at = [next(i for i, line in enumerate(lines) if step in line) for step in steps]
    return at == sorted(at)


def test_first_deploy_starts_replication_after_the_migration_and_before_the_api(deploy):
    r, calls = deploy("at-floor", first=True, env_extra={"SHIM_LITESTREAM_UP": "0"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "first deploy: no database and an empty replica" in r.stdout
    assert "2. Snapshot: none (no database yet)" in r.stdout and "maintenance snapshot" not in calls
    assert _order(calls, "litestream generations", "migrate", "up -d --no-deps litestream", "up -d --no-deps api")
    assert _deployed(calls)


def test_first_deploy_refuses_when_the_replica_already_has_generations(deploy):
    # A rebuilt host with an empty volume must restore first: a new generation would let retention delete the old.
    r, calls = deploy("at-floor", first=True, env_extra={"SHIM_GENERATIONS": "a1b2c3d4e5f60708"})
    assert r.returncode == 1
    assert "replica has generations; restore it first" in r.stdout
    assert "migrate" not in calls and "stop worker" not in calls and not _deployed(calls)


def test_first_deploy_refuses_when_the_replica_cannot_be_listed(deploy):
    r, calls = deploy("at-floor", first=True, env_extra={"SHIM_GENERATIONS_EXIT": "1"})
    assert r.returncode == 1
    assert "cannot list the replica's generations" in r.stdout
    assert "migrate" not in calls and not _deployed(calls)


def test_first_deploy_never_starts_the_api_without_replication(deploy):
    r, calls = deploy("at-floor", first=True, env_extra={"SHIM_LITESTREAM_UP": "0", "SHIM_LITESTREAM_BROKEN": "1"})
    assert r.returncode == 1
    assert "Refusing to start the API without replication" in r.stdout
    assert "migrate" in calls and not _deployed(calls)
    assert "up -d --no-deps worker scheduler" not in calls


def test_no_database_on_rollback_is_refused(deploy):
    r, calls = deploy("--rollback", "at-floor", first=True)
    assert r.returncode == 1 and "no database at" in r.stdout and not _deployed(calls)


def test_an_unmounted_data_volume_is_refused(deploy):
    r, calls = deploy("at-floor", first=True, env_extra={"SHIM_MOUNTED_EXIT": "1"})
    assert r.returncode == 1 and "is not the mounted data volume" in r.stdout
    assert "generations" not in calls and "migrate" not in calls and not _deployed(calls)


def test_later_deploys_start_a_stopped_litestream_and_require_its_metrics_first(deploy):
    r, calls = deploy("at-floor", env_extra={"SHIM_LITESTREAM_UP": "0"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert _order(calls, "up -d --no-deps litestream", "maintenance snapshot", "migrate", "up -d --no-deps api")
    assert "generations" not in calls


def test_later_deploys_refuse_without_replication_before_any_change(deploy):
    r, calls = deploy("at-floor", env_extra={"SHIM_LITESTREAM_BROKEN": "1"})
    assert r.returncode == 1 and "litestream metrics unavailable" in r.stdout
    assert "maintenance snapshot" not in calls and "migrate" not in calls and not _deployed(calls)


# --- AUT-201: the Cloudflare tunnel, behind Cloudflare Access ------------------------------------------------------

ACCESS_CONFIG = (Path(__file__).resolve().parents[3] / "infra" / "host" / "cloudflared.yml").read_text()


def test_without_an_edge_configuration_the_tunnel_stays_stopped(deploy):
    r, calls = deploy("at-floor")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "7. Edge: not configured (no tunnel)" in r.stdout
    assert "--profile edge rm -s -f cloudflared" in calls and "up -d --no-deps cloudflared" not in calls


def test_with_an_access_configuration_the_tunnel_starts_after_the_api_and_must_connect(deploy):
    r, calls = deploy("at-floor", tunnel_config=ACCESS_CONFIG, env_extra={"SHIM_TUNNEL": "ready"})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tunnel ready: 4 edge connection(s)" in r.stdout
    assert _order(
        calls, "up -d --no-deps api", "up -d --no-deps worker scheduler", "--profile edge up -d --no-deps cloudflared"
    )
    assert r.stdout.rstrip().endswith("done: at-floor")


def test_a_tunnel_that_never_connects_fails_the_deploy(deploy):
    r, calls = deploy("at-floor", tunnel_config=ACCESS_CONFIG, env_extra={"SHIM_TUNNEL": "down"})
    assert r.returncode == 1
    assert "tunnel not ready: no edge connection" in r.stdout and "done:" not in r.stdout


def test_a_tunnel_configuration_without_access_is_never_started(deploy):
    open_config = ACCESS_CONFIG.replace("        required: true\n", "        required: false\n")
    r, calls = deploy("at-floor", tunnel_config=open_config, env_extra={"SHIM_TUNNEL": "ready"})
    assert r.returncode == 1
    assert "does not require Cloudflare Access" in r.stdout
    assert "up -d --no-deps cloudflared" not in calls


def test_a_tunnel_configuration_without_its_token_is_never_started(deploy):
    r, calls = deploy("at-floor", tunnel_config=ACCESS_CONFIG, tunnel_token=False, env_extra={"SHIM_TUNNEL": "ready"})
    assert r.returncode == 1 and "up -d --no-deps cloudflared" not in calls


def test_the_compose_tunnel_service_is_pinned_host_networked_and_opt_in():
    compose = (DEPLOY.parent / "docker-compose.yml").read_text()
    block = compose[compose.index("  cloudflared:") : compose.index("  litestream:")]
    assert (
        "image: cloudflare/cloudflared:2026.9.3@sha256:072c067d25ccbe61d46e18f0d0723255f2bb5304f7317caa95b27031520ff92c"
        in block
    )
    assert 'profiles: ["edge"]' in block and "network_mode: host" in block
    assert "ports:" not in block, "the tunnel connects out; it publishes nothing"
    assert "/etc/veda/cloudflared/config.yml:/etc/cloudflared/config.yml:ro" in block
    assert "api.env" not in block, "the tunnel never receives the API's secrets"
    assert [line.strip() for line in block.splitlines() if "path:" in line] == [
        "- path: /etc/veda/cloudflared/tunnel.env"
    ]
