"""Shared MTQ test builders: a property with spaces, visits, a draft set, photos and Lite/Full-compliant payloads."""

from __future__ import annotations

import base64
import hashlib
import io
from datetime import timedelta

from PIL import Image

from veda.kernel import clock

_PHOTO_N = [0]


def jpeg(size=(640, 480)) -> bytes:
    _PHOTO_N[0] += 1
    img = Image.new("RGB", size, ((_PHOTO_N[0] * 37) % 255, 90, 120))  # distinct bytes per call
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def photo(api, entity_type: str, entity_id: str, *, category: str = "SITE_PHOTO", complete: bool = True) -> dict:
    data = jpeg()
    r = api.post("/api/v1/attachments", {"entity_type": entity_type, "entity_id": entity_id, "mime_type": "image/jpeg",
                                         "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                         "category_code": category})  # fmt: skip
    assert r.status == 201, r
    assert api.put(f"/api/v1/attachments/{r.data['id']}/content",
                   {"data_base64": base64.b64encode(data).decode()}).status == 200  # fmt: skip
    if not complete:
        return r.data
    done = api.post(f"/api/v1/attachments/{r.data['id']}/complete")
    assert done.status == 200, done
    return done.data


def kitchen_payload(**over) -> dict:
    body = {
        "client_ref": "sm-kitchen",
        "shape_code": "RECTANGULAR",
        "length_mm": 3600,
        "width_mm": 2700,
        "ceiling_height_mm": 2900,
        "floor_to_lintel_mm": 2100,
        "flooring_code": "VITRIFIED",
        "existing_condition_code": "BARE_SHELL",
        "attributes": {"has_gas_line": True, "has_water_inlet": True, "has_drain": True, "counter_existing": False},
        "walls": [
            {"wall_index": 1, "length_mm": 2700, "usable_for_code": ["NONE"],
             "openings": [{"client_ref": "op-door", "opening_type_code": "DOOR", "width_mm": 900, "height_mm": 2100,
                           "offset_from_wall_start_mm": 300, "swing_code": "IN"}]},
            {"wall_index": 2, "length_mm": 3600, "usable_for_code": ["KITCHEN_RUN"],
             "obstructions": [{"kind": "PIPE", "offset_mm": 1200, "width_mm": 50}],
             "openings": [{"client_ref": "op-window", "opening_type_code": "WINDOW", "width_mm": 1200,
                           "height_mm": 1200, "sill_height_mm": 1050, "offset_from_wall_start_mm": 1500,
                           "swing_code": "SLIDING"}]},
            {"wall_index": 3, "length_mm": 2700},
            {"wall_index": 4, "length_mm": 3600},
        ],
    }  # fmt: skip
    body.update(over)
    return body


def bedroom_payload(**over) -> dict:
    """A FULL-compliant bedroom (BEDROOM_DEFAULT: wardrobe tag, floor to lintel, AC and fan readings)."""
    body = {
        "client_ref": "sm-bedroom",
        "length_mm": 3300,
        "width_mm": 3000,
        "ceiling_height_mm": 2900,
        "floor_to_lintel_mm": 2100,
        "flooring_code": "VITRIFIED",
        "existing_condition_code": "BARE_SHELL",
        "attributes": {"ac_type": "SPLIT", "ac_point_count": 1, "fan_point_count": 1},
        "walls": [
            {"wall_index": 1, "length_mm": 3000, "usable_for_code": ["NONE"],
             "openings": [{"client_ref": "bd-door", "opening_type_code": "DOOR", "width_mm": 900, "height_mm": 2100,
                           "offset_from_wall_start_mm": 100, "swing_code": "IN"}]},
            {"wall_index": 2, "length_mm": 3300, "usable_for_code": ["WARDROBE"],
             "obstructions": [{"kind": "SWITCHBOARD", "offset_mm": 200, "width_mm": 150, "height_from_floor_mm": 1200}]},
            {"wall_index": 3, "length_mm": 3000},
            {"wall_index": 4, "length_mm": 3300},
        ],
        "electrical_points": [
            {"client_ref": "ep-switchboard", "point_type_code": "SWITCHBOARD", "wall_index": 2, "from_offset_mm": 200,
             "from_height_mm": 1200},
            {"client_ref": "ep-light", "point_type_code": "LIGHT_POINT", "location_code": "CEILING",
             "from_offset_mm": 1650, "from_height_mm": 1500},
            {"client_ref": "ep-fan", "point_type_code": "FAN_POINT", "location_code": "CEILING",
             "from_offset_mm": 1650, "from_height_mm": 1500},
        ],
    }  # fmt: skip
    body.update(over)
    return body


FULL_CAPTURE = {"floor_number": 7, "lift_available": True, "main_door_width_mm": 1000, "main_door_height_mm": 2100,
                "narrowest_passage_mm": 950, "db_location": "Behind the main door", "occupancy": "VACANT"}  # fmt: skip


class Site:
    """A property with a kitchen and a bedroom (both in scope), three surveyors with visits, a sales owner and a
    founder. ``level`` is the planned survey level of the visits."""

    def __init__(self, api, factory, *, level: str = "FULL"):
        self.api, self.factory = api, factory
        self.sales = factory.user("SALES")
        self.lead_surveyor = factory.user("SURVEYOR")
        self.second = factory.user("SURVEYOR")
        self.third = factory.user("SURVEYOR")
        self.founder = factory.user(founder=True)
        factory.login(api, self.sales)
        self.lead = api.post(
            "/api/v1/leads", {"name": "Ravi K", "phone": "+91 90000 44444", "source_code": "PHONE"}
        ).data
        self.property = api.post("/api/v1/properties", {"lead_id": self.lead["id"], "property_type_code": "APARTMENT",
                                                        "built_up_area_sqft_centi": 220_00}).data  # fmt: skip
        pid = self.property["id"]
        self.kitchen = api.post(
            f"/api/v1/properties/{pid}/spaces", {"space_type_code": "KITCHEN", "label": "Kitchen"}
        ).data
        self.bedroom = api.post(
            f"/api/v1/properties/{pid}/spaces", {"space_type_code": "BEDROOM", "label": "Bedroom"}
        ).data
        self.visits: dict[str, dict] = {}
        for who in (self.lead_surveyor, self.second, self.third):
            v = api.post("/api/v1/measurement-visits", {"property_id": pid, "assigned_to": who.id, "survey_level_code": level,
                                                        "scheduled_start_on": clock.to_rfc3339(clock.now() + timedelta(hours=1))}).data  # fmt: skip
            self.visits[who.id] = v
        self.set: dict | None = None

    def as_(self, user):
        self.factory.login(self.api, user)
        return self.api

    def start(self, user) -> dict:
        v = self.visits[user.id]
        r = self.as_(user).post(f"/api/v1/measurement-visits/{v['id']}/status", {"to_status": "IN_PROGRESS"},
                                if_match=v["version"])  # fmt: skip
        assert r.status == 200, r
        self.visits[user.id] = r.data
        return r.data

    def open_set(self, **body) -> dict:
        self.start(self.lead_surveyor)
        r = self.as_(self.lead_surveyor).post(
            f"/api/v1/measurement-visits/{self.visits[self.lead_surveyor.id]['id']}/measurement-sets", body
        )
        assert r.status == 201, r
        self.set = r.data
        return r.data

    def put(self, space, body, user=None, mset=None):
        api = self.as_(user or self.lead_surveyor)
        mset = mset or self.set
        return api.put(f"/api/v1/measurement-sets/{mset['id']}/spaces/{space['id']}", body)

    def overview_photos(self, user=None) -> None:
        api = self.as_(user or self.lead_surveyor)
        for space in (self.kitchen, self.bedroom):
            photo(api, "property_space", space["id"])

    def wall_photos(self, measurement: dict, user=None) -> None:
        from veda.modules.mtq.capture import FURNITURE_TAGS

        api = self.as_(user or self.lead_surveyor)
        for w in measurement["walls"]:
            if FURNITURE_TAGS & set(w["usable_for_code"]):
                photo(api, "space_wall", w["id"], category="LASER_READING")

    def capture_full(self, *, mset=None, user=None) -> tuple[dict, dict]:
        """Both spaces captured to the FULL rules with photos, and the property-level capture filled in."""
        m = mset or self.set
        tree = self.as_(user or self.lead_surveyor).get(f"/api/v1/measurement-sets/{m['id']}").data
        versions = {sp["space_id"]: sp["version"] for sp in tree["spaces"]}

        def base(space) -> dict:
            v = versions.get(space["id"])
            return {"base_version": v} if v else {}

        k = self.put(self.kitchen, kitchen_payload(is_complete=True, **base(self.kitchen)), user, mset)
        b = self.put(self.bedroom, bedroom_payload(is_complete=True, **base(self.bedroom)), user, mset)
        assert k.status in (200, 201) and b.status in (200, 201), (k, b)
        self.overview_photos(user)
        self.wall_photos(k.data, user)
        self.wall_photos(b.data, user)
        api = self.as_(user or self.lead_surveyor)
        cur = api.get(f"/api/v1/measurement-sets/{m['id']}").data
        r = api.patch(
            f"/api/v1/measurement-sets/{m['id']}", {"property_capture": FULL_CAPTURE}, if_match=cur["version"]
        )
        assert r.status == 200, r
        return k.data, b.data

    def submit(self, user=None, mset=None):
        api = self.as_(user or self.lead_surveyor)
        m = mset or self.set
        cur = api.get(f"/api/v1/measurement-sets/{m['id']}").data
        return api.post(f"/api/v1/measurement-sets/{m['id']}/submit", if_match=cur["version"])
