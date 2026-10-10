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


def test_the_rendered_quoted_form_is_read(deploy, tmp_path):  # noqa: F811
    """render-env.sh writes NAME="value"; the scanner step reads that form."""
    path = tmp_path / "api.env"
    path.write_text(f'VEDA_CATALOG_MEDIA_SCANNER="clamd"\nVEDA_CATALOG_CLAMD_IMAGE="{PINNED}"\n')
    r, calls = deploy("at-floor", env_extra={"VEDA_API_ENV": str(path)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "--profile scanner up -d --no-deps clamd" in calls
