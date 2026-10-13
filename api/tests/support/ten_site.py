"""MTQ B1-T12 ten-site harness: synthetic sites driven through the real API, then judged by ten_site.evaluate.

Everything here is SYNTHETIC (tests/fixtures/mtq_ten_site/synthetic-2026.10.json). Reference dimensions come from a
fixed table plus a deterministic variation per site and space; the "app" reading is the reference plus a deterministic
error of at most 5 mm, except the deviations a site plants on purpose. No real site, customer or measurement is used.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from tests.support.mtq import FULL_CAPTURE, photo
from veda.kernel import clock
from veda.modules.mtq import templates
from veda.modules.mtq.capture import FURNITURE_TAGS
from veda.modules.mtq.ten_site import Reference, SiteRef, SpaceRef

DATASET = Path(__file__).resolve().parents[1] / "fixtures" / "mtq_ten_site" / "synthetic-2026.10.json"

# Nominal (length, width) in mm by space type: plausible Indian residential sizes, not taken from any real site.
DIMS = {
    "FOYER": (2000, 1500), "PASSAGE": (3000, 1200), "LIVING": (5200, 4200), "LIVING_DINING": (6500, 4200),
    "DINING": (3600, 3200), "KITCHEN": (3600, 2700), "UTILITY": (1800, 1500), "LAUNDRY": (1800, 1500),
    "POOJA": (1500, 1200), "TOILET": (2400, 1500), "POWDER_ROOM": (1800, 1200), "MASTER_BEDROOM": (4200, 3600),
    "BEDROOM": (3600, 3300), "PARENTS_BEDROOM": (3600, 3300), "CHILDREN_BEDROOM": (3300, 3000),
    "GUEST_BEDROOM": (3600, 3000), "SERVANT_ROOM": (2700, 2400), "DRESSING": (2400, 1800), "WALK_IN_CLOSET": (2100, 1800),
    "STUDY": (3000, 2700), "HOME_OFFICE": (3000, 2700), "FAMILY_LOUNGE": (4000, 3600), "MEDIA_ROOM": (4500, 3600),
    "STORE": (1800, 1500), "BALCONY": (3000, 1500), "SIT_OUT": (3000, 2000), "TERRACE": (6000, 5000),
    "PORCH": (3000, 2400), "PARKING": (5500, 3000), "GARDEN": (6000, 4000), "STAIRCASE": (4000, 1100),
}  # fmt: skip
ATTRIBUTE_VALUES = {"ac_type": "SPLIT", "ac_point_count": 1, "fan_point_count": 1, "has_gas_line": True,
                    "has_water_inlet": True, "has_drain": True, "counter_existing": False, "railing_height_mm": 1000,
                    "exposure_code": "OPEN"}  # fmt: skip
CEILING = {"APARTMENT": 2900, "INDEPENDENT_HOUSE": 3050}
PARAPET_MM = 1000


def load() -> dict[str, Any]:
    return json.loads(DATASET.read_text())


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def err(site_id: str, label: str, quantity: str) -> int:
    """The synthetic app error for one reading: -5..+5 mm, fixed per site, space and quantity."""
    return _h(site_id, label, quantity) % 11 - 5


def reference_space(site_id: str, sp: dict[str, Any], property_type: str) -> SpaceRef:
    t, label = sp["space_type_code"], sp["label"]
    base_l, base_w = DIMS.get(t, (3000, 2500))
    length = base_l + (_h(site_id, label, "L") % 21) * 10
    width = base_w + (_h(site_id, label, "W") % 11) * 10
    walls = [width, length, width, length]
    if t == "STAIRCASE":  # compared by its walls; its area comes from the flight geometry, not length x width
        return SpaceRef(label=label, walls=walls)
    ceiling = None if sp["zone_code"] == "OUTDOOR" else CEILING[property_type]
    return SpaceRef(label=label, length_mm=length, width_mm=width, ceiling_height_mm=ceiling, walls=walls)


def payload(site_id: str, sp: dict[str, Any], ref: SpaceRef, level: str, deviations: list[dict], n: int,
            property_type: str) -> dict[str, Any]:  # fmt: skip
    """A capture that satisfies the space's template at ``level``, built from the reference plus the synthetic error."""
    t, label, zone = sp["space_type_code"], sp["label"], sp["zone_code"]
    _, tpl = templates.space_template_for(t)
    required = list(tpl.full_required) if level == "FULL" else []
    stair, outdoor = t == "STAIRCASE", zone == "OUTDOOR"
    walls: list[dict[str, Any]] = []
    for i, length in enumerate(ref.walls, start=1):
        planted = sum(d["delta_mm"] for d in deviations if d["space"] == label and d["wall"] == i)
        walls.append({"wall_index": i, "length_mm": length + err(site_id, label, f"W{i}") + planted})
    if not outdoor:
        walls[0]["openings"] = [{"client_ref": f"op{n}-door", "opening_type_code": "DOOR", "width_mm": 900,
                                 "height_mm": 2100, "offset_from_wall_start_mm": 100, "swing_code": "IN"}]  # fmt: skip
    walls[0]["usable_for_code"] = ["NONE"]
    tags = [c[4:] for c in required if c.startswith("TAG:")]
    for tag, w in zip(tags, walls[1:], strict=False):
        w["usable_for_code"] = [tag]
    furniture = [w for w in walls if FURNITURE_TAGS & set(w.get("usable_for_code", []))]
    points: list[dict[str, Any]] = []
    kinds = [c[9:] for c in required if c.startswith("OBS_KIND:")]
    for i, w in enumerate(furniture):
        obs = (
            [{"kind": k, "offset_mm": 300, "width_mm": 100, "height_from_floor_mm": 1200} for k in kinds]
            if i == 0
            else []
        )
        w["obstructions"] = obs or [{"kind": "NONE"}]
        for o in obs:
            if o["kind"] in ("SWITCHBOARD", "DB_BOX"):
                points.append({"client_ref": f"ep{n}-{o['kind'].lower()}", "point_type_code": o["kind"],
                               "wall_index": w["wall_index"], "from_offset_mm": 300, "from_height_mm": 1200})  # fmt: skip
    if "WALL_HEIGHTS" in required:
        for w in walls:
            w["height_mm"] = PARAPET_MM if t == "TERRACE" else CEILING[property_type]
    body: dict[str, Any] = {
        "client_ref": f"sm-{n}",
        "shape_code": "RECTANGULAR",
        "length_mm": ref.walls[1] + err(site_id, label, "L"),
        "width_mm": ref.walls[0] + err(site_id, label, "W"),
        "is_complete": True,
        "walls": walls,
        "electrical_points": points,
    }
    if ref.ceiling_height_mm:
        body["ceiling_height_mm"] = ref.ceiling_height_mm + err(site_id, label, "C")
    if not outdoor and not stair:
        body["flooring_code"] = "VITRIFIED"
        body["existing_condition_code"] = "BARE_SHELL"
        if "FL" in required:
            body["floor_to_lintel_mm"] = 2100
    attrs = {c[5:]: ATTRIBUTE_VALUES[c[5:]] for c in required if c.startswith("ATTR:")}
    if stair:
        attrs["staircase"] = {"from_level": 0, "to_level": 1, "turn_type_code": "STRAIGHT", "flight_count": 1,
                              "run_length_mm": body["length_mm"], "width_mm": body["width_mm"], "riser_count": 18,
                              "riser_height_mm": 170, "tread_depth_mm": 250, "headroom_mm": 2200,
                              "largest_panel_mm": 1200}  # fmt: skip
    if attrs:
        body["attributes"] = attrs
    return body


class TenSite:
    """Runs one dataset through the API: a lead and property per site, visits, an offline-style capture through the
    sync endpoint, photos, submission and four-eyes verification; then collects what the evaluator needs."""

    def __init__(self, api, factory):
        self.api, self.factory = api, factory
        self.sales = factory.user("SALES")
        self.lead_surveyor = factory.user("SURVEYOR")
        self.second = factory.user("SURVEYOR")
        self.founder = factory.user(founder=True)

    def as_(self, user):
        self.factory.login(self.api, user)
        return self.api

    def _ok(self, r, *codes):
        assert r.status in (codes or (200, 201)), r
        return r.data

    def _visit(self, prop_id: str, user, level: str) -> dict:
        api = self.as_(self.sales)
        v = self._ok(api.post("/api/v1/measurement-visits", {
            "property_id": prop_id, "assigned_to": user.id, "survey_level_code": level,
            "scheduled_start_on": clock.to_rfc3339(clock.now() + timedelta(hours=1))}))  # fmt: skip
        return self._ok(self.as_(user).post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "IN_PROGRESS"},
                                            if_match=v["version"]))  # fmt: skip

    def _sync(self, user, set_id: str, batch: str, ops: list[dict]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ops), 50):
            r = self.as_(user).post(f"/api/v1/measurement-sets/{set_id}/sync",
                                    {"batch_id": f"{batch}-{i // 50}", "operations": ops[i : i + 50]})  # fmt: skip
            out += self._ok(r)["results"]
        return out

    def run_site(self, spec: dict[str, Any]) -> tuple[SiteRef, dict[str, Any], dict[str, bool]]:
        site_id, level = spec["site_id"], spec["survey_level_code"]
        ptype = "APARTMENT" if spec["template_key"].startswith("APARTMENT") else "INDEPENDENT_HOUSE"
        api = self.as_(self.sales)
        lead = self._ok(api.post("/api/v1/leads", {"name": f"Synthetic site {site_id}",
                                                    "phone": f"+91 90000 {50000 + int(site_id[1:]):05d}",
                                                    "source_code": "PHONE"}))  # fmt: skip
        prop = self._ok(api.post("/api/v1/properties", {"lead_id": lead["id"], "property_type_code": ptype,
                                                        "template_key": spec["template_key"]}))  # fmt: skip
        for extra in spec.get("extra_spaces", []):
            self._ok(api.post(f"/api/v1/properties/{prop['id']}/spaces", extra))
        visit = self._visit(prop["id"], self.lead_surveyor, level)
        mset = self._ok(self.as_(self.lead_surveyor).post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets",
                                                          {"unit_system_code": "MM"}))  # fmt: skip
        prop = self._ok(self.as_(self.lead_surveyor).get(f"/api/v1/properties/{prop['id']}"))
        spaces = [sp for sp in prop["spaces"] if sp["is_in_scope"]]
        refs = {sp["id"]: reference_space(site_id, sp, ptype) for sp in spaces}
        deviations = spec.get("deviations", [])
        bodies = {
            sp["id"]: payload(site_id, sp, refs[sp["id"]], level, deviations, n, ptype) for n, sp in enumerate(spaces)
        }
        events = {"second_surveyor_conflict": False, "offline_retry": False}
        conflict_label = spec.get("conflict_space")
        held = next((sp for sp in spaces if sp["label"] == conflict_label), None)
        ops = [{"op_id": f"{site_id}-op-{n}", "type": "space", "space_id": sp["id"], "data": bodies[sp["id"]]}
               for n, sp in enumerate(spaces) if sp is not held]  # fmt: skip
        first = self._sync(self.lead_surveyor, mset["id"], f"{site_id}-capture", ops)
        assert all(r["status"] == "APPLIED" for r in first), [r for r in first if r["status"] != "APPLIED"]
        if spec.get("offline_retry"):
            # The device never saw the answers and resends the whole queue: every write is recognised, none repeats.
            again = self._sync(self.lead_surveyor, mset["id"], f"{site_id}-capture-retry", ops)
            events["offline_retry"] = all(r["status"] == "DUPLICATE" for r in again)
        if held is not None:
            events["second_surveyor_conflict"] = self._conflict(mset["id"], prop["id"], held, bodies[held["id"]], level)
        self._photos(mset["id"], spaces, level)
        capture = FULL_CAPTURE if level == "FULL" else {"floor_number": 0 if ptype == "INDEPENDENT_HOUSE" else 7,
                                                        "lift_available": ptype == "APARTMENT"}  # fmt: skip
        if ptype == "INDEPENDENT_HOUSE" and level == "FULL":
            capture = {**capture, "floor_number": 0, "lift_available": False}
        lead_api = self.as_(self.lead_surveyor)
        cur = self._ok(lead_api.get(f"/api/v1/measurement-sets/{mset['id']}"))
        self._ok(lead_api.patch(f"/api/v1/measurement-sets/{mset['id']}", {"property_capture": capture},
                                if_match=cur["version"]))  # fmt: skip
        cur = self._ok(lead_api.get(f"/api/v1/measurement-sets/{mset['id']}"))
        self._ok(lead_api.post(f"/api/v1/measurement-sets/{mset['id']}/submit", if_match=cur["version"]))
        founder = self.as_(self.founder)
        ready = self._ok(founder.get(f"/api/v1/measurement-sets/{mset['id']}/checks"))
        assert ready["ready_to_verify"], (site_id, ready["verify_problems"])
        acks = [{"code": p["code"], "note": "Synthetic site: stated area not given"} for p in ready["verify_problems"]
                if p["acknowledgeable"]]  # fmt: skip
        cur = self._ok(founder.get(f"/api/v1/measurement-sets/{mset['id']}"))
        self._ok(founder.post(f"/api/v1/measurement-sets/{mset['id']}/verify", {"acknowledgements": acks},
                              if_match=cur["version"]))  # fmt: skip
        measured = {
            "set": self._ok(founder.get(f"/api/v1/measurement-sets/{mset['id']}")),
            "property": self._ok(founder.get(f"/api/v1/properties/{prop['id']}")),
        }
        ref = SiteRef(
            site_id=site_id,
            property_type_code=ptype,
            bedrooms=measured["property"]["derived_bedroom_count"],
            survey_level_code=level,
            reference_method="SYNTHETIC_GENERATED",
            spaces=[refs[sp["id"]] for sp in spaces],
            causes={f"{d['space']}/W{d['wall']}": d["cause"] for d in deviations},
            root_cause=spec.get("root_cause"),
        )
        return ref, measured, events

    def _conflict(self, set_id: str, prop_id: str, space: dict, body: dict, level: str) -> bool:
        """A second surveyor takes a first reading of a space (and holds its claim); the lead surveyor, who owns the
        revision, re-measures it online; the second surveyor's next reading, queued offline on the old version, must
        come back CONFLICT with the server's reading (never last-write-wins). The second surveyor keeps the server's
        reading, so the lead's re-measurement stands."""
        op = lambda op_id, data: {"op_id": op_id, "type": "space", "space_id": space["id"], "data": data}  # noqa: E731
        self._visit(prop_id, self.second, level)
        first = self._sync(
            self.second, set_id, "conflict-first", [op("c-1", {**body, "length_mm": body["length_mm"] + 20})]
        )
        assert first[0]["status"] == "APPLIED", first
        v1 = first[0]["version"]
        online = self._sync(self.lead_surveyor, set_id, "conflict-online", [op("c-2", {**body, "base_version": v1})])
        assert online[0]["status"] == "APPLIED", online
        queued = self._sync(self.second, set_id, "conflict-offline", [op("c-3", {**body, "base_version": v1,
                                                                               "length_mm": body["length_mm"] + 8})])  # fmt: skip
        return queued[0]["status"] == "CONFLICT" and queued[0]["conflicting_fields"] == ["length_mm"]

    def _photos(self, set_id: str, spaces: list[dict], level: str) -> None:
        api = self.as_(self.lead_surveyor)
        for sp in spaces:
            photo(api, "property_space", sp["id"])
        if level != "FULL":
            return
        tree = self._ok(api.get(f"/api/v1/measurement-sets/{set_id}"))
        for sm in tree["spaces"]:
            for w in sm["walls"]:
                if FURNITURE_TAGS & set(w["usable_for_code"]):
                    photo(api, "space_wall", w["id"], category="LASER_READING")

    def run(self, dataset: dict[str, Any]) -> tuple[Reference, dict[str, dict], dict[str, dict]]:
        refs, measured, events = [], {}, {}
        for spec in dataset["sites"]:
            ref, m, ev = self.run_site(spec)
            refs.append(ref)
            measured[ref.site_id] = m
            events[ref.site_id] = ev
        reference = Reference(dataset_id=dataset["dataset_id"], dataset_kind=dataset["dataset_kind"], sites=refs)
        return reference, measured, events
