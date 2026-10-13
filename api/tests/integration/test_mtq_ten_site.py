"""MTQ B1-T12: the ten-site validation harness on a SYNTHETIC dataset, end to end through the API.

Ten synthetic sites (five apartments: 2, 2, 3, 3, 4 BHK; five independent houses on two levels, one of them 5 BHK)
are captured through the offline sync endpoint (Lite and Full), photographed, submitted and verified four-eyes, then
compared with their reference under the recorded tolerance policy: walls, ceilings, areas, openings (doors, windows
and sills) and the staircase flight. One site carries an explained deviation and one a planted failure with its root
cause, so the rules are exercised, not just the happy path. The result is SYNTHETIC_VALIDATED: it proves the pipeline,
never field accuracy.

Set VEDA_MTQ_EVIDENCE_OUT to a directory to write the run's inputs (reference.json, measured.json, events.json) there;
``tools/mtq_ten_site.py`` turns them into the committed evidence document.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from tests.support.ten_site import TenSite, load
from veda.modules.mtq import templates, ten_site

ON = pytest.mark.settings(mtq_site_enabled=True)


@ON
def test_ten_synthetic_sites_validate_end_to_end(api, factory, engine):
    dataset = load()
    reference, measured, events = TenSite(api, factory).run(dataset)
    evidence = ten_site.evaluate(reference, measured, events, template_version=templates.TEMPLATE_VERSION,
                                 provenance={"database_engine": engine})  # fmt: skip

    by_site = {s["site_id"]: s for s in evidence["sites"]}
    assert evidence["dataset_kind"] == "SYNTHETIC" and evidence["sites_evaluated"] == 10
    assert evidence["provenance"]["database_engine"] == engine
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", evidence["provenance"]["reference_sha256"])
    assert evidence["coverage"]["complete"], [(s["site_id"], s["profile_mismatches"]) for s in evidence["sites"]]
    assert evidence["coverage"]["two_houses_with_two_or_more_levels"] and evidence["coverage"]["profiles_agree"]
    assert evidence["coverage"]["informational"]["five_bhk_sites"] == ["S10"]
    assert sorted(s["bedrooms"] for s in evidence["sites"] if s["property_type_code"] == "APARTMENT") == [2, 2, 3, 3, 4]
    assert all(s["levels"] == 2 for s in evidence["sites"] if s["property_type_code"] == "INDEPENDENT_HOUSE")
    assert {s["survey_level_code"] for s in evidence["sites"]} == {"LITE", "FULL"}
    assert all(
        s["set_status"] == "VERIFIED" and re.fullmatch(r"sha256:[0-9a-f]{64}", s["snapshot"]) for s in evidence["sites"]
    )
    assert all(s["profile_mismatches"] == [] for s in evidence["sites"])
    # Openings and the staircase are compared, not skipped.
    assert all(s["openings"]["compared"] > 0 and s["openings"]["fail"] == 0 for s in evidence["sites"])
    houses = [s for s in evidence["sites"] if s["property_type_code"] == "INDEPENDENT_HOUSE"]
    assert all(s["staircase"] == {"compared": 4, "pass": 4, "explained": 0, "fail": 0} for s in houses)
    # The planted deviations behave as the closure's rules say.
    assert by_site["S04"]["verdict"] == "PASS" and by_site["S04"]["walls"]["explained"] == 1
    assert by_site["S07"]["verdict"] == "FAIL" and by_site["S07"]["walls"]["fail"] == 1
    assert by_site["S07"]["root_cause"] == "Tape slipped off the skirting"
    assert [s for s, v in by_site.items() if v["verdict"] != "PASS"] == ["S07"]
    assert by_site["S05"]["events"]["second_surveyor_conflict"] is True
    assert by_site["S03"]["events"]["offline_retry"] and by_site["S09"]["events"]["offline_retry"]
    assert evidence["survey_time_not_recorded"] == ["S06"]
    assert by_site["S06"]["survey_time"]["against_baseline"] == "NOT_RECORDED"
    assert evidence["gate_verdict"] == "PASS" and evidence["label"] == "SYNTHETIC_VALIDATED"

    text = json.dumps(evidence)
    assert "Synthetic site" not in text and "+91" not in text and "lead" not in text.lower()  # no customer data
    assert not re.search(r"₹|INR|(?<!gene)rate|amount", text)  # no pricing; only "generated_at" is exempt
    out = os.environ.get("VEDA_MTQ_EVIDENCE_OUT")
    if out:
        target = Path(out) / engine
        target.mkdir(parents=True, exist_ok=True)
        (target / "reference.json").write_text(reference.model_dump_json(indent=2, exclude_none=True) + "\n")
        (target / "measured.json").write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n")
        (target / "events.json").write_text(json.dumps(events, indent=2, sort_keys=True) + "\n")


def test_fewer_than_ten_references_is_unvalidated_never_a_pass():
    ref = ten_site.Reference(dataset_id="LIVE-STAGING-2026-10", dataset_kind="LIVE", sites=[])
    evidence = ten_site.evaluate(ref, {}, template_version=templates.TEMPLATE_VERSION)
    assert evidence["label"] == "UNVALIDATED_NO_REFERENCE" and evidence["gate_verdict"] == "INCOMPLETE"


def _measured(label: str, length: int, width: int, walls: list[int], area: int | None) -> dict:
    return {
        "set": {"status": "VERIFIED", "revision_no": 1, "snapshot_sha256": "0" * 64, "spaces": [{
            "space_id": "sp1", "ceiling_height_mm": 2900, "derived_floor_area_sqft_centi": area,
            "walls": [{"wall_index": i, "length_mm": w} for i, w in enumerate(walls, start=1)]}]},
        "property": {"property_type_code": "APARTMENT", "derived_bedroom_count": 2, "derived_level_count": 1,
                     "spaces": [{"id": "sp1", "label": label}]},
    }  # fmt: skip


def test_site_rules_pass_explain_and_fail():
    from veda.modules.mtq.derivation import mm2_to_sqft_centi

    space = ten_site.SpaceRef(label="Kitchen", length_mm=3600, width_mm=2700, ceiling_height_mm=2900,
                              walls=[2700, 3600, 2700, 3600])  # fmt: skip
    site = ten_site.SiteRef(site_id="S01", property_type_code="APARTMENT", bedrooms=2, survey_level_code="LITE",
                            reference_method="TAPE", spaces=[space])  # fmt: skip
    area = mm2_to_sqft_centi(3600 * 2700)
    ok = ten_site.evaluate_site(site, _measured("Kitchen", 3600, 2700, [2705, 3590, 2700, 3610], area))
    assert ok["verdict"] == "PASS" and ok["walls"] == {"compared": 4, "pass": 4, "explained": 0, "fail": 0}
    unexplained = ten_site.evaluate_site(site, _measured("Kitchen", 3600, 2700, [2740, 3600, 2700, 3600], area))
    assert unexplained["verdict"] == "FAIL"  # 40 mm on a short wall without a recorded cause
    explained = ten_site.evaluate_site(
        site.model_copy(update={"causes": {"Kitchen/W1": "Skirting tile"}}),
        _measured("Kitchen", 3600, 2700, [2740, 3600, 2700, 3600], area),
    )
    # Explained, not failed; but one exception in four walls is under the closure's 95 % rule, so the site fails.
    assert (
        explained["walls"] == {"compared": 4, "pass": 3, "explained": 1, "fail": 0} and explained["verdict"] == "FAIL"
    )
    nothing = _measured("Kitchen", 3600, 2700, [], area)
    nothing["set"]["spaces"] = []
    missing = ten_site.evaluate_site(site, nothing)
    assert missing["verdict"] == "FAIL" and missing["exceptions"][0]["cause"] == "NOT_MEASURED"
    with pytest.raises(ValueError):
        ten_site.SiteRef(
            site_id="Ravi K",
            property_type_code="APARTMENT",
            bedrooms=2,
            survey_level_code="LITE",
            reference_method="TAPE",
            spaces=[space],
        )  # fmt: skip  (site ids are anonymous)
