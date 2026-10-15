"""CQX-07 customer questions and change requests: structured, sanitised, idempotent, never scope; answered by staff and
linked to the revision that answers them; private to one recipient kind. SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import sqlalchemy as sa

from tests.support.proposal import INTERACTION_ON, PROPOSAL_ON, customer, ok, setup, share, step
from veda.kernel import db

K = "k" * 32


def _ask(cust, body: dict, key: str = K):
    return cust.post("/requests", body, key=key)


@PROPOSAL_ON
def test_requests_are_closed_while_interaction_is_off(api, factory):
    c, prop, est, q = setup(api, factory)
    r = _ask(customer(api, share(c, q)), {"category": "GENERAL_QUESTION", "message": "Hello there"})
    assert r.status == 404


@INTERACTION_ON
def test_question_is_idempotent_sanitised_and_never_becomes_scope(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    from veda.modules.mtq_commercial.models import Requirement, ScopeItem

    with db.unit_of_work() as s:
        before = (s.execute(sa.select(sa.func.count()).select_from(Requirement)).scalar(),
                  s.execute(sa.select(sa.func.count()).select_from(ScopeItem)).scalar())  # fmt: skip
    text = "Please add a <script>alert(1)</script> study unit\x00 in bedroom 2"
    r = _ask(cust, {"category": "GENERAL_QUESTION", "message": text})
    assert r.status == 201 and len(r.data) == 1
    item = r.data[0]
    assert item["message"] == "Please add a <script>alert(1)</script> study unit in bedroom 2"  # stored as text, no NUL
    assert item["status"] == "OPEN" and item["status_label"] == "Sent" and item["response"] is None
    again = _ask(cust, {"category": "GENERAL_QUESTION", "message": text})  # a retry with the same key
    assert again.status == 201 and len(again.data) == 1
    r = _ask(cust, {"category": "GENERAL_QUESTION", "message": "Something else entirely"})
    assert r.status == 409 and r.code == "IDEMPOTENCY_KEY_REUSED"
    assert cust.post("/requests", {"category": "GENERAL_QUESTION", "message": "No key"}).status == 422
    for bad in ("", "  ", "x" * 2001):
        assert _ask(cust, {"category": "GENERAL_QUESTION", "message": bad}, key="b" * 32).status == 422
    assert _ask(cust, {"category": "GENERAL_QUESTION", "message": "hi", "html": "<b>"}, key="c" * 32).status == 422
    with db.unit_of_work() as s:
        after = (s.execute(sa.select(sa.func.count()).select_from(Requirement)).scalar(),
                 s.execute(sa.select(sa.func.count()).select_from(ScopeItem)).scalar())  # fmt: skip
    assert after == before  # customer text never becomes scope
    after_q = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    assert after_q["status"] == "ISSUED" and after_q["snapshot_sha256"] == q["snapshot_sha256"]


@INTERACTION_ON
def test_change_requests_are_structured(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    page = cust.get().data
    line = page["proposal"]["rooms"][0]["lines"][0]
    room = page["proposal"]["rooms"][0]
    assert _ask(cust, {"category": "REMOVE_ITEM", "message": "Remove this please"}, key="a" * 32).status == 422
    assert _ask(cust, {"category": "CHANGE_QUANTITY", "line_ref": line["ref"], "requested_quantity": "2",
                       "message": "Two of these"}, key="b" * 32).status == 201  # fmt: skip
    assert (
        _ask(cust, {"category": "CHANGE_FINISH", "line_ref": "L9999", "message": "Acrylic"}, key="c" * 32).status == 422
    )
    assert _ask(cust, {"category": "ADD_ITEM", "room_ref": "R99", "message": "A shoe rack"}, key="d" * 32).status == 422
    assert (
        _ask(cust, {"category": "ADD_ITEM", "requested_quantity": "3", "message": "Three racks"}, key="e" * 32).status
        == 422
    )
    r = _ask(
        cust, {"category": "ADD_ITEM", "room_ref": room["ref"], "message": "A shoe rack near the door"}, key="f" * 32
    )
    assert r.status == 201
    items = {i["category"]: i for i in r.data}
    assert items["CHANGE_QUANTITY"]["requested_quantity"] == "2" and items["CHANGE_QUANTITY"]["line_ref"] == line["ref"]
    assert items["ADD_ITEM"]["room"] == room["title"] and items["CHANGE_QUANTITY"]["room"] == room["title"]


@INTERACTION_ON
def test_staff_answer_and_link_the_revision_and_the_customer_sees_it(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    line = cust.get().data["proposal"]["rooms"][0]["lines"][0]
    _ask(cust, {"category": "CHANGE_MATERIAL", "line_ref": line["ref"], "message": "Can this be plywood?"})
    act = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}/customer-activity"))
    req = act["requests"][0]
    assert req["recipient_kind"] == "PRIMARY_CUSTOMER" and req["message"] == "Can this be plywood?"
    api_ = c.as_(c.estimator)
    r = api_.post(
        f"/api/v1/customer-requests/{req['id']}/respond", {"status": "NEEDS_CLARIFICATION"}, if_match=req["version"]
    )
    assert r.status == 422  # a clarification request says what is needed
    req = ok(api_.post(f"/api/v1/customer-requests/{req['id']}/respond",
                       {"status": "NEEDS_CLARIFICATION", "response": "Which grade of plywood?"}, if_match=req["version"]))  # fmt: skip
    page = cust.get().data
    assert page["requests"]["items"][0]["response"] == "Which grade of plywood?"
    assert any(a["code"] == "CLARIFY_REQUEST" for a in page["actions"])
    r = api_.post(
        f"/api/v1/customer-requests/{req['id']}/respond", {"status": "ACCEPTED_FOR_REVISION"}, if_match=req["version"]
    )
    assert r.status == 422  # accepted for revision only by linking the revision
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    r = api_.post(
        f"/api/v1/customer-requests/{req['id']}/link", {"resulting_quotation_id": q["id"]}, if_match=req["version"]
    )
    assert r.status == 422 and r.code == "LINEAGE_MISMATCH"  # the same version answers nothing
    for _ in ("draft", "in review", "approved"):  # N12: never a version the customer has not been issued
        cur = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q2['id']}"))
        r = api_.post(f"/api/v1/customer-requests/{req['id']}/link", {"resulting_quotation_id": q2["id"]},
                      if_match=req["version"])  # fmt: skip
        assert r.status == 409 and r.code == "VERSION_NOT_ISSUED" and r.json["status"] == 409, (cur["status"], r)
        if cur["status"] == "DRAFT":
            step(c, q2, "submit", c.estimator)
        elif cur["status"] == "INTERNAL_REVIEW":
            step(c, q2, "approve", c.manager)
    q2 = ok(step(c, q2, "issue", c.manager))
    req = ok(api_.post(f"/api/v1/customer-requests/{req['id']}/link",
                       {"resulting_quotation_id": q2["id"], "response": "Revised in version 2."}, if_match=req["version"]))  # fmt: skip
    assert req["status"] == "ACCEPTED_FOR_REVISION" and req["resulting_label"] == "Version 2"
    item = cust.get().data["requests"]["items"][0]
    assert item["answered_by_revision"] == "Version 2" and q2["id"] not in str(item)
    req = ok(
        api_.post(f"/api/v1/customer-requests/{req['id']}/respond", {"status": "RESOLVED"}, if_match=req["version"])
    )
    r = api_.post(f"/api/v1/customer-requests/{req['id']}/respond", {"status": "UNDER_REVIEW"}, if_match=req["version"])
    assert r.status == 409  # resolved is final
    assert c.as_(c.designer).post(f"/api/v1/customer-requests/{req['id']}/respond", {"status": "RESOLVED"},
                                  if_match=req["version"]).status in (403, 404)  # fmt: skip


@INTERACTION_ON
def test_requests_are_private_to_the_recipient_kind(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    primary = customer(api, share(c, q))
    co_owner = customer(api, share(c, q, kind="CO_OWNER"))
    _ask(primary, {"category": "DISCUSS_PRICE", "message": "Is there any flexibility?"})
    assert co_owner.get("/requests").data == []
    assert len(primary.get("/requests").data) == 1


@INTERACTION_ON
def test_lead_erasure_removes_customer_text_and_closes_links(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    g = share(c, q)
    cust = customer(api, g)
    _ask(cust, {"category": "GENERAL_QUESTION", "message": "My neighbour Ravi suggested you"})
    from veda.kernel.context import actor, system_context
    from veda.modules.crm.leads import erasure as lead_erasure
    from veda.modules.crm.leads.models import Lead
    from veda.modules.customer_proposal.models import CustomerProposalRequest, ProposalAccessGrant

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        lead_erasure.run(s, s.get(Lead, prop["lead_id"]))
    with db.unit_of_work() as s:
        row = s.execute(sa.select(CustomerProposalRequest)).scalar_one()
        assert row.body == "[erased]"
        grant = s.get(ProposalAccessGrant, g["id"])
        assert grant.status == "REVOKED" and grant.revoke_reason_code == "LEAD_ERASED"
    assert cust.get().status == 410


@INTERACTION_ON
def test_a_replacement_link_never_inherits_an_earlier_holders_conversation(api, factory):
    """N4: requests belong to the exact link that sent them; nothing is inferred from the recipient kind."""
    c, prop, est, q = setup(api, factory, "2BHK")
    old = share(c, q, kind="FAMILY_MEMBER")
    assert (
        _ask(customer(api, old), {"category": "GENERAL_QUESTION", "message": "A private family question"}).status == 201
    )
    cur = next(x for x in ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/access-grants")) if x["id"] == old["id"])
    ok(c.as_(c.sales).post(f"/api/v1/proposal-access-grants/{old['id']}/revoke", if_match=cur["version"]))
    new = customer(api, share(c, q, kind="FAMILY_MEMBER"))
    assert new.get("/requests").data == [] and new.get().data["requests"]["items"] == []
    other = customer(api, share(c, q, kind="OTHER"))
    assert other.get("/requests").data == []
    primary = customer(api, share(c, q))
    assert primary.get("/requests").data == []  # no shared-recipient policy exists: the primary sees only their own
    acts = ok(c.as_(c.sales).get(f"/api/v1/quotations/{q['id']}/customer-activity"))["requests"]
    assert [a["message"] for a in acts] == ["A private family question"]  # staff, by permission, see all
    assert c.as_(c.designer).get(f"/api/v1/quotations/{q['id']}/customer-activity").status in (403, 404)


@INTERACTION_ON
def test_a_request_can_only_name_a_line_the_customer_can_see(api, factory):
    """N3: a line the frozen document omits (a zero line) or another version's line is never a valid reference."""
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    from veda.modules.customer_proposal import projection
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work() as s:
        qq = s.get(Quotation, q["id"])
        shown, _ = projection.printed(s, qq)
        hidden = [ref for ref in projection.refs(s, qq) if ref not in shown]
    for ref in hidden[:3] + ["L9999"]:
        r = _ask(
            cust,
            {"category": "LINE_QUESTION", "line_ref": ref, "message": "What is this line?"},
            key=ref.ljust(32, "x"),
        )
        assert r.status == 422 and r.json["errors"][0]["code"] == "UNKNOWN_LINE", (ref, r)
