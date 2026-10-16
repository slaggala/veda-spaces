"""Customer-visible project documents (CPP-D04, decision log 46): visibility is an explicit staff publication, never
"it belongs to the project"; internal, unavailable and other customers' files are refused; every customer request is
authorised on the server through the account's property; a guessed or withdrawn id answers 404 like an unknown one.
SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.mtq import photo
from tests.support.portal import PUBLIC, Portal
from tests.support.project import BASE, install, no_four_eyes

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
             customer_portal_enabled=True, project_lifecycle_enabled=True)  # fmt: skip
pytestmark = pytest.mark.settings(**FLAGS, project_delivery_portal_enabled=True)


@pytest.fixture
def team(api, factory):
    t = Portal(api, factory)
    install(no_four_eyes())
    yield t
    install(None)


def _project(t: Portal, key: str, email: str):
    prop, _, q = t.accepted(key)
    p = t.book(q, prop)
    t.staff(p)
    return prop, t.get(p), t.invite(prop["lead_id"], email)


def _publish(t: Portal, p: dict, att: dict, user=None, **over):
    body = {"attachment_id": att["id"], "document_class": "PROGRESS_PHOTO", "title": "Kitchen carcass fitted", **over}
    return t.as_(user or t.founder).post(f"{BASE}/{p['id']}/customer-documents", body)


def _content(me, prop: dict, doc_id: str, variant: str = "mobile"):
    return me.call("GET", f"{PUBLIC}/properties/{prop['id']}/documents/{doc_id}/content?variant={variant}")


def test_only_an_explicit_publication_is_visible_and_it_is_served_through_the_property(team):
    t = team
    prop, p, me = _project(t, "2BHK", "docs-a@example.test")
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    assert ok(me.property(prop["id"]))["delivery"]["projects"][0]["documents"] == []  # belonging is not visibility
    assert not [d for d in ok(me.property(prop["id"]))["documents"] if d["kind"] == "PROJECT_DOCUMENT"]
    d = ok(_publish(t, p, att), 201)["customer_documents"]
    assert d["documents"][0]["status"] == "PUBLISHED" and d["documents"][0]["title"] == "Kitchen carcass fitted"
    assert att["id"] not in {o["id"] for o in d["options"]}  # already shown: not offered again
    view = ok(me.property(prop["id"]))
    (doc,) = [x for x in view["documents"] if x["kind"] == "PROJECT_DOCUMENT"]
    assert set(doc) == {"id", "kind", "document_class", "label", "title", "published_on", "width", "height",
                        "project_id"}  # no file name, uploader, attachment id or lead  # fmt: skip
    assert doc["id"] != att["id"] and att["id"] not in str(view)
    r = _content(me, prop, doc["id"])
    assert r.status == 200 and r.headers["Content-Type"] == "image/webp" and r.raw.data[:4] == b"RIFF"
    assert "no-store" in r.headers["Cache-Control"] and r.headers["X-Content-Type-Options"] == "nosniff"
    assert _content(me, prop, doc["id"], "full").status == 422  # the original-size variant is never served
    # a repeat is idempotent; a different class for the same file must withdraw first
    assert _publish(t, p, att).status == 201
    assert _publish(t, p, att, title="Another title").code == "ALREADY_PUBLISHED"


def test_internal_unavailable_and_other_customers_files_are_refused_at_publication(team):
    t = team
    prop, p, _me = _project(t, "2BHK", "docs-b@example.test")
    prop2, p2, _me2 = _project(t, "3BHK", "docs-c@example.test")
    other = photo(t.as_(t.founder), "property", p2["property"]["id"])
    r = _publish(t, p, other)
    assert r.status == 422 and r.json["errors"][0]["code"] == "UNKNOWN_ATTACHMENT"
    pending = photo(t.as_(t.founder), "property", p["property"]["id"], complete=False)
    assert _publish(t, p, pending).code == "DOCUMENT_NOT_AVAILABLE"
    internal = photo(t.as_(t.founder), "property", p["property"]["id"], category="FLOOR_PLAN")  # always INTERNAL
    assert internal["visibility_code"] == "INTERNAL"
    assert _publish(t, p, internal).code == "DOCUMENT_INTERNAL"
    assert (
        _publish(t, p, photo(t.as_(t.founder), "property", p["property"]["id"]), document_class="QC_NOTE").status == 422
    )


def test_rbac_only_a_publisher_on_the_project_publishes(team):
    t = team
    _prop, p, _me = _project(t, "2BHK", "docs-d@example.test")
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    assert _publish(t, p, att, user=t.manager).status == 403  # SALES_MANAGER does not hold project.publish_document
    assert _publish(t, p, att, user=t.ops).status == 403  # nor the operations persona unless granted
    assert t.get(p, t.manager)["customer_documents"]["can_publish"] is False


def test_customer_isolation_guessed_ids_and_withdrawal(team):
    t = team
    prop_a, p_a, me_a = _project(t, "2BHK", "docs-e@example.test")
    prop_b, p_b, me_b = _project(t, "3BHK", "docs-f@example.test")
    doc_a = ok(_publish(t, p_a, photo(t.as_(t.founder), "property", p_a["property"]["id"])), 201)
    doc_a = doc_a["customer_documents"]["documents"][0]
    assert _content(me_a, prop_a, doc_a["id"]).status == 200
    # B, through B's own property, through A's property, or with no session: all 404/401, never the bytes
    assert _content(me_b, prop_b, doc_a["id"]).status == 404
    assert _content(me_b, prop_a, doc_a["id"]).status == 404
    assert me_a.api.call("GET", f"{PUBLIC}/properties/{prop_a['id']}/documents/{doc_a['id']}/content",
                         anonymous=True).status == 401  # fmt: skip
    assert _content(me_a, prop_a, p_a["id"]).status == 404  # a well-formed id of something else
    assert not [d for d in ok(me_b.property(prop_b["id"]))["documents"] if d["kind"] == "PROJECT_DOCUMENT"]
    r = t.as_(t.founder).post(f"{BASE}/{p_a['id']}/customer-documents/{doc_a['id']}/withdraw",
                              {"reason": "Wrong photo"}, if_match=doc_a["version"])  # fmt: skip
    after = ok(r)["customer_documents"]["documents"][0]
    assert after["status"] == "WITHDRAWN" and after["withdrawn_reason"] == "Wrong photo"  # the history stays
    assert _content(me_a, prop_a, doc_a["id"]).status == 404
    assert not [d for d in ok(me_a.property(prop_a["id"]))["documents"] if d["kind"] == "PROJECT_DOCUMENT"]
    again = t.as_(t.founder).post(f"{BASE}/{p_a['id']}/customer-documents/{doc_a['id']}/withdraw",
                                  {"reason": "Wrong photo"}, if_match=after["version"])  # fmt: skip
    assert again.code == "INVALID_STATE"


@pytest.mark.settings(**FLAGS, project_delivery_portal_enabled=False)
def test_nothing_is_served_while_the_delivery_view_is_off(team):
    t = team
    prop, p, me = _project(t, "2BHK", "docs-g@example.test")
    doc = ok(_publish(t, p, photo(t.as_(t.founder), "property", p["property"]["id"])), 201)
    doc = doc["customer_documents"]["documents"][0]
    assert _content(me, prop, doc["id"]).status == 404
    assert not [d for d in ok(me.property(prop["id"]))["documents"] if d["kind"] == "PROJECT_DOCUMENT"]
