"""Targeted media enablement: deploy.sh runs the malware scanner only when the configuration selects clamd, only with
an image pinned by digest, and only if it answers before the API restarts. docker is a shim; nothing is deployed."""

import pytest

from tests.unit.test_deploy_floor import deploy  # noqa: F401  (the shared shim fixture)

PINNED = "clamav/clamav-debian:1.4@sha256:" + "c" * 64


def env_file(tmp_path, **settings):
    path = tmp_path / "api.env"
    path.write_text("".join(f"{k}={v}\n" for k, v in settings.items()))
    return {"VEDA_API_ENV": str(path)}


def test_no_scanner_unless_the_configuration_selects_it(deploy, tmp_path):  # noqa: F811
    r, calls = deploy("at-floor", env_extra=env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="none"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--profile scanner rm -s -f clamd" in calls and "--profile scanner up" not in calls
    assert "media uploads stay PENDING" in r.stdout


def test_no_scanner_when_the_setting_is_absent(deploy, tmp_path):  # noqa: F811
    r, calls = deploy("at-floor", env_extra=env_file(tmp_path))
    assert r.returncode == 0 and "--profile scanner up" not in calls


@pytest.mark.parametrize("image", ["", "clamav/clamav-debian:latest", "clamav/clamav-debian:PLACEHOLDER",
                                   "clamav/clamav-debian@sha256:short"])  # fmt: skip
def test_a_scanner_image_not_pinned_by_digest_is_refused(deploy, tmp_path, image):  # noqa: F811
    r, calls = deploy("at-floor", env_extra=env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="clamd",
                                                      VEDA_CATALOG_CLAMD_IMAGE=image))  # fmt: skip
    assert r.returncode != 0 and "not pinned by digest" in r.stdout
    assert "up -d --no-deps api" not in calls, "the API is not restarted"


def test_a_pinned_scanner_starts_on_the_private_network_and_must_answer(deploy, tmp_path):  # noqa: F811
    r, calls = deploy("at-floor", env_extra=env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="clamd",
                                                      VEDA_CATALOG_CLAMD_IMAGE=PINNED))  # fmt: skip
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--profile scanner up -d --no-deps clamd" in calls
    assert calls.index("--profile scanner up -d --no-deps clamd") < calls.index("up -d --no-deps api"), "before the API"


def test_a_scanner_that_does_not_answer_stops_the_deploy(deploy, tmp_path):  # noqa: F811
    extra = {**env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="clamd", VEDA_CATALOG_CLAMD_IMAGE=PINNED),
             "SHIM_SCANNER": "down"}  # fmt: skip
    r, calls = deploy("at-floor", env_extra=extra)
    assert r.returncode != 0 and "the scanner did not answer" in r.stdout
    assert "up -d --no-deps api" not in calls


def test_the_scanner_service_is_private_bounded_and_hardened():
    from pathlib import Path

    import yaml

    compose = yaml.safe_load((Path(__file__).resolve().parents[2] / "deploy" / "docker-compose.yml").read_text())
    clamd = compose["services"]["clamd"]
    assert clamd["profiles"] == ["scanner"], "never started by default"
    assert "ports" not in clamd and clamd["expose"] == ["3310"], "no host port"
    assert (
        clamd["read_only"] is True
        and clamd["cap_drop"] == ["ALL"]
        and "no-new-privileges:true" in clamd["security_opt"]
    )
    assert clamd["mem_limit"] and clamd["mem_reservation"], "bounded memory"
    assert "network_mode" not in clamd, "the private Compose network, not the host network"
    assert compose["volumes"]["clamav-db"] == {}, "signatures persist across restarts"


def test_the_scanner_runs_as_the_image_user_without_any_capability():
    """CATALOG-V3-scanner-implementation.md: the validated non-root profile. The image's /init (root, chown -R on the
    0700 signature directory) cannot start under cap_drop ALL; the profile runs the image's clamav user with the
    bundle's entrypoint instead, and adds no capability and no privilege to make it work."""
    from pathlib import Path

    import yaml

    bundle = Path(__file__).resolve().parents[2] / "deploy"
    clamd = yaml.safe_load((bundle / "docker-compose.yml").read_text())["services"]["clamd"]
    assert clamd["user"] == "1000:1000" and clamd["entrypoint"] == ["/usr/local/bin/veda-clamd-init"]
    assert "cap_add" not in clamd and "privileged" not in clamd and clamd["cap_drop"] == ["ALL"]
    assert clamd["pids_limit"] == 256 and clamd["restart"] == "unless-stopped"
    assert clamd["mem_limit"] == "${VEDA_CLAMD_MEM_LIMIT:-2048m}", "the validated limit is the default"
    assert "env_file" not in clamd and set(clamd["environment"]) == {"CLAMAV_NO_MILTERD", "FRESHCLAM_CHECKS"}
    # The three directories the daemons write are tmpfs with an explicit mode (the default mode was not writable by
    # uid 1000), a size bound (tmpfs pages count against mem_limit) and no exec, suid or device nodes.
    tmpfs = dict(t.split(":", 1) for t in clamd["tmpfs"])
    assert set(tmpfs) == {"/tmp", "/run/clamav", "/var/log/clamav"}
    for options in tmpfs.values():
        parts = set(options.split(","))
        assert (
            "mode=1777" in parts
            and {"noexec", "nosuid", "nodev"} <= parts
            and any(p.startswith("size=") for p in parts)
        )
    # Read-only bind mounts from the bundle: the configuration (StreamMaxLength 30M etc.) and the entrypoint; the
    # signature database on the named volume. Nothing else from the host.
    assert sorted(clamd["volumes"]) == sorted([
        "clamav-db:/var/lib/clamav",
        "./clamd.conf:/etc/clamav/clamd.conf:ro",
        "./clamd-entrypoint.sh:/usr/local/bin/veda-clamd-init:ro",
    ])  # fmt: skip
    conf = (bundle / "clamd.conf").read_text()
    for directive in ("StreamMaxLength 30M", "MaxScanSize 100M", "MaxFileSize 30M", "MaxRecursion 10",
                      "ConcurrentDatabaseReload no", "ExitOnOOM yes", "TCPSocket 3310"):  # fmt: skip
        assert f"\n{directive}\n" in conf, directive
    entrypoint = (bundle / "clamd-entrypoint.sh").read_text()
    assert entrypoint.startswith("#!/bin/sh\n") and (bundle / "clamd-entrypoint.sh").stat().st_mode & 0o111
    for required in ("clamd --foreground &", 'wait "$clamd_pid"', 'exit "$rc"', "freshclam --checks="):
        assert required in entrypoint, required
    code = "\n".join(line for line in entrypoint.splitlines() if not line.lstrip().startswith("#"))
    assert "chown" not in code and "tail -f" not in code, "no ownership change; PID 1 exits with clamd"
    health = clamd["healthcheck"]
    assert (
        health["test"] == ["CMD-SHELL", "clamdcheck.sh"]
        and health["interval"] == "30s"
        and health["start_period"] == "300s"
    )


def test_the_rendered_quoted_form_is_read(deploy, tmp_path):  # noqa: F811
    """render-env.sh writes NAME="value"; the scanner step reads that form."""
    path = tmp_path / "api.env"
    path.write_text(f'VEDA_CATALOG_MEDIA_SCANNER="clamd"\nVEDA_CATALOG_CLAMD_IMAGE="{PINNED}"\n')
    r, calls = deploy("at-floor", env_extra={"VEDA_API_ENV": str(path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--profile scanner up -d --no-deps clamd" in calls


# --- deployment order (pre-plan closure, phase 7) -----------------------------------------------------------------
OFF = {"VEDA_CATALOG_MEDIA_SCANNER": "none", "VEDA_CATALOG_ESTIMATOR_ENABLED": "false"}


def test_with_v3_off_no_approval_is_needed_and_the_deploy_proceeds(deploy, tmp_path):  # noqa: F811
    r, calls = deploy("at-floor", env_extra=env_file(tmp_path, **OFF))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "staging_approval" not in calls and "up -d --no-deps api" in calls


@pytest.mark.parametrize(
    "approval_exit", ["1", "2"]
)  # DRAFT, IN_REVIEW, REVOKED, expired, missing: the validator exits 1
def test_v3_activation_without_a_current_approval_is_refused_before_anything_changes(deploy, tmp_path, approval_exit):  # noqa: F811
    extra = {**env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="clamd", VEDA_CATALOG_CLAMD_IMAGE=PINNED,
                        VEDA_CATALOG_ESTIMATOR_ENABLED="true"), "SHIM_APPROVAL_EXIT": approval_exit}  # fmt: skip
    r, calls = deploy("at-floor", env_extra=extra)
    assert r.returncode != 0 and "APPROVAL RECORD INVALID" in r.stdout
    for step in (
        "maintenance snapshot",
        "stop worker scheduler",
        "veda.cli migrate",
        "up -d --no-deps api",
        "--profile scanner up",
    ):
        assert step not in calls, step


def test_v3_activation_with_a_current_approval_proceeds(deploy, tmp_path):  # noqa: F811
    extra = {**env_file(tmp_path, VEDA_CATALOG_MEDIA_SCANNER="clamd", VEDA_CATALOG_CLAMD_IMAGE=PINNED,
                        VEDA_CATALOG_ESTIMATOR_ENABLED="true"), "SHIM_APPROVAL_EXIT": "0"}  # fmt: skip
    r, calls = deploy("at-floor", env_extra=extra)
    assert r.returncode == 0, r.stdout + r.stderr
    assert calls.index("staging_approval") < calls.index("up -d --no-deps api")
