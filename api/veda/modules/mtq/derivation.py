"""Derivation engine (MTQ B1-T07; blueprint §6.3). Computed on the server from raw millimetres, never trusted from a
client, and recomputed on every write.

| Derived | Rule |
|---|---|
| Floor area | RECTANGULAR: L × W · L_SHAPE: leg A + leg B (B1-T08) · POLYGON: shoelace over the vertices · FREEFORM: stated |
| Perimeter | Σ wall lengths, OPEN edges included (B1-SCOPE §2.9.2) |
| Gross wall area | Σ length × height for every non-OPEN wall; height = the wall's own height, else the ceiling height |
| Net wall area | Gross − Σ (width × height) of openings that deduct from wall area, never below zero |
| Usable segments | Per wall, the stretches between openings, from the wall's start corner (for B2 rules; read-only) |

Areas are integer hundredths of a square foot (the estimator's ``*_centi`` convention): 1 sq ft = 92,903.04 mm²,
rounded half up with integer arithmetic only. A STAIRCASE's floor area is run length × width (B1-SCOPE §2.4).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

SQFT_MM2_X100 = 9_290_304  # one square foot in hundredths of a square millimetre (92,903.04 mm² × 100)
NO_HEIGHT_DEFAULT = frozenset({"STAIRCASE", "TERRACE"})  # walls here need their own height (AR-19, 01 §11)


def mm2_to_sqft_centi(mm2: int) -> int:
    """mm² → hundredths of a square foot, rounded half up, exact."""
    if mm2 <= 0:
        return 0
    return (mm2 * 10_000 * 2 + SQFT_MM2_X100) // (2 * SQFT_MM2_X100)


def shoelace_mm2(vertices: Sequence[Sequence[int]]) -> int:
    twice = 0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        twice += x1 * y2 - x2 * y1
    return abs(twice) // 2


def polygon_perimeter_mm(vertices: Sequence[Sequence[int]]) -> int:
    from math import isqrt

    total = 0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        total += isqrt(dx * dx + dy * dy)
    return total


def floor_area_mm2(m: dict[str, Any], space_type_code: str) -> int | None:
    shape = m.get("shape_code")
    attrs = m.get("attributes") or {}
    if space_type_code == "STAIRCASE":
        st = attrs.get("staircase") or {}
        if st.get("run_length_mm") and st.get("width_mm"):
            return int(st["run_length_mm"]) * int(st["width_mm"])
        return None
    if shape == "RECTANGULAR" and m.get("length_mm") and m.get("width_mm"):
        return int(m["length_mm"]) * int(m["width_mm"])
    if shape == "L_SHAPE":
        legs = attrs.get("l_shape") or {}
        a, b = legs.get("leg_a") or {}, legs.get("leg_b") or {}
        if a.get("l_mm") and a.get("w_mm") and b.get("l_mm") and b.get("w_mm"):
            return int(a["l_mm"]) * int(a["w_mm"]) + int(b["l_mm"]) * int(b["w_mm"])
        return None
    if shape == "POLYGON" and m.get("polygon"):
        return shoelace_mm2(m["polygon"])
    return None


def wall_height(wall: dict[str, Any], ceiling_height_mm: int | None, space_type_code: str) -> int | None:
    if wall.get("height_mm"):
        return int(wall["height_mm"])
    if space_type_code in NO_HEIGHT_DEFAULT:
        return None
    return int(ceiling_height_mm) if ceiling_height_mm else None


def derive(m: dict[str, Any], walls: Iterable[dict[str, Any]], space_type_code: str) -> dict[str, int | None]:
    """The derived columns of one space measurement from its raw values (``m``) and walls (with ``openings``)."""
    walls = list(walls)
    if m.get("shape_code") == "FREEFORM" and space_type_code != "STAIRCASE":
        floor = m.get("stated_floor_area_sqft_centi")
    else:
        mm2 = floor_area_mm2(m, space_type_code)
        floor = mm2_to_sqft_centi(mm2) if mm2 is not None else None
    perimeter = sum(int(w["length_mm"]) for w in walls) if walls else None
    gross_mm2 = 0
    deduct_mm2 = 0
    known = bool(walls)
    for w in walls:
        if w.get("wall_type_code") == "OPEN":
            continue
        h = wall_height(w, m.get("ceiling_height_mm"), space_type_code)
        if h is None:
            known = False
            continue
        gross_mm2 += int(w["length_mm"]) * h
        for o in w.get("openings") or []:
            if o.get("deducts_from_wall_area", True):
                deduct_mm2 += int(o["width_mm"]) * min(int(o["height_mm"]), h)
    gross = mm2_to_sqft_centi(gross_mm2) if known else None
    net = mm2_to_sqft_centi(max(0, gross_mm2 - deduct_mm2)) if known else None
    return {
        "derived_floor_area_sqft_centi": floor,
        "derived_perimeter_mm": perimeter,
        "derived_wall_area_gross_sqft_centi": gross,
        "derived_wall_area_net_sqft_centi": net,
    }


def usable_segments(wall: dict[str, Any]) -> list[list[int]]:
    """Stretches of a wall clear of openings, as [start_mm, end_mm] from the wall's start corner. An opening without
    an offset makes its wall's segments unknown (empty list); B2 rules then treat the item as assumed."""
    length = int(wall["length_mm"])
    blocks = []
    for o in wall.get("openings") or []:
        if o.get("offset_from_wall_start_mm") is None:
            return []
        start = int(o["offset_from_wall_start_mm"])
        blocks.append((max(0, start), min(length, start + int(o["width_mm"]))))
    out, cursor = [], 0
    for a, b in sorted(blocks):
        if a > cursor:
            out.append([cursor, a])
        cursor = max(cursor, b)
    if cursor < length:
        out.append([cursor, length])
    return out
