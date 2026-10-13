"""L-shape and staircase geometry (MTQ B1-T08; B1-SCOPE §2.4, §2.9.1; AR-19).

**L-shape.** Leg A contains the entry wall (W1, width ``w_a``) and runs ``l_a`` into the room. Leg B continues
sideways from the far end of leg A, turning LEFT or RIGHT as seen standing at W1 facing in: it adds ``l_b`` beyond leg
A's side over a depth of ``w_b`` (``w_b ≤ l_a``). The six walls, clockwise from W1, are therefore

    RIGHT turn: w_a, l_a − w_b, l_b, w_b, w_a + l_b, l_a
    LEFT turn:  w_a, l_a, w_a + l_b, w_b, l_b, l_a − w_b

Floor area is leg A + leg B; perimeter is 2 × (l_a + w_a + l_b). Verification fails when the six walls do not match
these lengths within 50 mm (closure tolerance, OI-MTQ-01 §2.3).

**Staircase.** A typed space: geometry in ``attributes.staircase``; every stairwell wall segment is its own wall row
with its own height (mean height for a sloped segment); headroom under 2 m or a largest panel under 900 mm needs a
RISK note on the staircase.
"""

from __future__ import annotations

from typing import Any

from . import tolerance
from .verification import EXTRA_SPACE_CHECKS, problem


def l_shape_walls(legs: dict[str, Any]) -> list[int]:
    a, b = legs["leg_a"], legs["leg_b"]
    la, wa, lb, wb = int(a["l_mm"]), int(a["w_mm"]), int(b["l_mm"]), int(b["w_mm"])
    if legs["turn_code"] == "RIGHT":
        return [wa, la - wb, lb, wb, wa + lb, la]
    return [wa, la, wa + lb, wb, lb, la - wb]


def l_shape_vertices(legs: dict[str, Any]) -> list[tuple[int, int]]:
    """Reconstructed outline in mm, W1 on the x axis from the origin (for drawings and polygon tools)."""
    a, b = legs["leg_a"], legs["leg_b"]
    la, wa, lb, wb = int(a["l_mm"]), int(a["w_mm"]), int(b["l_mm"]), int(b["w_mm"])
    if legs["turn_code"] == "RIGHT":
        return [(0, 0), (wa, 0), (wa, la - wb), (wa + lb, la - wb), (wa + lb, la), (0, la)]
    return [(0, 0), (wa, 0), (wa, la), (-lb, la), (-lb, la - wb), (0, la - wb)]


def _l_shape_problems(sp, m: dict[str, Any], level: str, gate: str) -> list[dict]:
    if m.get("shape_code") != "L_SHAPE":
        return []
    ptr = f"/spaces/{sp.id}"
    legs = (m.get("attributes") or {}).get("l_shape")
    if not legs:
        return [problem(ptr, "L_SHAPE_LEGS_REQUIRED", "Give the two legs and the turn of the L.", space=sp.label)]
    if int(legs["leg_b"]["w_mm"]) > int(legs["leg_a"]["l_mm"]):
        return [problem(ptr, "L_SHAPE_INVALID", "Leg B's depth cannot exceed leg A's length.", space=sp.label)]
    if gate != "verify":
        return []
    walls = [w for w in m.get("walls") or [] if w.get("wall_index", 0) >= 1]
    expected = l_shape_walls(legs)
    if len(walls) != 6:
        return [problem(ptr, "L_SHAPE_NOT_CLOSED", "An L-shaped space has exactly six walls.", space=sp.label)]
    got = [int(w["length_mm"]) for w in sorted(walls, key=lambda w: w["wall_index"])]
    worst = max(abs(x - y) for x, y in zip(got, expected, strict=True))
    if worst > tolerance.CLOSURE_MM:
        return [problem(ptr, "L_SHAPE_NOT_CLOSED",
                        f"The walls differ from the legs by up to {worst} mm (50 mm allowed).", space=sp.label,
                        expected_mm=expected)]  # fmt: skip
    return []


def _staircase_problems(sp, m: dict[str, Any], level: str, gate: str) -> list[dict]:
    ptr = f"/spaces/{sp.id}"
    st = (m.get("attributes") or {}).get("staircase")
    if sp.space_type_code != "STAIRCASE":
        return []
    if not st:
        return [problem(ptr, "STAIRCASE_GEOMETRY_REQUIRED", "Record the staircase geometry.", space=sp.label)]
    out = []
    if gate == "verify":
        # Each RISK condition needs a RISK note on the staircase (B1-SCOPE §2.4); notes are passed in by the caller.
        risks = m.get("_risk_notes", 0)
        if st["headroom_mm"] < 2000 and not risks:
            out.append(
                problem(ptr, "STAIRCASE_RISK_NOTE_REQUIRED", "Headroom is under 2 m: add a RISK note.", space=sp.label)
            )
        if st["largest_panel_mm"] < 900 and not risks:
            out.append(problem(ptr, "STAIRCASE_RISK_NOTE_REQUIRED", "The largest panel is under 900 mm: add a RISK note.",
                               space=sp.label))  # fmt: skip
        walls = {w["wall_index"] for w in m.get("walls") or []}
        if st.get("handrail_wall_index") is not None and st["handrail_wall_index"] not in walls:
            out.append(problem(ptr, "STAIRCASE_HANDRAIL_WALL_UNKNOWN", "The handrail wall is not one of the stair walls.",
                               space=sp.label))  # fmt: skip
    return out


EXTRA_SPACE_CHECKS.append(_l_shape_problems)
EXTRA_SPACE_CHECKS.append(_staircase_problems)
