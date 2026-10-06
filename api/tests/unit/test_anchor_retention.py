"""D6: the anchor Object Lock retention is configured (VEDA_ANCHOR_RETENTION_DAYS), never silently defaulted.

COMPLIANCE-mode retention cannot be shortened or removed once an object is written, so: the default is the ledger's
ten years; staging must state its own value (30 days, owner decision D6); production refuses anything below ten
years; a value that is not a whole number of days refuses to load; and the S3 anchor store locks every object it
writes until exactly now + the configured retention.
"""

from datetime import UTC, datetime, timedelta

import pytest

from veda import config
from veda.kernel import clock
from veda.platform import anchor_store

from .test_config_environments import deployed_env

NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)


def _problems(settings) -> list[str]:
    return [p for p in config.validate_environment(settings) if "ANCHOR_RETENTION" in p]


@pytest.mark.parametrize("env", ["local", "test"])
def test_D6_default_is_ten_years_when_unset(monkeypatch, env):
    monkeypatch.delenv("VEDA_ANCHOR_RETENTION_DAYS", raising=False)
    monkeypatch.setenv("VEDA_ENV", env)
    settings = config.load_settings()
    assert settings.anchor_retention_days is None
    assert settings.anchor_retention == timedelta(days=3650) == timedelta(days=config.ANCHOR_RETENTION_DEFAULT_DAYS)
    assert _problems(settings) == []


def test_D6_staging_uses_thirty_days(monkeypatch):
    settings = deployed_env(monkeypatch, "staging")
    assert settings.anchor_retention_days == 30
    assert settings.anchor_retention == timedelta(days=30)
    assert config.validate_environment(settings) == []


def test_D6_staging_refuses_an_unset_retention(monkeypatch):
    settings = deployed_env(monkeypatch, "staging", VEDA_ANCHOR_RETENTION_DAYS=None)
    assert _problems(settings) == ["VEDA_ANCHOR_RETENTION_DAYS is required in staging (D6)"]


@pytest.mark.parametrize("days", [None, "3650", "3651", "36500"])
def test_D6_production_accepts_ten_years_or_more(monkeypatch, days):
    settings = deployed_env(monkeypatch, "production", VEDA_ANCHOR_RETENTION_DAYS=days)
    assert settings.anchor_retention >= timedelta(days=3650)
    assert config.validate_environment(settings) == []


@pytest.mark.parametrize("days", ["1", "30", "3649"])
def test_D6_production_refuses_less_than_ten_years(monkeypatch, days):
    settings = deployed_env(monkeypatch, "production", VEDA_ANCHOR_RETENTION_DAYS=days)
    assert "VEDA_ANCHOR_RETENTION_DAYS must be at least 3650 in production (D6)" in _problems(settings)


@pytest.mark.parametrize("env", ["test", "staging", "production"])
@pytest.mark.parametrize("days", ["0", "36501"])
def test_D6_out_of_range_retention_is_reported_in_every_environment(monkeypatch, env, days):
    if env == "test":
        monkeypatch.setenv("VEDA_ENV", "test")
        monkeypatch.setenv("VEDA_ANCHOR_RETENTION_DAYS", days)
        settings = config.load_settings()
    else:
        settings = deployed_env(monkeypatch, env, VEDA_ANCHOR_RETENTION_DAYS=days)
    assert f"VEDA_ANCHOR_RETENTION_DAYS must be between 1 and 36500 (got {int(days)})" in _problems(settings)


@pytest.mark.parametrize("value", ["30d", "-1", "1.5", "thirty", "3e3", "30 days", "0x1e"])
def test_D6_a_retention_that_is_not_whole_days_refuses_to_load(monkeypatch, value):
    with pytest.raises(config.ConfigError, match="VEDA_ANCHOR_RETENTION_DAYS must be a whole number of days"):
        deployed_env(monkeypatch, "staging", VEDA_ANCHOR_RETENTION_DAYS=value)


def test_D6_surrounding_whitespace_is_tolerated(monkeypatch):
    # SSM values rendered into the env file may carry a trailing newline.
    assert deployed_env(monkeypatch, "staging", VEDA_ANCHOR_RETENTION_DAYS=" 30\n").anchor_retention_days == 30


class _RecordingS3:
    def __init__(self):
        self.put_args: list[dict] = []

    def put_object(self, **kwargs):
        self.put_args.append(kwargs)


@pytest.mark.parametrize("days,expected", [(30, 30), (None, 3650), (3650, 3650)])
def test_D6_s3_store_locks_each_object_for_the_configured_retention(days, expected):
    previous = config._current
    config.use_settings(config.Settings(env="test", anchor_retention_days=days))
    clock.set_clock(lambda: NOW)
    fake = _RecordingS3()
    try:
        store = anchor_store.S3AnchorStore("veda-stg-anchor", client=fake)
        store.put("anchor", 7, {"chain_seq": 7})
        store.put_blob("export", "000000000001-000000000007-run", b"{}\n")
    finally:
        clock.reset()
        config._current = previous
    assert [a["ObjectLockMode"] for a in fake.put_args] == ["COMPLIANCE", "COMPLIANCE"]
    assert [a["ObjectLockRetainUntilDate"] for a in fake.put_args] == [NOW + timedelta(days=expected)] * 2


def test_D6_the_store_has_no_fixed_retention_of_its_own():
    # The retention comes only from settings: no module constant can silently override the configured value.
    assert not hasattr(anchor_store, "RETENTION")
