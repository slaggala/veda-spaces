"""IR-35: one API process per database, enforced from the effective configuration and at runtime."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from veda.kernel import single_instance

CONF = str(Path(__file__).resolve().parents[2] / "deploy" / "gunicorn.conf.py")


def _deploy_check(monkeypatch, cmd_args=None):
    from veda.cli.main import main

    if cmd_args is None:
        monkeypatch.delenv("GUNICORN_CMD_ARGS", raising=False)
    else:
        monkeypatch.setenv("GUNICORN_CMD_ARGS", cmd_args)
    return main(["deploy-check", "--gunicorn-conf", CONF])


def test_IR35_deploy_check_passes_for_the_committed_configuration(monkeypatch):
    assert _deploy_check(monkeypatch) == 0


@pytest.mark.parametrize("args", ["--workers=4", "-w 2", "--worker-class=gevent", "--threads=1 --worker-class=sync"])
def test_IR35_deploy_check_applies_gunicorn_cmd_args(monkeypatch, args):
    assert _deploy_check(monkeypatch, args) == 1


def test_IR35_runtime_hook_refuses_more_than_one_worker():
    with pytest.raises(single_instance.SingleInstanceError):
        single_instance.check_gunicorn(SimpleNamespace(workers=4, worker_class_str="gthread"))
    single_instance.check_gunicorn(SimpleNamespace(workers=1, worker_class_str="gthread"))


def test_IR35_second_instance_on_the_same_database_is_refused(tmp_path):
    url = f"sqlite:///{tmp_path}/veda.db"
    try:
        assert single_instance.acquire_lock(url) == Path(f"{tmp_path}/veda.db.api.lock")
        with pytest.raises(single_instance.SingleInstanceError):
            single_instance.acquire_lock(url)
    finally:
        single_instance.release_all()
    assert single_instance.acquire_lock(url)
    single_instance.release_all()
    assert single_instance.acquire_lock("postgresql+psycopg://db/veda") is None
