"""Ten-site validation support (MTQ B1-T12; blocker closure §2.1, §2.2; B1-SCOPE §5 exit).

Compares what the app recorded for each site with an independent reference measurement of the same site, using the
recorded agreement tolerance (tolerance.py), and labels the result. Pure functions over JSON: no database, no
network. The ten-site harness test feeds it synthetic sites driven through the real API; ``tools/mtq_ten_site.py``
feeds it a dataset from files (the owner's reference measurements and the sets exported from protected staging).

Labels, never mixed and never inferred:

- ``LIVE_VALIDATED``: a LIVE dataset of exactly ten referenced sites, each with a VERIFIED measured set, every
  coverage requirement met, gate PASS.
- ``SYNTHETIC_VALIDATED``: the same for a SYNTHETIC dataset. It proves the pipeline and the rules, not field accuracy.
  A SYNTHETIC dataset can never carry a LIVE label, and a LIVE dataset cannot carry a synthetic reference method.
- ``VALIDATION_FAILED``: ten referenced sites and the gate is not PASS (FAIL or INCOMPLETE: a site without a measured
  set, an unverified set, a site with nothing compared), or coverage is incomplete.
- ``UNVALIDATED_NO_REFERENCE``: fewer than ten sites carry a reference measurement. Nothing is claimed.

What is compared, per site (closure §2.1 tolerances, §2.2 rules):

- **Walls** by ``wall_index``: PASS within tolerance, EXPLAINED within twice the tolerance when a cause is recorded
  (key ``"<space>/W<i>"``), FAIL otherwise. A reference wall with no recorded length is FAIL.
- **Openings**, matched deterministically: on each wall, the reference openings and the recorded openings are both
  ordered along the wall (offset from the wall's start corner ascending; openings without an offset after those with
  one, reference in listed order, recorded by ``client_ref``) and paired by position. Width and height against
  ``opening_size``; offset and sill (when the reference gives them) against ``opening_position``; the opening type
  must agree. An unpaired opening on either side is FAIL. Causes are keyed ``"<space>/W<i>/O<k>"``.
- **Staircase** run, width, riser and tread (``attributes.staircase``) against ``staircase``; causes keyed
  ``"<space>/staircase"``.
- **Space**: PASS only when every opening, every staircase value and the area are within tolerance (PASS, not
  EXPLAINED: closure §2.2 says "within tolerance" for openings and area and reserves EXPLAINED for walls), the ceiling
  is not FAIL, and no wall is FAIL.
- **Site**: closure §2.2 site rule (tolerance.site_verdict). INCOMPLETE when the measured set is not VERIFIED, when no
  wall was compared, or when there is no property total to compare. FAIL when the measured property's type, bedroom
  count or level count disagrees with the reference.
- **Surveyor time**: recorded per site against the 03 §13 baseline row; reported, never part of the verdict.

Evidence carries anonymous site ids, dimensions and verdicts only: no customer name, phone, address, lead id, rate
or amount.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from veda.kernel import clock
from veda.kernel.dto import Closed

from . import tolerance
from .derivation import mm2_to_sqft_centi

LABELS = ("LIVE_VALIDATED", "SYNTHETIC_VALIDATED", "VALIDATION_FAILED", "UNVALIDATED_NO_REFERENCE")
MM = Annotated[int, Field(ge=1, le=60_000)]
NON_NEGATIVE_MM = Annotated[int, Field(ge=0, le=60_000)]
_LAST = 10**9  # sort key for an opening without an offset: after every positioned opening
NO_5_BHK = "ABSENT: no 5 BHK site in this dataset (not required by closure section 2.2; recorded, never filled in)"

# 03-measurement-visit-playbook §13 on-site time, in minutes (low, high), by configuration. Estimates until measured.
SURVEY_BASELINE_MINUTES: dict[str, tuple[int, int]] = {
    "2 BHK": (120, 150),
    "3 BHK": (150, 210),
    "4 BHK": (210, 270),
    "5 BHK": (270, 360),
    "Villa / independent house": (360, 600),
}


class OpeningRef(Closed):
    wall: Annotated[int, Field(ge=1, le=64)]  # the wall_index it sits on
    opening_type_code: Annotated[str | None, Field(max_length=40)] = None
    width_mm: MM
    height_mm: MM
    offset_from_wall_start_mm: NON_NEGATIVE_MM | None = None
    sill_height_mm: NON_NEGATIVE_MM | None = None


class StaircaseRef(Closed):
    run_length_mm: MM | None = None
    width_mm: MM | None = None
    riser_height_mm: MM | None = None
    tread_depth_mm: MM | None = None


class SpaceRef(Closed):
    label: Annotated[str, Field(min_length=1, max_length=80)]
    length_mm: MM | None = None  # None: no area comparison (a staircase, a freeform space)
    width_mm: MM | None = None
    ceiling_height_mm: MM | None = None
    walls: Annotated[list[MM], Field(max_length=64)] = []  # wall lengths by wall_index 1..n
    openings: Annotated[list[OpeningRef], Field(max_length=200)] = []  # every opening of the space (see matching)
    staircase: StaircaseRef | None = None


class SiteRef(Closed):
    site_id: Annotated[str, Field(pattern=r"^S[0-9]{2}$")]  # anonymous: never a customer or lead identifier
    property_type_code: Literal["APARTMENT", "INDEPENDENT_HOUSE"]
    bedrooms: Annotated[int, Field(ge=1, le=10)]
    levels: Annotated[int, Field(ge=1, le=14)] | None = None  # required for a house; an apartment without it is 1
    survey_level_code: Literal["LITE", "FULL"]
    method_code: Literal["TAPE", "LASER"] = "LASER"
    reference_method: Annotated[str, Field(min_length=1, max_length=80)]
    spaces: Annotated[list[SpaceRef], Field(min_length=1, max_length=80)]
    # Recorded causes, keyed "<space>", "<space>/W<i>", "<space>/W<i>/O<k>" or "<space>/staircase".
    causes: dict[Annotated[str, Field(max_length=100)], Annotated[str, Field(max_length=200)]] = {}
    root_cause: Annotated[str | None, Field(max_length=200)] = None
    survey_minutes: Annotated[int, Field(ge=1, le=2880)] | None = None  # on-site surveyor time, closure §2.2

    @model_validator(mode="after")
    def _levels(self):
        if self.property_type_code == "INDEPENDENT_HOUSE" and self.levels is None:
            raise ValueError("an independent house states its number of levels (closure §2.2 site mix)")
        labels = [sp.label for sp in self.spaces]
        if len(set(labels)) != len(labels):
            raise ValueError("a space label repeats within a site")
        return self

    @property
    def level_count(self) -> int:
        return self.levels or 1


class Reference(Closed):
    dataset_id: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,60}$")]
    dataset_kind: Literal["SYNTHETIC", "LIVE"]
    # The gate is defined over exactly ten sites (closure §2.2): more is not a valid reference.
    sites: Annotated[list[SiteRef], Field(max_length=tolerance.GATE_SITES)]

    @model_validator(mode="after")
    def _distinct(self):
        ids = [s.site_id for s in self.sites]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"site ids repeat: {', '.join(dupes)}")
        if self.dataset_kind == "LIVE":
            synthetic = sorted(s.site_id for s in self.sites if s.reference_method.upper().startswith("SYNTHETIC"))
            if synthetic:
                raise ValueError(f"a LIVE dataset cannot carry a synthetic reference: {', '.join(synthetic)}")
        return self


def _cmp(kind: tolerance.Kind, ref: int, measured: Any, cause: str | None) -> tolerance.Comparison:
    if measured is None:  # nothing recorded where the reference has a value: a failure, never a skip
        return tolerance.Comparison(kind, ref, -1, tolerance.allowed(kind, ref), "FAIL", cause or "NOT_RECORDED")
    return tolerance.compare(kind, ref, int(measured), cause=cause)


def _row(label: str, quantity: str, c: tolerance.Comparison) -> dict[str, Any]:
    return {"space": label, "quantity": quantity, "reference": c.reference, "measured": c.measured,
            "tolerance": c.tolerance, "verdict": c.verdict, "cause": c.cause}  # fmt: skip


def _tally(cs: list[tolerance.Comparison]) -> dict[str, int]:
    return {
        "compared": len(cs),
        "pass": sum(1 for c in cs if c.verdict == "PASS"),
        "explained": sum(1 for c in cs if c.verdict == "EXPLAINED"),
        "fail": sum(1 for c in cs if c.verdict == "FAIL"),
    }


def _baseline(ref: SiteRef) -> tuple[str | None, tuple[int, int] | None]:
    row: str | None
    if ref.property_type_code == "INDEPENDENT_HOUSE":
        row = "Villa / independent house"
    elif ref.bedrooms >= 5:
        row = "5 BHK"
    else:
        row = f"{ref.bedrooms} BHK" if ref.bedrooms >= 2 else None
    return row, SURVEY_BASELINE_MINUTES.get(row) if row else None


def survey_time(ref: SiteRef) -> dict[str, Any]:
    """Closure §2.2: surveyor time per site recorded against the 03 §13 baseline. Reported; never a verdict input."""
    row, band = _baseline(ref)
    if ref.survey_minutes is None:
        against = "NOT_RECORDED"
    elif band is None:
        against = "NO_BASELINE_ROW"
    elif ref.survey_minutes < band[0]:
        against = "BELOW"
    elif ref.survey_minutes > band[1]:
        against = "ABOVE"
    else:
        against = "WITHIN"
    return {
        "minutes": ref.survey_minutes,
        "baseline_row": row,
        "baseline_minutes": None if band is None else {"low": band[0], "high": band[1]},
        "baseline_source": "03-measurement-visit-playbook.md section 13",
        "against_baseline": against,
    }


OPENING_QUANTITIES: tuple[tuple[tolerance.Kind, str, str], ...] = (
    ("opening_size", "width", "width_mm"),
    ("opening_size", "height", "height_mm"),
    ("opening_position", "offset", "offset_from_wall_start_mm"),
    ("opening_position", "sill", "sill_height_mm"),
)


def _along(offset: int | None) -> int:
    """Sort key along a wall: by offset from the start corner; an opening without an offset after every other."""
    return _LAST if offset is None else int(offset)


def _openings(label: str, sp: SpaceRef, sm: dict[str, Any], causes: dict[str, str], rows: list[dict[str, Any]]):
    """Compare a space's openings wall by wall (matching rule in the module docstring)."""
    out: list[tolerance.Comparison] = []
    recorded_walls = {w["wall_index"]: w.get("openings") or [] for w in sm.get("walls") or []}
    ref_by_wall: dict[int, list[OpeningRef]] = {}
    for o in sp.openings:
        ref_by_wall.setdefault(o.wall, []).append(o)
    for wall in sorted(set(ref_by_wall) | {i for i, ops in recorded_walls.items() if ops}):
        listed = list(enumerate(ref_by_wall.get(wall, [])))
        refs = [o for _, o in sorted(listed, key=lambda t: (_along(t[1].offset_from_wall_start_mm), t[0]))]
        got = sorted(
            recorded_walls.get(wall, []),
            key=lambda o: (_along(o.get("offset_from_wall_start_mm")), str(o.get("client_ref") or "")),
        )
        for k in range(max(len(refs), len(got))):
            q = f"W{wall}/O{k + 1}"
            cause = causes.get(f"{label}/{q}")
            if k >= len(refs):  # recorded, but the reference has no such opening
                c = tolerance.Comparison("opening_size", 0, int(got[k].get("width_mm") or 0), 0, "FAIL",
                                         "NOT_IN_REFERENCE")  # fmt: skip
                out.append(c)
                rows.append(_row(label, f"{q}/opening", c))
                continue
            r, m = refs[k], (got[k] if k < len(got) else {})
            if r.opening_type_code and m and m.get("opening_type_code") != r.opening_type_code:
                c = tolerance.Comparison("opening_size", r.width_mm, int(m.get("width_mm") or 0), 0, "FAIL",
                                         f"TYPE_MISMATCH {r.opening_type_code}/{m.get('opening_type_code')}")  # fmt: skip
                out.append(c)
                rows.append(_row(label, f"{q}/type", c))
            for kind, name, field in OPENING_QUANTITIES:
                value = getattr(r, field)
                if value is None:  # the reference did not capture it: nothing to compare
                    continue
                c = _cmp(kind, value, m.get(field), cause)
                out.append(c)
                if c.verdict != "PASS":
                    rows.append(_row(label, f"{q}/{name}", c))
    return out


def _staircase(label: str, sp: SpaceRef, sm: dict[str, Any], causes: dict[str, str], rows: list[dict[str, Any]]):
    out: list[tolerance.Comparison] = []
    if sp.staircase is None:
        return out
    got = (sm.get("attributes") or {}).get("staircase") or {}
    cause = causes.get(f"{label}/staircase")
    for field in ("run_length_mm", "width_mm", "riser_height_mm", "tread_depth_mm"):
        value = getattr(sp.staircase, field)
        if value is None:
            continue
        c = _cmp("staircase", value, got.get(field), cause)
        out.append(c)
        if c.verdict != "PASS":
            rows.append(_row(label, f"staircase/{field[:-3]}", c))
    return out


def profile_mismatches(ref: SiteRef, prop: dict[str, Any]) -> list[dict[str, Any]]:
    """The reference's property type, bedroom count and level count against the measured property's."""
    pairs = (
        ("property_type_code", ref.property_type_code, prop.get("property_type_code")),
        ("bedrooms", ref.bedrooms, prop.get("derived_bedroom_count")),
        ("levels", ref.level_count, prop.get("derived_level_count")),
    )
    return [{"field": f, "reference": r, "measured": m} for f, r, m in pairs if r != m]


def evaluate_site(ref: SiteRef, measured: dict[str, Any], events: dict[str, bool] | None = None) -> dict[str, Any]:
    """One site. ``measured`` is ``{"set": <GET /measurement-sets/{id}>, "property": <GET /properties/{id}>}``."""
    labels = {sp["id"]: sp["label"] for sp in measured["property"].get("spaces") or []}
    by_label = {labels.get(sm["space_id"]): sm for sm in measured["set"].get("spaces") or []}
    walls: list[tolerance.Comparison] = []
    openings: list[tolerance.Comparison] = []
    stairs: list[tolerance.Comparison] = []
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
            ok &= c.verdict != "FAIL"
            if c.verdict != "PASS":
                rows.append(_row(sp.label, f"W{i}", c))
        sp_openings = _openings(sp.label, sp, sm, ref.causes, rows)
        sp_stairs = _staircase(sp.label, sp, sm, ref.causes, rows)
        ok &= all(c.verdict == "PASS" for c in sp_openings + sp_stairs)
        openings += sp_openings
        stairs += sp_stairs
        space_ok.append(ok)
    prop = tolerance.compare("property_area", ref_total, got_total) if ref_total else None
    verdict: str = tolerance.site_verdict(walls, space_ok, prop)
    incomplete: list[str] = []
    mset = measured["set"]
    if not walls:
        incomplete.append("NO_WALLS_COMPARED")
    if prop is None:
        incomplete.append("NO_PROPERTY_AREA_COMPARED")
    mismatches = profile_mismatches(ref, measured["property"])
    if mismatches:
        verdict = "FAIL"
    if mset.get("status") != "VERIFIED":
        incomplete.insert(0, f"SET_NOT_VERIFIED ({mset.get('status')})")
        verdict = "INCOMPLETE"
    return {
        "site_id": ref.site_id,
        "property_type_code": ref.property_type_code,
        "bedrooms": ref.bedrooms,
        "levels": ref.level_count,
        "measured_profile": {
            "property_type_code": measured["property"].get("property_type_code"),
            "bedrooms": measured["property"].get("derived_bedroom_count"),
            "levels": measured["property"].get("derived_level_count"),
        },
        "profile_mismatches": mismatches,
        "survey_level_code": ref.survey_level_code,
        "method_code": ref.method_code,
        "reference_method": ref.reference_method,
        "set_status": mset.get("status"),
        "revision_no": mset.get("revision_no"),
        # The sealed revision's digest, "sha256:"-prefixed (a digest, not a secret, for the repository's scanners).
        "snapshot": f"sha256:{mset['snapshot_sha256']}" if mset.get("snapshot_sha256") else None,
        "spaces": {"compared": len(space_ok), "pass": sum(space_ok)},
        "walls": _tally(walls),
        "openings": _tally(openings),
        "staircase": _tally(stairs),
        "property_area": None
        if prop is None
        else {
            "reference": prop.reference,
            "measured": prop.measured,
            "tolerance": prop.tolerance,
            "verdict": prop.verdict,
        },  # fmt: skip
        "verdict": verdict,
        "incomplete_reasons": incomplete if verdict == "INCOMPLETE" else [],
        "root_cause": ref.root_cause if verdict == "FAIL" else None,
        "survey_time": survey_time(ref),
        "exceptions": rows,
        "events": {"second_surveyor_conflict": False, "offline_retry": False, **(events or {})},
    }


def coverage(sites: list[dict[str, Any]]) -> dict[str, Any]:
    """The closure §2.2 site mix and the B1-T12 dataset requirements, over sites whose reference profile agrees with
    the measured property: five apartments covering 2, 3 and 4 BHK; five independent houses, at least two with two or
    more levels; Lite and Full surveys; at least one second-surveyor conflict and one offline retry. A 5 BHK is
    reported (``has_5_bhk``) but not required: closure §2.2 does not ask for one; its absence is recorded."""
    agreed = [s for s in sites if not s["profile_mismatches"]]
    apartments = [s for s in agreed if s["property_type_code"] == "APARTMENT"]
    houses = [s for s in agreed if s["property_type_code"] == "INDEPENDENT_HOUSE"]
    need = {
        "profiles_agree": len(agreed) == len(sites),
        "five_apartments": len(apartments) >= 5,
        "apartments_cover_2_3_4_bhk": {2, 3, 4} <= {s["bedrooms"] for s in apartments},
        "five_independent_houses": len(houses) >= 5,
        "two_houses_with_two_or_more_levels": sum(1 for s in houses if s["levels"] >= 2) >= 2,
        "lite_and_full": {"LITE", "FULL"} <= {s["survey_level_code"] for s in sites},
        "second_surveyor_conflict": any(s["events"]["second_surveyor_conflict"] for s in sites),
        "offline_retry": any(s["events"]["offline_retry"] for s in sites),
    }
    five = sorted(s["site_id"] for s in agreed if s["bedrooms"] >= 5)
    return {
        **need,
        "complete": all(need.values()),
        "missing": sorted(k for k, v in need.items() if not v),
        "profile_mismatch_sites": sorted(s["site_id"] for s in sites if s["profile_mismatches"]),
        "informational": {
            "has_5_bhk": bool(five),
            "five_bhk_sites": five,
            "five_bhk_note": "present" if five else NO_5_BHK,
        },
    }


def reference_digest(reference: Reference) -> str:
    """A digest of the reference as parsed, for evidence produced without the source file."""
    return "sha256:" + hashlib.sha256(reference.model_dump_json().encode()).hexdigest()


def evaluate(
    reference: Reference,
    measured: dict[str, dict[str, Any]],
    events: dict[str, dict[str, bool]] | None = None,
    *,
    template_version: str,
    provenance: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The evidence document for a dataset. A reference site without a measured set is listed and counts as
    INCOMPLETE at the gate; a measured set without a reference site is refused (ValueError).

    ``provenance`` binds the evidence: ``generator_commit``, ``database_engine``, ``reference_sha256`` (of the
    reference file, ``sha256:``-prefixed) and optionally ``generated_at``. Missing values are recorded as unknown (the
    reference digest falls back to a digest of the parsed reference)."""
    events = events or {}
    known = {r.site_id for r in reference.sites}
    stray = sorted(set(measured) - known)
    if stray:
        raise ValueError(f"measured sets for sites the reference does not list: {', '.join(stray)}")
    sites = [
        evaluate_site(r, measured[r.site_id], events.get(r.site_id)) for r in reference.sites if r.site_id in measured
    ]
    unmeasured = sorted(r.site_id for r in reference.sites if r.site_id not in measured)
    gate = tolerance.gate_verdict(
        [(s["site_id"], s["verdict"], s["root_cause"]) for s in sites] + [(i, "INCOMPLETE", None) for i in unmeasured]
    )
    cov = coverage(sites)
    if len(reference.sites) < tolerance.GATE_SITES:
        label = "UNVALIDATED_NO_REFERENCE"
    elif gate == "PASS" and cov["complete"] and not unmeasured:
        label = "LIVE_VALIDATED" if reference.dataset_kind == "LIVE" else "SYNTHETIC_VALIDATED"
    else:
        label = "VALIDATION_FAILED"
    p = provenance or {}
    return {
        "evidence": "MTQ-B1-TEN-SITE-VALIDATION",
        "dataset_id": reference.dataset_id,
        "dataset_kind": reference.dataset_kind,
        "template_version": template_version,
        "provenance": {
            "generator_commit": p.get("generator_commit") or "unknown",
            "database_engine": p.get("database_engine") or "unknown",
            "generated_at": p.get("generated_at") or clock.to_rfc3339(clock.now()),
            "reference_sha256": p.get("reference_sha256") or reference_digest(reference),
            "template_version": template_version,
        },
        "tolerance_policy": "OI-MTQ-01 (MTQ-B1-blocker-closure.md section 2)",
        "label": label,
        "gate_verdict": gate,
        "sites_referenced": len(reference.sites),
        "sites_evaluated": len(sites),
        "sites_without_a_measured_set": unmeasured,
        "sites_incomplete": sorted([s["site_id"] for s in sites if s["verdict"] == "INCOMPLETE"] + unmeasured),
        "survey_time_not_recorded": sorted(r.site_id for r in reference.sites if r.survey_minutes is None),
        "coverage": cov,
        "sites": sites,
    }
