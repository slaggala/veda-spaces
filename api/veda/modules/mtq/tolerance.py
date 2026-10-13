"""The recorded tolerance policy (OI-MTQ-01, blocker closure §2) as code.

Two different things, never mixed:

- **Agreement tolerance** (closure §2.1, §2.2): how far an app measurement may differ from the reference method on the
  same site for the B1 validation gate. Used by the ten-site validation harness (B1-T12), never by capture.
- **Runtime thresholds** (closure §2.3): what verification enforces on every set, fail closed.

Both are integers in millimetres or basis points; nothing here is a pricing default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# --- runtime thresholds (closure §2.3) ---------------------------------------------------------------------------------
CLOSURE_MM = 50  # L_SHAPE and POLYGON walls close within 50 mm of the geometry
BUILT_UP_DEVIATION_BP = 2500  # derived total within ±25 % of the stated built-up area, or a verifier RISK_ACK
# Plausibility bounds that catch unit mistakes (feet keyed as millimetres and the like); outside them verification fails.
CEILING_HEIGHT_MM = (1800, 9000)  # double-height volumes allowed
ROOM_DIMENSION_MM = (600, 30_000)
WALL_LENGTH_MM = (100, 30_000)

# --- agreement tolerance (closure §2.1) --------------------------------------------------------------------------------
LONG_WALL_MM = 6000

Kind = Literal["wall", "ceiling", "opening_size", "opening_position", "space_area", "property_area", "staircase"]


def allowed(kind: Kind, reference: int) -> int:
    """The tolerated absolute difference for one compared quantity (mm, or for areas the same unit as ``reference``)."""
    if kind == "wall":
        return 25 if reference <= LONG_WALL_MM else 50
    if kind == "ceiling":
        return 25
    if kind == "opening_size":
        return 20
    if kind == "opening_position":
        return 25
    if kind == "staircase":
        return 10
    if kind == "space_area":
        # ±1 % or ±0.1 m², whichever is larger; 0.1 m² = 107.639 sq ft hundredths → 108 (rounded up, the lenient side)
        return max((reference + 99) // 100, 108)
    if kind == "property_area":
        return (reference + 99) // 100
    raise ValueError(kind)


Verdict = Literal["PASS", "EXPLAINED", "FAIL"]


@dataclass(frozen=True)
class Comparison:
    kind: str
    reference: int
    measured: int
    tolerance: int
    verdict: Verdict
    cause: str | None = None


def compare(kind: Kind, reference: int, measured: int, *, cause: str | None = None) -> Comparison:
    """Closure §2.2: within tolerance PASS; within twice the tolerance EXPLAINED when a cause is recorded; else FAIL."""
    tol = allowed(kind, reference)
    diff = abs(measured - reference)
    if diff <= tol:
        verdict: Verdict = "PASS"
    elif diff <= 2 * tol and cause:
        verdict = "EXPLAINED"
    else:
        verdict = "FAIL"
    return Comparison(kind, reference, measured, tol, verdict, cause)


SiteVerdict = Literal["PASS", "FAIL", "INCOMPLETE"]
GATE_SITES = 10


def site_verdict(walls: list[Comparison], spaces: list[bool], property_area: Comparison | None) -> SiteVerdict:
    """Closure §2.2 site rule: ≥ 95 % of compared walls PASS, no wall FAIL, every space PASS, property total within 1 %.

    The 95 % rule applies whenever walls are compared. A site with no compared wall, or with no property total to
    compare, has not shown the rule and is INCOMPLETE, never PASS. A failure already shown is FAIL.
    """
    if any(w.verdict == "FAIL" for w in walls):
        return "FAIL"
    passed = sum(1 for w in walls if w.verdict == "PASS")
    if walls and passed * 100 < 95 * len(walls):
        return "FAIL"
    if not all(spaces) or (property_area is not None and property_area.verdict != "PASS"):
        return "FAIL"
    if not walls or property_area is None:
        return "INCOMPLETE"
    return "PASS"


def gate_verdict(sites: list[tuple[str, str, str | None]]) -> Literal["PASS", "FAIL", "INCOMPLETE"]:
    """Closure §2.2 gate: ≥ 9 of 10 sites PASS and no FAIL shares a root cause with another; ``sites`` holds
    (site_id, verdict, root_cause).

    The gate is defined over exactly ten sites. Fewer is INCOMPLETE, never PASS; more is not this gate and is refused
    (ValueError), so a larger dataset can never pass on a count of nine. A FAIL without a recorded root cause cannot be
    shown to be isolated and fails the gate. A site that is INCOMPLETE (unverified set, nothing compared) keeps the gate
    INCOMPLETE unless the sites already fail it.
    """
    if len(sites) > GATE_SITES:
        raise ValueError(f"the gate is defined over exactly {GATE_SITES} sites, {len(sites)} given")
    if len({s[0] for s in sites}) != len(sites):
        raise ValueError("a site appears twice")
    if len(sites) < GATE_SITES:
        return "INCOMPLETE"
    passed = sum(1 for s in sites if s[1] == "PASS")
    incomplete = sum(1 for s in sites if s[1] == "INCOMPLETE")
    causes = [s[2] for s in sites if s[1] == "FAIL"]
    if passed + incomplete < GATE_SITES - 1 or len(causes) != len(set(causes)) or None in causes:
        return "FAIL"
    if incomplete or any(s[1] not in ("PASS", "FAIL") for s in sites):
        return "INCOMPLETE"
    return "PASS"
