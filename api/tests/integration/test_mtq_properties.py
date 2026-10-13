"""MTQ B1-T04: properties and the space tree (blueprint §4.1, §5; B1-SCOPE §2.2, §2.7, §2.9.4)."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.mtq import schemas, templates, vocab
from veda.modules.mtq.models import MeasurementVisit, PropertySpace

ON = pytest.mark.settings(mtq_site_enabled=True)


@pytest.fixture
def sales(api, factory):
    user = factory.user("SALES")
    factory.login(api, user)
    return user


def lead(api, name="Meera Iyer", phone="+91 90000 22222") -> str:
    r = api.post("/api/v1/leads", {"name": name, "phone": phone, "source_code": "PHONE"})
    assert r.status == 201, r
    return r.data["id"]


def create(api, lead_id, **body):
    payload = {"lead_id": lead_id, "property_type_code": "APARTMENT", **body}
    return api.post("/api/v1/properties", payload)


def types(prop):
    return [s["space_type_code"] for s in prop["spaces"]]


def test_schema_literals_match_the_vocabulary():
    assert set(schemas.SpaceType.__args__) == set(vocab.SPACE_TYPES)
    assert set(schemas.PropertyTemplateKey.__args__) == set(templates.load().property_templates)


def test_fixture_is_valid_and_covers_every_space_type():
    t = templates.load()
    assert t.template_version == "2026.10.1"
    covered = {st for tpl in t.space_templates.values() for st in tpl.space_types}
    assert covered == set(vocab.SPACE_TYPES)
    assert {"APARTMENT_2BHK", "APARTMENT_3BHK", "APARTMENT_4BHK", "APARTMENT_5BHK", "INDEPENDENT_HOUSE"} == set(
        t.property_templates
    )
    # Deferred property types have no template in B1 (duplex, villa, commercial).
    assert all(p.property_type_code in ("APARTMENT", "INDEPENDENT_HOUSE") for p in t.property_templates.values())


def test_routes_are_404_while_the_flag_is_off(api, sales):
    zero = "0" * 32
    for method, path in (("GET", "/api/v1/properties"), ("POST", "/api/v1/properties"),
                         ("GET", f"/api/v1/properties/{zero}"), ("GET", "/api/v1/mtq/templates"),
                         ("PATCH", f"/api/v1/spaces/{zero}"), ("DELETE", f"/api/v1/spaces/{zero}")):  # fmt: skip
        assert api.call(method, path, None if method == "GET" else {}).status == 404, path


@ON
@pytest.mark.parametrize(
    ("key", "beds", "toilets"),
    [("APARTMENT_2BHK", 2, 2), ("APARTMENT_3BHK", 3, 2), ("APARTMENT_4BHK", 4, 3), ("APARTMENT_5BHK", 5, 4)],
)
def test_apartment_templates_seed_a_tree_and_bhk_is_derived(api, sales, key, beds, toilets):
    r = create(api, lead(api), template_key=key)
    assert r.status == 201, r
    p = r.data
    assert p["derived_bedroom_count"] == beds and p["derived_toilet_count"] == toilets
    assert p["derived_level_count"] == 1 and p["display_label"] == f"{beds} BHK apartment"
    assert p["template_key"] == key and p["template_version"] == "2026.10.1"
    assert all(s["template_version"] == "2026.10.1" and s["space_template_key"] for s in p["spaces"])
    assert p["property_number"].startswith("VS-P-")
    master = next(s for s in p["spaces"] if s["space_type_code"] == "MASTER_BEDROOM")
    attached = next(s for s in p["spaces"] if s["label"] == "Master toilet")
    assert attached["parent_space_id"] == master["id"]
    assert "SERVANT_ROOM" not in types(p)  # optional spaces only when asked for


@ON
def test_optional_spaces_and_the_servant_room_is_not_a_bedroom(api, sales):
    p = create(api, lead(api), template_key="APARTMENT_4BHK",
               include_optional=["SERVANT_ROOM#1", "STUDY#1", "DRESSING#1", "TOILET#3"]).data  # fmt: skip
    assert {"SERVANT_ROOM", "STUDY", "DRESSING"} <= set(types(p))
    assert p["derived_bedroom_count"] == 4  # SERVANT_ROOM and STUDY never count (B1-SCOPE §2.9.4)
    bad = create(api, lead(api, phone="+91 90000 22223"), template_key="APARTMENT_4BHK", include_optional=["SAUNA#1"])
    assert bad.status == 422


@ON
def test_independent_house_levels_and_staircase(api, sales):
    r = create(api, lead(api), property_type_code="INDEPENDENT_HOUSE", template_key="INDEPENDENT_HOUSE",
               include_optional=["TERRACE#1"], plot_area_sqft_centi=2400_00)  # fmt: skip
    assert r.status == 201, r
    p = r.data
    assert p["project_kind_code"] == "RENOVATION"  # older stock (02 §7)
    assert "STAIRCASE" in types(p) and p["derived_level_count"] == 3  # 0, 1 and the terrace on 2
    assert p["display_label"] == f"{p['derived_bedroom_count']} BHK independent house, 3 levels"
    mismatch = create(api, lead(api, phone="+91 90000 22224"), template_key="INDEPENDENT_HOUSE")
    assert mismatch.status == 422  # an apartment cannot take the house template


@ON
def test_bhk_is_never_a_schema_constraint(api, sales):
    p = create(api, lead(api), template_key="APARTMENT_3BHK").data
    r = api.post(f"/api/v1/properties/{p['id']}/spaces", {"space_type_code": "BEDROOM", "label": "Bedroom 4"})
    assert r.status == 201 and r.data["instance_no"] == 3
    after = api.get(f"/api/v1/properties/{p['id']}").data
    assert after["derived_bedroom_count"] == 4 and after["display_label"] == "4 BHK apartment"
    assert after["configuration_label"] == "3 BHK"  # what the customer said stays, display only


@ON
def test_custom_spaces_tree_rules_and_stable_ids(api, sales):
    p = create(api, lead(api)).data
    pid = p["id"]
    assert api.post(f"/api/v1/properties/{pid}/spaces", {"space_type_code": "CUSTOM", "label": "Gym"}).status == 422
    gym = api.post(f"/api/v1/properties/{pid}/spaces",
                   {"space_type_code": "CUSTOM", "label": "Gym", "custom_type_label": "Home gym"}).data  # fmt: skip
    bed = api.post(f"/api/v1/properties/{pid}/spaces", {"space_type_code": "BEDROOM", "label": "Bedroom 2"}).data
    toilet = api.post(f"/api/v1/properties/{pid}/spaces",
                      {"space_type_code": "TOILET", "label": "Attached", "parent_space_id": bed["id"]}).data  # fmt: skip
    closet = api.post(f"/api/v1/properties/{pid}/spaces",
                      {"space_type_code": "WALK_IN_CLOSET", "label": "Closet", "parent_space_id": toilet["id"]}).data  # fmt: skip
    too_deep = api.post(f"/api/v1/properties/{pid}/spaces",
                        {"space_type_code": "STORE", "label": "Nook", "parent_space_id": closet["id"]})  # fmt: skip
    assert too_deep.status == 422
    cycle = api.patch(f"/api/v1/spaces/{bed['id']}", {"parent_space_id": toilet["id"]}, if_match=bed["version"])
    assert cycle.status == 422
    other = create(api, lead(api, phone="+91 90000 22225")).data
    foreign = api.post(f"/api/v1/properties/{other['id']}/spaces",
                       {"space_type_code": "TOILET", "label": "X", "parent_space_id": bed["id"]})  # fmt: skip
    assert foreign.status == 422
    stale = api.patch(f"/api/v1/spaces/{gym['id']}", {"label": "Gym room"}, if_match=gym["version"] + 5)
    assert stale.status == 409 and stale.code == "VERSION_CONFLICT"
    assert api.delete(f"/api/v1/spaces/{bed['id']}", {}, if_match=bed["version"]).status == 409  # children first
    for sp in (closet, toilet):
        assert (
            api.delete(f"/api/v1/spaces/{sp['id']}", {"reason": "Not in scope"}, if_match=sp["version"]).status == 204
        )
    bed_now = next(s for s in api.get(f"/api/v1/properties/{pid}/spaces").data if s["id"] == bed["id"])
    assert api.delete(f"/api/v1/spaces/{bed['id']}", {}, if_match=bed_now["version"]).status == 204
    with db.unit_of_work(write=False) as s:
        row = s.execute(
            sa.select(PropertySpace).where(PropertySpace.id == bed["id"]).execution_options(include_deleted=True)
        ).scalar_one()
        assert row.is_deleted and row.id == bed["id"]  # archived, id kept (B1-SCOPE §2.7)
    again = api.post(f"/api/v1/properties/{pid}/spaces", {"space_type_code": "BEDROOM", "label": "Bedroom 2"}).data
    assert again["instance_no"] == 2  # an archived instance number is never reused
    assert api.get(f"/api/v1/properties/{pid}").data["derived_bedroom_count"] == 1


@ON
def test_walk_order_needs_every_live_space_once(api, sales):
    p = create(api, lead(api), template_key="APARTMENT_2BHK").data
    ids = [s["id"] for s in p["spaces"]]
    r = api.put(f"/api/v1/properties/{p['id']}/spaces/order", {"space_ids": list(reversed(ids))})
    assert r.status == 200 and [s["id"] for s in r.data] == list(reversed(ids))
    assert api.put(f"/api/v1/properties/{p['id']}/spaces/order", {"space_ids": ids[:-1]}).status == 422
    assert api.put(f"/api/v1/properties/{p['id']}/spaces/order", {"space_ids": ids + ids[:1]}).status == 422


@ON
def test_from_template_only_on_an_empty_property(api, sales):
    p = create(api, lead(api)).data
    r = api.post(f"/api/v1/properties/{p['id']}/spaces/from-template", {"template_key": "APARTMENT_2BHK"})
    assert r.status == 201 and r.data["derived_bedroom_count"] == 2
    again = api.post(f"/api/v1/properties/{p['id']}/spaces/from-template", {"template_key": "APARTMENT_2BHK"})
    assert again.status == 409


@ON
def test_patch_property_and_floor_plan_must_be_a_floor_plan(api, sales):
    p = create(api, lead(api), city="Hyderabad").data
    r = api.patch(f"/api/v1/properties/{p['id']}", {"carpet_area_sqft_centi": 1450_00, "pincode": "500081"},
                  if_match=p["version"])  # fmt: skip
    assert r.status == 200 and r.data["carpet_area_sqft_centi"] == 1450_00
    assert api.patch(f"/api/v1/properties/{p['id']}", {"pincode": "12"}, if_match=r.data["version"]).status == 422
    assert api.patch(f"/api/v1/properties/{p['id']}", {"floor_plan_attachment_id": "0" * 31 + "1"},
                     if_match=r.data["version"]).status == 422  # fmt: skip
    listed = api.get("/api/v1/properties?city=hyderabad").data
    assert [x["id"] for x in listed] == [p["id"]]


@ON
def test_scope_owner_other_sales_and_assigned_surveyor(api, factory):
    owner = factory.user("SALES")
    factory.login(api, owner)
    p = create(api, lead(api), template_key="APARTMENT_2BHK").data
    other = factory.user("SALES")
    factory.login(api, other)
    assert api.get(f"/api/v1/properties/{p['id']}").status == 404
    assert create(api, p["lead_id"]).status == 404  # not their lead
    surveyor = factory.user("SURVEYOR")
    factory.login(api, surveyor)
    assert api.get(f"/api/v1/properties/{p['id']}").status == 404  # no visit yet
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.add(MeasurementVisit(visit_number="VS-M-S1", property_id=p["id"], lead_id=p["lead_id"],
                               survey_level_code="FULL", status="SCHEDULED", assigned_to=surveyor.id,
                               status_changed_on=db.tx_time(s), scheduled_start_on=db.tx_time(s)))  # fmt: skip
    assert api.get(f"/api/v1/properties/{p['id']}").status == 200  # the assigned surveyor reads the property
    r = api.post(f"/api/v1/properties/{p['id']}/spaces", {"space_type_code": "STORE", "label": "Store"})
    assert r.status == 403  # SURVEYOR holds no property.update
    founder = factory.user(founder=True)
    factory.login(api, founder)
    assert api.get(f"/api/v1/properties/{p['id']}").status == 200


@ON
def test_erased_lead_takes_no_new_property(api, sales):
    from veda.modules.crm.leads import service as lead_service
    from veda.modules.crm.leads.models import Lead

    lead_id = lead(api)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_service.anonymize(s, s.get(Lead, lead_id), legal_basis="TEST", request_ref=None)
    assert create(api, lead_id).status == 409


@ON
def test_space_photos_attach_through_att(api, sales):
    import base64
    import hashlib
    import io

    from PIL import Image

    p = create(api, lead(api), template_key="APARTMENT_2BHK").data
    kitchen = next(s for s in p["spaces"] if s["space_type_code"] == "KITCHEN")
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (10, 20, 30)).save(buf, "JPEG")
    data = buf.getvalue()
    r = api.post("/api/v1/attachments", {"entity_type": "property_space", "entity_id": kitchen["id"],
                                         "mime_type": "image/jpeg", "byte_size": len(data),
                                         "sha256": hashlib.sha256(data).hexdigest()})  # fmt: skip
    assert r.status == 201 and r.data["lead_id"] == p["lead_id"]
    api.put(f"/api/v1/attachments/{r.data['id']}/content", {"data_base64": base64.b64encode(data).decode()})
    assert api.post(f"/api/v1/attachments/{r.data['id']}/complete").data["available"] is True


@ON
def test_templates_endpoint(api, sales):
    r = api.get("/api/v1/mtq/templates")
    assert r.status == 200 and r.data["template_version"] == "2026.10.1"
    assert "KITCHEN_DEFAULT" in r.data["space_templates"]
