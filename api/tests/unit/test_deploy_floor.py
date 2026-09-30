"""FC-12: deploy.sh enforces the release floor and the schema floor in every mode (runbook §2.1).

docker and curl are replaced by shims on PATH: each fake image answers `veda schema-status` the way a real image of
that release would. Nothing here deploys anything; no rollback rehearsal is claimed (RG-7 stays open).
"""

import json
import os
import shutil
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
    (bin_dir / "curl").write_text("#!/bin/sh\necho 'litestream_db_size 1'\n")
    for f in bin_dir.iterdir():
        f.chmod(0o755)
    work = tmp_path / "deploy"
    work.mkdir()
    shutil.copy(DEPLOY, work / "deploy.sh")
    log = tmp_path / "docker.log"

    def run(*args, env_extra=None):
        env = {
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "SHIM_IMAGES": json.dumps(IMAGES),
            "SHIM_LOG": str(log),
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
