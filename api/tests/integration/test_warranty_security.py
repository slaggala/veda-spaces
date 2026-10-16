"""Warranty and service security (WSV-020): RBAC (FOUNDER only by default; not ACCOUNTANT, not SALES_MANAGER), OWN
scope, customer isolation and ID guessing, photos and evidence never public, portal field minimisation, the flag.
SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.portal import PUBLIC, keys
from tests.support.project import install, no_four_eyes
from tests.support.warranty import FLAGS, SERVICE, WARRANTY, Service, india_today, policy

pytestmark = pytest.mark.settings(**FLAGS)
INTERNAL = {"internal_reason", "internal_note", "period_basis", "assessed_by", "owner", "owner_user_id", "resolved_by",
            "basis_path", "basis_text_sha256", "terms_sha256", "attachment_id", "account_id", "lead_id", "created_by",
            "timeline", "visibility", "cancel_reason", "decided_by", "uploaded_by", "filename"}  # fmt: skip


@pytest.fixture
def team(api, factory):
    install(no_four_eyes())
    t = Service(api, factory)
    yield t
    install(None)
    policy(None)


def test_default_grants_are_the_founders_only():
    from veda.platform.rbac.registry import MATRIX

    codes = [c for c in MATRIX if c.startswith("warranty.")]
    assert len(codes) == 9 and all(MATRIX[c] == {"FOUNDER": "A"} for c in codes)


def test_roles_without_a_grant_see_nothing_and_cannot_act(team, factory):
    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    accountant = factory.user("ACCOUNTANT", mfa=True)
    for user in (accountant, t.manager, t.ops):
        api = t.as_(user)
        assert api.get(f"{SERVICE}/{rid}").status == 403
        assert api.get(SERVICE).status == 403
        assert api.get(f"{WARRANTY}/projects/{p['id']}").status == 403
    assert ok(t.as_(t.founder).get(f"{SERVICE}/{rid}"))["id"] == rid  # FOUNDER oversight
    # a technician cannot assess, and resolves only what they own
    version = t.req(rid)["version"]
    r = t.as_(t.tech).post(f"{SERVICE}/{rid}/triage", {}, if_match=version)
    assert r.status == 403


def test_own_scope_reaches_only_the_owners_requests_or_the_project_team(team, factory):
    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    own = factory.user("ESTIMATOR")
    factory.grant(own, "warranty.service.view", scope="OWN")
    assert t.as_(own).get(f"{SERVICE}/{rid}").status == 404  # not the owner, not on the team: not disclosed
    assert ok(t.as_(own).get(SERVICE)) == []
    factory.grant(own, "warranty.service.resolve", scope="OWN")
    t.do(rid, "triage", {"priority": "NORMAL"})
    t.do(rid, "assign", {"owner_user_id": own.id})
    assert ok(t.as_(own).get(f"{SERVICE}/{rid}"))["id"] == rid


def test_customer_isolation_and_id_guessing(team):
    t = team
    prop_a, p_a, me_a = t.handed_over("2BHK", "iso-a@example.test")
    prop_b, p_b, me_b = t.handed_over("3BHK", "iso-b@example.test")
    rid_a = t.submit(me_a, prop_a, p_a).data["request"]["id"]
    photo = t.photo(me_a, prop_a, rid_a).data["photo_id"]
    # B cannot see, address or act on A's request, through its own property or A's
    assert ok(me_b.property(prop_b["id"]))["warranty"]["projects"][0]["requests"] == []
    assert me_b.property(prop_a["id"]).status == 404
    for prop in (prop_a, prop_b):
        for action, body in (("confirm", {}), ("withdraw", {}), ("information", {"text": "Someone else's request"}),
                             ("reject", {"reason": "Trying to reach someone else's request"})):  # fmt: skip
            r = t.customer(me_b, prop, rid_a, action, body)
            assert r.status == 404, (prop["id"], action)
        url = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid_a}/photos/{photo}/content"
        assert me_b.call("GET", url).status == 404
    # B cannot file a request against A's project through B's own property
    r = t.submit(me_b, prop_b, p_a, key="cross-key-001")
    assert r.status == 404
    # a well-formed id of something else answers like an unknown one
    assert t.customer(me_a, prop_a, p_a["id"], "confirm").status == 404
    # no session, or a staff token, reaches nothing
    anon = me_a.api.call("POST", f"{PUBLIC}/properties/{prop_a['id']}/service-requests/{rid_a}/withdraw", {},
                         anonymous=True)  # fmt: skip
    assert anon.status == 401
    staff = me_a.api.call("GET", f"{PUBLIC}/properties/{prop_a['id']}", token=t.token(t.founder))
    assert staff.status == 401


def test_the_customer_view_carries_no_internal_field(team):
    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.resolved(rid)
    view = ok(me.property(prop["id"]))
    w = view["warranty"]
    found = {k.rsplit(".", 1)[-1] for k in keys(w)}
    assert not found & INTERNAL, found & INTERNAL
    text = str(w)
    d = t.req(rid, t.checker)
    for secret in (d["assessments"][0]["internal_reason"], d["assessments"][0]["period_basis"], t.tech.id, t.care.id):
        assert secret not in text
    assert {"WARRANTY_SUMMARY"} <= {x["kind"] for x in view["documents"]}
    assert w["projects"][0]["warranty"]["status_label"] == "Not recorded in your portal"  # never "covered"


def test_staff_evidence_is_shown_only_when_marked_and_never_an_internal_file(team):
    from tests.support.mtq import photo

    t = team
    prop, p, me = t.handed_over()
    rid = t.submit(me, prop, p).data["request"]["id"]
    t.do(rid, "triage", {"priority": "NORMAL"})
    hidden = photo(t.as_(t.founder), "property", p["property"]["id"])
    shown = photo(t.as_(t.founder), "property", p["property"]["id"])
    internal = photo(t.as_(t.founder), "property", p["property"]["id"], category="FLOOR_PLAN")
    t.factory.grant(t.care, "warranty.service.resolve")
    t.do(rid, "evidence", {"attachment_id": hidden["id"]})
    r = t.do(rid, "evidence", {"attachment_id": shown["id"], "customer_visible": True}, status=422)
    assert r.json["errors"][0]["code"] == "NOT_SHAREABLE"  # a customer caption is required
    t.do(rid, "evidence", {"attachment_id": shown["id"], "customer_visible": True, "caption": "After the fix"})
    r = t.do(
        rid, "evidence", {"attachment_id": internal["id"], "customer_visible": True, "caption": "Plan"}, status=422
    )
    assert r.json["errors"][0]["code"] == "NOT_SHAREABLE"
    v = ok(me.property(prop["id"]))["warranty"]["projects"][0]["requests"][0]
    assert [e["caption"] for e in v["evidence"]] == ["After the fix"]
    url = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/evidence/{v['evidence'][0]['id']}/content"
    assert me.call("GET", url).status == 200
    hidden_ev = next(e for e in t.req(rid)["evidence"] if e["attachment_id"] == hidden["id"])
    assert me.call("GET", url.replace(v["evidence"][0]["id"], hidden_ev["id"])).status == 404


@pytest.mark.settings(**{**FLAGS, "warranty_service_enabled": False})
def test_everything_answers_404_while_the_flag_is_off(team):
    t = team
    prop, p, me = t.handed_over()
    assert t.as_(t.founder).get(SERVICE).status == 404
    assert t.as_(t.founder).get(f"{WARRANTY}/projects/{p['id']}").status == 404
    assert t.submit(me, prop, p).status == 404
    assert ok(me.property(prop["id"])).get("warranty") is None


def test_staff_record_a_request_for_the_customer(team):
    t = team
    prop, p, _me = t.handed_over()
    body = {"property_id": prop["id"], "project_id": p["id"], "category": "HARDWARE",
            "description": "Customer phoned: the wardrobe handle came loose."}  # fmt: skip
    r = t.as_(t.care).post(SERVICE, body)
    assert r.status == 201 and r.data["channel"] == "STAFF" and r.data["reported_on"] == india_today()
