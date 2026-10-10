"""Canonical customer-copy closure, Phase 11: the owner-run real-card evidence tool.

The tool runs here only on the synthetic card: it never sees the private card in tests or CI."""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[2]
SYNTHETIC = API / "tests/fixtures/estimator/synthetic-rate-card.json"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("evidence", API / "tools/catalog_real_card_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def outside(tmp_path):
    card = tmp_path / "card.json"
    shutil.copy(SYNTHETIC, card)
    return card


def test_a_card_inside_the_repository_is_refused(tool, tmp_path, capsys):
    assert tool.main(["--card", str(SYNTHETIC), "--expected-sha256", "0" * 64, "--operator", "Owner (test)",
                      "--out-dir", str(tmp_path)]) == 2  # fmt: skip
    assert "outside the repository" in capsys.readouterr().err


def test_a_card_with_another_fingerprint_is_refused(tool, outside, tmp_path, capsys):
    assert tool.main(["--card", str(outside), "--expected-sha256", "0" * 64, "--operator", "Owner (test)",
                      "--out-dir", str(tmp_path / "ev")]) == 2  # fmt: skip
    assert "fingerprint" in capsys.readouterr().err and not (tmp_path / "ev").exists()


def test_evidence_inside_the_repository_is_refused(tool, outside, monkeypatch):
    monkeypatch.setattr(tool, "run_engine", lambda e, c, x: [{"id": "t::a", "engine": e, "outcome": "passed"}])
    assert tool.main(["--card", str(outside), "--expected-sha256", tool.fingerprint(outside), "--operator", "Owner",
                      "--out-dir", str(API / "var/evidence")]) == 2  # fmt: skip


def test_the_artifact_holds_only_the_allowed_fields_and_no_card_content(tool, outside, tmp_path, monkeypatch):
    monkeypatch.setattr(
        tool, "run_engine", lambda e, c, x: [{"id": f"{tool.TESTS}::test_x", "engine": e, "outcome": "passed"}]
    )
    out = tmp_path / "ev"
    assert tool.main(["--card", str(outside), "--expected-sha256", tool.fingerprint(outside), "--operator",
                      "Owner (test)", "--out-dir", str(out)]) == 0  # fmt: skip
    [path] = list(out.iterdir())
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    doc = json.loads(path.read_text())
    assert set(doc) == {*tool.FIELDS, "artifact_sha256"} and doc["equality"] == "PASS"
    assert doc["engines"] == ["sqlite", "postgresql"] and len(doc["scenarios"]) == 2
    card = json.loads(SYNTHETIC.read_text())
    amounts = {str(v) for line in card["products"][0]["lines"] for v in line["rates"].values()}
    assert not any(a in path.read_text() for a in amounts if len(a) > 3), "no rate reaches the artifact"
    assert tool.verify(doc)
    assert not tool.verify({**doc, "equality": "FAIL"}), "a changed artifact fails its hash"
    assert not tool.verify({**doc, "rates": {}}), "an extra field is refused"


def test_a_failed_or_skipped_run_is_not_equality(tool, outside, tmp_path, monkeypatch):
    for outcome in ("failed", "skipped", "error"):
        monkeypatch.setattr(tool, "run_engine", lambda e, c, x, o=outcome: [{"id": "t::a", "engine": e, "outcome": o}])
        assert tool.main(["--card", str(outside), "--expected-sha256", tool.fingerprint(outside), "--operator", "Owner",
                          "--out-dir", str(tmp_path / outcome)]) == 1  # fmt: skip
        [path] = list((tmp_path / outcome).iterdir())
        assert json.loads(path.read_text())["equality"] == "FAIL"
