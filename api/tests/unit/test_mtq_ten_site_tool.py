"""MTQ B1-T12: the ten-site evidence tool never claims a validation it cannot show."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TOOL = Path(__file__).resolve().parents[2] / "tools" / "mtq_ten_site.py"


def _tool():
    spec = importlib.util.spec_from_file_location("mtq_ten_site_tool", TOOL)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_without_references_the_live_track_is_unvalidated(tmp_path):
    out = tmp_path / "evidence.json"
    assert _tool().main(["--dataset-id", "LIVE-STAGING-B1", "--out", str(out)]) == 1
    evidence = json.loads(out.read_text())
    assert evidence["label"] == "UNVALIDATED_NO_REFERENCE" and evidence["dataset_kind"] == "LIVE"
    assert evidence["sites"] == [] and evidence["gate_verdict"] == "INCOMPLETE"


def test_a_reference_without_measured_sets_is_reported_not_evaluated(tmp_path):
    ref = {"dataset_id": "LIVE-STAGING-B1", "dataset_kind": "LIVE", "sites": [{
        "site_id": "S01", "property_type_code": "APARTMENT", "bedrooms": 3, "survey_level_code": "FULL",
        "reference_method": "LASER_DISTO_SECOND_SURVEYOR",
        "spaces": [{"label": "Kitchen", "length_mm": 3600, "width_mm": 2700, "walls": [2700, 3600, 2700, 3600]}]}]}  # fmt: skip
    (tmp_path / "ref.json").write_text(json.dumps(ref))
    out = tmp_path / "evidence.json"
    assert _tool().main(["--reference", str(tmp_path / "ref.json"), "--out", str(out)]) == 1
    evidence = json.loads(out.read_text())
    assert evidence["label"] == "UNVALIDATED_NO_REFERENCE" and evidence["sites_without_a_measured_set"] == ["S01"]


def test_malformed_or_identifying_input_is_refused(tmp_path):
    ref = {"dataset_id": "LIVE-STAGING-B1", "dataset_kind": "LIVE", "sites": [{
        "site_id": "Mr Rao, Flat 402", "property_type_code": "APARTMENT", "bedrooms": 3, "survey_level_code": "FULL",
        "reference_method": "TAPE", "spaces": [{"label": "Kitchen"}]}]}  # fmt: skip
    (tmp_path / "ref.json").write_text(json.dumps(ref))
    assert _tool().main(["--reference", str(tmp_path / "ref.json"), "--out", str(tmp_path / "o.json")]) == 2
    (tmp_path / "bad.json").write_text("{not json")
    assert _tool().main(["--reference", str(tmp_path / "bad.json"), "--out", str(tmp_path / "o.json")]) == 2
    assert not (tmp_path / "o.json").exists()
