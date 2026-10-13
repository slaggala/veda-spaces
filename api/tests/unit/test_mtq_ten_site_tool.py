"""MTQ B1-T12: the ten-site evidence tool and evaluator never claim a validation they cannot show."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from veda.modules.mtq import templates, ten_site, tolerance
from veda.modules.mtq.derivation import mm2_to_sqft_centi

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


# --- the evaluator against closure §2.2: one test per defect found by the independent review ---------------------------
DOOR = {"wall": 1, "opening_type_code": "DOOR", "width_mm": 900, "height_mm": 2100, "offset_from_wall_start_mm": 100}
WINDOW = {"wall": 1, "opening_type_code": "WINDOW", "width_mm": 1200, "height_mm": 1200,
          "offset_from_wall_start_mm": 1500, "sill_height_mm": 900}  # fmt: skip


def _site(site_id="S01", ptype="APARTMENT", bedrooms=2, levels=None, **extra) -> dict:
    space = {"label": "Living", "length_mm": 4000, "width_mm": 3000, "ceiling_height_mm": 2900,
             "walls": [3000, 4000, 3000, 4000], "openings": [DOOR, WINDOW]}  # fmt: skip
    return {"site_id": site_id, "property_type_code": ptype, "bedrooms": bedrooms, "levels": levels,
            "survey_level_code": "LITE", "reference_method": "LASER_SECOND_SURVEYOR", "spaces": [space], **extra}  # fmt: skip


def _measured_for(site: dict, *, status="VERIFIED", walls=None, stair=None) -> dict:
    sp = site["spaces"][0]
    ops = [{"client_ref": f"o{k}", **{f: v for f, v in o.items() if f != "wall"}} for k, o in enumerate(sp["openings"])]
    wl = sp["walls"] if walls is None else walls
    m_walls = [{"wall_index": i, "length_mm": w, "openings": ops if i == 1 else []} for i, w in enumerate(wl, start=1)]
    area = mm2_to_sqft_centi(sp["length_mm"] * sp["width_mm"]) if sp.get("length_mm") else None
    space = {"space_id": "sp1", "ceiling_height_mm": sp.get("ceiling_height_mm"), "walls": m_walls,
             "derived_floor_area_sqft_centi": area}  # fmt: skip
    if stair is not None:
        space["attributes"] = {"staircase": stair}
    return {
        "set": {"status": status, "revision_no": 1, "snapshot_sha256": "0" * 64, "spaces": [space]},
        "property": {"property_type_code": site["property_type_code"], "derived_bedroom_count": site["bedrooms"],
                     "derived_level_count": site["levels"] or 1, "spaces": [{"id": "sp1", "label": sp["label"]}]},
    }  # fmt: skip


def _ten(kind="SYNTHETIC") -> tuple[dict, dict, dict]:
    """Ten sites meeting the closure §2.2 site mix, measured exactly: the PASS baseline every test bends."""
    sites = [_site(f"S0{i}", "APARTMENT", b) for i, b in zip(range(1, 6), (2, 2, 3, 3, 4), strict=True)]
    sites += [_site(f"S{i:02d}", "INDEPENDENT_HOUSE", 3, 2) for i in range(6, 11)]
    sites[1]["survey_level_code"] = "FULL"
    ref = {"dataset_id": "SYN-UNIT-2026-10", "dataset_kind": kind, "sites": sites}
    events = {"S03": {"offline_retry": True}, "S05": {"second_surveyor_conflict": True}}
    return ref, {s["site_id"]: _measured_for(s) for s in sites}, events


def _evaluate(ref: dict, measured: dict, events: dict | None = None) -> dict:
    return ten_site.evaluate(ten_site.Reference.model_validate(ref), measured, events,
                             template_version=templates.TEMPLATE_VERSION)  # fmt: skip


def test_baseline_ten_exact_sites_are_synthetic_validated_never_live():
    ref, measured, events = _ten()
    evidence = _evaluate(ref, measured, events)
    assert evidence["gate_verdict"] == "PASS" and evidence["label"] == "SYNTHETIC_VALIDATED", evidence["coverage"]


def test_defect1_gate_is_defined_over_exactly_ten_sites(tmp_path):
    nine_pass_eleven_fail = [(f"S{i:02d}", "PASS", None) for i in range(1, 10)]
    nine_pass_eleven_fail += [(f"S{i:02d}", "FAIL", f"cause {i}") for i in range(10, 21)]
    with pytest.raises(ValueError, match="exactly 10"):
        tolerance.gate_verdict(nine_pass_eleven_fail)
    assert tolerance.gate_verdict(nine_pass_eleven_fail[:9]) == "INCOMPLETE"
    assert tolerance.gate_verdict(nine_pass_eleven_fail[:10]) == "PASS"
    assert tolerance.gate_verdict(nine_pass_eleven_fail[:8] + nine_pass_eleven_fail[9:11]) == "FAIL"
    ref, _, _ = _ten()
    ref["sites"].append(_site("S11"))
    with pytest.raises(ValidationError):
        ten_site.Reference.model_validate(ref)
    (tmp_path / "ref.json").write_text(json.dumps(ref))
    assert _tool().main(["--reference", str(tmp_path / "ref.json"), "--out", str(tmp_path / "o.json")]) == 2


def test_defect2_duplicate_ids_refused_and_a_site_without_a_measured_set_never_validates(tmp_path):
    ref, measured, events = _ten()
    dup = json.loads(json.dumps(ref))
    dup["sites"][9]["site_id"] = "S01"
    with pytest.raises(ValidationError, match="repeat"):
        ten_site.Reference.model_validate(dup)
    (tmp_path / "dup.json").write_text(json.dumps(dup))
    assert _tool().main(["--reference", str(tmp_path / "dup.json"), "--out", str(tmp_path / "o.json")]) == 2
    del measured["S10"]
    for kind in ("SYNTHETIC", "LIVE"):
        evidence = _evaluate({**ref, "dataset_kind": kind}, measured, events)
        assert evidence["sites_without_a_measured_set"] == ["S10"] and evidence["sites_incomplete"] == ["S10"]
        assert evidence["gate_verdict"] == "INCOMPLETE" and evidence["label"] == "VALIDATION_FAILED"
    with pytest.raises(ValueError, match="S99"):
        _evaluate(ref, {**measured, "S99": measured["S01"]}, events)


def test_defect3_an_unverified_set_is_incomplete_never_a_pass():
    ref, measured, events = _ten()
    measured["S02"] = _measured_for(ref["sites"][1], status="SUBMITTED")
    evidence = _evaluate(ref, measured, events)
    s02 = next(s for s in evidence["sites"] if s["site_id"] == "S02")
    assert s02["verdict"] == "INCOMPLETE" and s02["incomplete_reasons"] == ["SET_NOT_VERIFIED (SUBMITTED)"]
    assert evidence["gate_verdict"] == "INCOMPLETE" and evidence["label"] == "VALIDATION_FAILED"


def test_defect4_reference_profile_is_cross_checked_against_the_measured_property():
    ref, measured, events = _ten("LIVE")
    measured["S05"]["property"]["derived_bedroom_count"] = 3  # the reference says 4 BHK
    measured["S06"]["property"]["property_type_code"] = "APARTMENT"
    evidence = _evaluate(ref, measured, events)
    by = {s["site_id"]: s for s in evidence["sites"]}
    assert by["S05"]["verdict"] == "FAIL"
    assert by["S05"]["profile_mismatches"] == [{"field": "bedrooms", "reference": 4, "measured": 3}]
    assert by["S06"]["profile_mismatches"][0]["field"] == "property_type_code"
    cov = evidence["coverage"]
    assert cov["profile_mismatch_sites"] == ["S05", "S06"] and not cov["profiles_agree"]
    assert "apartments_cover_2_3_4_bhk" in cov["missing"] and "five_independent_houses" in cov["missing"]
    assert evidence["label"] == "VALIDATION_FAILED"


def test_defect5_openings_and_staircase_are_compared_with_their_tolerances():
    site = _site()
    ref = ten_site.SiteRef.model_validate(site)
    exact = ten_site.evaluate_site(ref, _measured_for(site))
    assert exact["verdict"] == "PASS" and exact["openings"] == {"compared": 7, "pass": 7, "explained": 0, "fail": 0}
    # Matching is by wall and position along it, not by list order: the reversed list pairs the same way.
    m = _measured_for(site)
    m["set"]["spaces"][0]["walls"][0]["openings"].reverse()
    assert ten_site.evaluate_site(ref, m)["verdict"] == "PASS"
    # Door 30 mm wider than the reference: outside ±20, no cause → FAIL; the space and the site fail.
    m = _measured_for(site)
    m["set"]["spaces"][0]["walls"][0]["openings"][0]["width_mm"] = 930
    out = ten_site.evaluate_site(ref, m)
    assert out["verdict"] == "FAIL" and out["openings"]["fail"] == 1 and out["spaces"]["pass"] == 0
    assert out["exceptions"][0]["quantity"] == "W1/O1/width"
    # Same reading with a recorded cause: EXPLAINED (inside 2×) and recorded, but the space still fails: closure
    # §2.2 needs every opening of a space within tolerance; EXPLAINED is a wall-level allowance.
    explained = ten_site.evaluate_site(ref.model_copy(update={"causes": {"Living/W1/O1": "Frame not yet fixed"}}), m)
    assert explained["openings"]["explained"] == 1 and explained["openings"]["fail"] == 0
    assert explained["verdict"] == "FAIL" and explained["spaces"]["pass"] == 0
    # Sill 30 mm off (±25) fails; so does an opening the reference does not have.
    m = _measured_for(site)
    m["set"]["spaces"][0]["walls"][0]["openings"][1]["sill_height_mm"] = 930
    assert ten_site.evaluate_site(ref, m)["openings"]["fail"] == 1
    m = _measured_for(site)
    m["set"]["spaces"][0]["walls"][2]["openings"] = [{"client_ref": "x", "opening_type_code": "WINDOW",
                                                     "width_mm": 600, "height_mm": 600}]  # fmt: skip
    assert ten_site.evaluate_site(ref, m)["exceptions"][0]["cause"] == "NOT_IN_REFERENCE"
    # Staircase: tread 12 mm off (±10) fails; run 8 mm off passes.
    stair = {"run_length_mm": 4000, "width_mm": 1100, "riser_height_mm": 170, "tread_depth_mm": 250}
    stair_site = {**site, "spaces": [{**site["spaces"][0], "staircase": stair}]}
    sref = ten_site.SiteRef.model_validate(stair_site)
    ok = ten_site.evaluate_site(sref, _measured_for(stair_site, stair={**stair, "run_length_mm": 4008}))
    assert ok["verdict"] == "PASS" and ok["staircase"]["pass"] == 4
    bad = ten_site.evaluate_site(sref, _measured_for(stair_site, stair={**stair, "tread_depth_mm": 262}))
    assert bad["verdict"] == "FAIL" and bad["staircase"]["fail"] == 1


def test_defect6_walls_rule_applies_without_areas_and_zero_walls_is_incomplete():
    site = _site()
    site["spaces"][0].update(length_mm=None, width_mm=None, ceiling_height_mm=None)
    ref = ten_site.SiteRef.model_validate(site)
    # One EXPLAINED wall in four is under the 95 % rule: FAIL even though no area is compared.
    m = _measured_for(site, walls=[3040, 4000, 3000, 4000])
    explained = ten_site.evaluate_site(ref.model_copy(update={"causes": {"Living/W1": "Skirting"}}), m)
    assert explained["walls"]["explained"] == 1 and explained["verdict"] == "FAIL"
    # Walls all PASS but no property total: INCOMPLETE, never PASS.
    out = ten_site.evaluate_site(ref, _measured_for(site))
    assert out["verdict"] == "INCOMPLETE" and out["incomplete_reasons"] == ["NO_PROPERTY_AREA_COMPARED"]
    # No wall compared at all: INCOMPLETE.
    site = _site()
    site["spaces"][0].update(walls=[], openings=[])
    out = ten_site.evaluate_site(ten_site.SiteRef.model_validate(site), _measured_for(site, walls=[]))
    assert out["verdict"] == "INCOMPLETE" and out["incomplete_reasons"] == ["NO_WALLS_COMPARED"]
    assert tolerance.site_verdict([], [True], None) == "INCOMPLETE"


def test_defect7_site_mix_needs_two_multi_level_houses_and_5_bhk_is_informational():
    ref, measured, events = _ten("LIVE")
    for s in ref["sites"][6:]:  # four of five houses on one level: only S06 has two
        s["levels"] = 1
        measured[s["site_id"]]["property"]["derived_level_count"] = 1
    evidence = _evaluate(ref, measured, events)
    assert evidence["coverage"]["missing"] == ["two_houses_with_two_or_more_levels"]
    assert evidence["label"] == "VALIDATION_FAILED"
    # A house must state its levels (cross-checked against the measured level count, defect 4).
    with pytest.raises(ValidationError, match="levels"):
        ten_site.SiteRef.model_validate(_site("S06", "INDEPENDENT_HOUSE", 3, None))
    # No 5 BHK anywhere: recorded as absent, not required.
    ref, measured, events = _ten("LIVE")
    evidence = _evaluate(ref, measured, events)
    info = evidence["coverage"]["informational"]
    assert info["has_5_bhk"] is False and info["five_bhk_note"].startswith("ABSENT")
    assert evidence["label"] == "LIVE_VALIDATED" and evidence["coverage"]["complete"]


def test_defect8_surveyor_time_is_recorded_against_the_03_section_13_baseline():
    ref, measured, events = _ten()
    ref["sites"][0]["survey_minutes"] = 140  # 2 BHK: 120–150
    ref["sites"][4]["survey_minutes"] = 300  # 4 BHK: 210–270
    evidence = _evaluate(ref, measured, events)
    by = {s["site_id"]: s["survey_time"] for s in evidence["sites"]}
    assert by["S01"]["against_baseline"] == "WITHIN" and by["S01"]["baseline_minutes"] == {"low": 120, "high": 150}
    assert by["S05"]["against_baseline"] == "ABOVE"
    assert by["S06"]["baseline_row"] == "Villa / independent house" and by["S06"]["against_baseline"] == "NOT_RECORDED"
    assert "S01" not in evidence["survey_time_not_recorded"] and "S06" in evidence["survey_time_not_recorded"]
    assert evidence["label"] == "SYNTHETIC_VALIDATED"  # absence is reported, not fatal


def test_defect9_evidence_is_bound_and_synthetic_is_never_live(tmp_path, monkeypatch):
    ref, measured, events = _ten()
    raw = json.dumps(ref).encode()
    (tmp_path / "ref.json").write_bytes(raw)
    (tmp_path / "measured.json").write_text(json.dumps(measured))
    (tmp_path / "events.json").write_text(json.dumps(events))
    monkeypatch.setenv("VEDA_GIT_SHA", "a" * 40)
    out = tmp_path / "evidence.json"
    rc = _tool().main(["--reference", str(tmp_path / "ref.json"), "--measured", str(tmp_path / "measured.json"),
                       "--events", str(tmp_path / "events.json"), "--database-engine", "postgresql",
                       "--generated-at", "2026-10-13T00:00:00Z", "--out", str(out)])  # fmt: skip
    evidence = json.loads(out.read_text())
    assert rc == 0 and evidence["label"] == "SYNTHETIC_VALIDATED" and evidence["dataset_kind"] == "SYNTHETIC"
    assert evidence["provenance"] == {
        "generator_commit": "a" * 40,
        "database_engine": "postgresql",
        "generated_at": "2026-10-13T00:00:00Z",
        "reference_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "template_version": templates.TEMPLATE_VERSION,
    }
    assert "LIVE_VALIDATED" not in out.read_text()
    # A LIVE dataset cannot carry a synthetic reference method.
    live = {**ref, "dataset_kind": "LIVE"}
    live["sites"][0]["reference_method"] = "SYNTHETIC_GENERATED"
    with pytest.raises(ValidationError, match="synthetic"):
        ten_site.Reference.model_validate(live)
