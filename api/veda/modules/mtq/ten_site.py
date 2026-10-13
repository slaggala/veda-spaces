"""Ten-site validation support (MTQ B1-T12; blocker closure §2.1, §2.2; B1-SCOPE §5 exit).

Compares what the app recorded for each site with an independent reference measurement of the same site, using the
recorded agreement tolerance (tolerance.py), and labels the result. Pure functions over JSON: no database, no
network. The ten-site harness test feeds it synthetic sites driven through the real API; ``tools/mtq_ten_site.py``
feeds it a live dataset (the owner's reference measurements and the sets exported from protected staging).

Labels, never mixed and never inferred:

- ``LIVE_VALIDATED``: a LIVE dataset, every coverage requirement met, gate PASS.
- ``SYNTHETIC_VALIDATED``: the same for a SYNTHETIC dataset. It proves the pipeline and the rules, not field accuracy.
- ``VALIDATION_FAILED``: references for ten sites exist and the gate failed, or coverage is incomplete.
- ``UNVALIDATED_NO_REFERENCE``: fewer than ten sites carry a reference measurement. Nothing is claimed.

Evidence carries anonymous site ids, dimensions and verdicts only: no customer name, phone, address, lead id, rate
or amount.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from veda.kernel.dto import Closed

from . import tolerance
from .derivation import mm2_to_sqft_centi

LABELS = ("LIVE_VALIDATED", "SYNTHETIC_VALIDATED", "VALIDATION_FAILED", "UNVALIDATED_NO_REFERENCE")
MM = Annotated[int, Field(ge=1, le=60_000)]


class SpaceRef(Closed):
    label: Annotated[str, Field(min_length=1, max_length=80)]
    length_mm: MM | None = None  # None: no area comparison (a staircase, a freeform space)
    width_mm: MM | None = None
    ceiling_height_mm: MM | None = None
    walls: Annotated[list[MM], Field(max_length=64)] = []  # wall lengths by wall_index 1..n


class SiteRef(Closed):
    site_id: Annotated[str, Field(pattern=r"^S[0-9]{2}$")]  # anonymous: never a customer or lead identifier
    property_type_code: Literal["APARTMENT", "INDEPENDENT_HOUSE"]
    bedrooms: Annotated[int, Field(ge=1, le=10)]
    survey_level_code: Literal["LITE", "FULL"]
    method_code: Literal["TAPE", "LASER"] = "LASER"
    reference_method: Annotated[str, Field(min_length=1, max_length=80)]
    spaces: Annotated[list[SpaceRef], Field(min_length=1, max_length=80)]
    # Recorded causes, keyed "<space label>" or "<space label>/W<index>" (closure §2.2: EXPLAINED needs a cause).
    causes: dict[Annotated[str, Field(max_length=90)], Annotated[str, Field(max_length=200)]] = {}
    root_cause: Annotated[str | None, Field(max_length=200)] = None


class Reference(Closed):
    dataset_id: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,60}$")]
    dataset_kind: Literal["SYNTHETIC", "LIVE"]
    sites: Annotated[list[SiteRef], Field(max_length=20)]


def _cmp(kind: tolerance.Kind, ref: int, measured: int | None, cause: str | None) -> tolerance.Comparison:
    if measured is None:  # nothing recorded where the reference has a value: a failure, never a skip
        return tolerance.Comparison(kind, ref, -1, tolerance.allowed(kind, ref), "FAIL", cause or "NOT_RECORDED")
    return tolerance.compare(kind, ref, int(measured), cause=cause)


def _row(label: str, quantity: str, c: tolerance.Comparison) -> dict[str, Any]:
    return {"space": label, "quantity": quantity, "reference": c.reference, "measured": c.measured,
            "tolerance": c.tolerance, "verdict": c.verdict, "cause": c.cause}  # fmt: skip


def evaluate_site(ref: SiteRef, measured: dict[str, Any], events: dict[str, bool] | None = None) -> dict[str, Any]:
    """One site. ``measured`` is ``{"set": <GET /measurement-sets/{id}>, "property": <GET /properties/{id}>}``."""
    labels = {sp["id"]: sp["label"] for sp in measured["property"]["spaces"]}
    by_label = {labels.get(sm["space_id"]): sm for sm in measured["set"]["spaces"]}
    walls: list[tolerance.Comparison] = []
    space_ok: list[bool] = []
    rows: list[dict[str, Any]] = []
    ref_total = got_total = 0
    for sp in ref.spaces:
        sm = by_label.get(sp.label)
        if sm is None:
            space_ok.append(False)
            rows.append({"space": sp.label, "quantity": "space", "verdict": "FAIL", "cause": "NOT_MEASURED"})
            continue
        ok = True
        if sp.ceiling_height_mm is not None:
            c = _cmp("ceiling", sp.ceiling_height_mm, sm.get("ceiling_height_mm"), ref.causes.get(sp.label))
            ok &= c.verdict != "FAIL"
            if c.verdict != "PASS":
                rows.append(_row(sp.label, "ceiling", c))
        if sp.length_mm and sp.width_mm:
            area = mm2_to_sqft_centi(sp.length_mm * sp.width_mm)
            got = sm.get("derived_floor_area_sqft_centi")
            c = _cmp("space_area", area, got, ref.causes.get(sp.label))
            ok &= c.verdict == "PASS"
            ref_total += area
            got_total += int(got or 0)
            if c.verdict != "PASS":
                rows.append(_row(sp.label, "area", c))
        recorded = {w["wall_index"]: w.get("length_mm") for w in sm.get("walls") or []}
        for i, length in enumerate(sp.walls, start=1):
            c = _cmp("wall", length, recorded.get(i), ref.causes.get(f"{sp.label}/W{i}"))
            walls.append(c)
            if c.verdict != "PASS":
                rows.append(_row(sp.label, f"W{i}", c))
        space_ok.append(ok)
    prop = tolerance.compare("property_area", ref_total, got_total) if ref_total else None
    verdict = (
        tolerance.site_verdict(walls, space_ok, prop)
        if prop is not None
        else ("FAIL" if not all(space_ok) or any(w.verdict == "FAIL" for w in walls) else "PASS")
    )
    mset = measured["set"]
    return {
        "site_id": ref.site_id,
        "property_type_code": ref.property_type_code,
        "bedrooms": ref.bedrooms,
        "survey_level_code": ref.survey_level_code,
        "method_code": ref.method_code,
        "reference_method": ref.reference_method,
        "set_status": mset.get("status"),
        "revision_no": mset.get("revision_no"),
        # The sealed revision's digest, "sha256:"-prefixed (a digest, not a secret, for the repository's scanners).
        "snapshot": f"sha256:{mset['snapshot_sha256']}" if mset.get("snapshot_sha256") else None,
        "spaces": {"compared": len(space_ok), "pass": sum(space_ok)},
        "walls": {
            "compared": len(walls),
            "pass": sum(1 for w in walls if w.verdict == "PASS"),
            "explained": sum(1 for w in walls if w.verdict == "EXPLAINED"),
            "fail": sum(1 for w in walls if w.verdict == "FAIL"),
        },
        "property_area": None
        if prop is None
        else {
            "reference": prop.reference,
            "measured": prop.measured,
            "tolerance": prop.tolerance,
            "verdict": prop.verdict,
        },  # fmt: skip
        "verdict": verdict,
        "root_cause": ref.root_cause if verdict == "FAIL" else None,
        "exceptions": rows,
        "events": {"second_surveyor_conflict": False, "offline_retry": False, **(events or {})},
    }


def coverage(sites: list[dict[str, Any]]) -> dict[str, Any]:
    """The B1-T12 dataset requirements: five apartments covering 2, 3 and 4 BHK, five independent houses, at least
    one 5 BHK, Lite and Full surveys, at least one second-surveyor conflict and one offline retry."""
    apartments = [s for s in sites if s["property_type_code"] == "APARTMENT"]
    houses = [s for s in sites if s["property_type_code"] == "INDEPENDENT_HOUSE"]
    need = {
        "five_apartments": len(apartments) >= 5,
        "apartments_cover_2_3_4_bhk": {2, 3, 4} <= {s["bedrooms"] for s in apartments},
        "five_independent_houses": len(houses) >= 5,
        "at_least_one_5_bhk": any(s["bedrooms"] >= 5 for s in sites),
        "lite_and_full": {"LITE", "FULL"} <= {s["survey_level_code"] for s in sites},
        "second_surveyor_conflict": any(s["events"]["second_surveyor_conflict"] for s in sites),
        "offline_retry": any(s["events"]["offline_retry"] for s in sites),
    }
    return {**need, "complete": all(need.values()), "missing": sorted(k for k, v in need.items() if not v)}


def evaluate(
    reference: Reference,
    measured: dict[str, dict[str, Any]],
    events: dict[str, dict[str, bool]] | None = None,
    *,
    template_version: str,
) -> dict[str, Any]:
    """The evidence document for a dataset. Sites without a measured set are reported, never evaluated."""
    events = events or {}
    sites = [
        evaluate_site(r, measured[r.site_id], events.get(r.site_id)) for r in reference.sites if r.site_id in measured
    ]
    unmeasured = sorted(r.site_id for r in reference.sites if r.site_id not in measured)
    gate = tolerance.gate_verdict([(s["site_id"], s["verdict"], s["root_cause"]) for s in sites])
    cov = coverage(sites)
    if len(sites) < 10:
        label = "UNVALIDATED_NO_REFERENCE"
    elif gate == "PASS" and cov["complete"]:
        label = "LIVE_VALIDATED" if reference.dataset_kind == "LIVE" else "SYNTHETIC_VALIDATED"
    else:
        label = "VALIDATION_FAILED"
    return {
        "evidence": "MTQ-B1-TEN-SITE-VALIDATION",
        "dataset_id": reference.dataset_id,
        "dataset_kind": reference.dataset_kind,
        "template_version": template_version,
        "tolerance_policy": "OI-MTQ-01 (MTQ-B1-blocker-closure.md section 2)",
        "label": label,
        "gate_verdict": gate,
        "sites_evaluated": len(sites),
        "sites_without_a_measured_set": unmeasured,
        "coverage": cov,
        "sites": sites,
    }
