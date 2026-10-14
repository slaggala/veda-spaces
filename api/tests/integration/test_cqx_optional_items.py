"""CQX-06 optional-item selection: explicit, idempotent, server-recalculated, never a quotation edit; a price is shown
only when the owner allows live totals (CQX-D02). SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import sqlalchemy as sa

from tests.support.proposal import INTERACTION_ON, PROPOSAL_ON, customer, install_proposal_policy, ok, setup, share
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context


def _amount(text: str) -> int:
    return int(Decimal(text.replace(",", "")) * 100)


def _optional(page: dict) -> list[dict]:
    return [x for x in page["proposal"]["optional_items"] if x["priced"]]


@PROPOSAL_ON
def test_choices_are_closed_while_interaction_is_off(api, factory):
    c, prop, est, q = setup(api, factory)
    cust = customer(api, share(c, q))
    r = cust.post("/selections", {"line_ref": "L1", "state": "SELECTED"})
    assert r.status == 404 and r.code == "NOT_FOUND"


@INTERACTION_ON
def test_a_choice_is_a_proposal_and_the_price_waits_for_the_owner(api, factory):
    c, prop, est, q = setup(api, factory, "3BHK")
    cust = customer(api, share(c, q))
    page = cust.get().data
    assert any(a["code"] == "REVIEW_OPTIONAL_ITEMS" for a in page["actions"])
    item = _optional(page)[0]
    before = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    r = cust.post("/selections", {"line_ref": item["ref"], "state": "SELECTED"})
    assert r.status == 200 and r.data["selected_refs"] == [item["ref"]]
    assert (
        r.data["status"] == "PRICE_CONFIRMATION_REQUIRED"
        and r.data["total_with_selections"] is None
        and r.data["extra"] is None
    )
    after = ok(c.as_(c.founder).get(f"/api/v1/quotations/{q['id']}"))
    for k in ("total_minor", "base_total_minor", "optional_minor", "snapshot_sha256", "status", "version"):
        assert after[k] == before[k], k  # the quotation never changes
    page = cust.get().data
    assert not any(a["code"] == "REVIEW_OPTIONAL_ITEMS" for a in page["actions"])


@INTERACTION_ON
def test_live_total_is_server_computed_idempotent_and_never_double_counted(api, factory):
    install_proposal_policy()  # SYNTHETIC: CQX-D02 live_total true
    c, prop, est, q = setup(api, factory, "3BHK")
    cust = customer(api, share(c, q))
    page = cust.get().data
    items = _optional(page)
    assert len(items) >= 2
    a, b = items[0], items[1]
    from veda.modules.customer_proposal import projection, selections
    from veda.modules.mtq_commercial.models import Quotation

    with db.unit_of_work() as s:
        qq = s.get(Quotation, q["id"])
        refs = projection.refs(s, qq)
        value = {k: selections.line_value(refs[k]) for k in (a["ref"], b["ref"])}
        total = qq.total_minor
    r1 = cust.post("/selections", {"line_ref": a["ref"], "state": "SELECTED"}).data
    r2 = cust.post("/selections", {"line_ref": a["ref"], "state": "SELECTED"}).data  # retried: no change
    assert r1 == r2 and r1["status"] == "CALCULATED"
    assert _amount(r1["total_with_selections"]) == total + value[a["ref"]]
    r3 = cust.post("/selections", {"line_ref": b["ref"], "state": "SELECTED"}).data
    assert _amount(r3["total_with_selections"]) == total + value[a["ref"]] + value[b["ref"]]
    r4 = cust.post("/selections", {"line_ref": a["ref"], "state": "DESELECTED"}).data
    assert _amount(r4["total_with_selections"]) == total + value[b["ref"]] and r4["selected_refs"] == [b["ref"]]
    r5 = cust.post("/selections", {"line_ref": a["ref"], "state": "REQUESTED_FOR_DISCUSSION"}).data
    assert _amount(r5["total_with_selections"]) == total + value[b["ref"]]  # discussion adds nothing
    from veda.modules.customer_proposal.models import CustomerOptionalSelection, ProposalEvent

    with db.unit_of_work() as s:
        sel = s.execute(
            sa.select(CustomerOptionalSelection).where(CustomerOptionalSelection.line_ref == a["ref"])
        ).scalar_one()
        assert sel.change_no == 3  # SELECTED, DESELECTED, REQUESTED_FOR_DISCUSSION (the retry recorded nothing)
        changes = (
            s.execute(sa.select(ProposalEvent).where(ProposalEvent.event_code == "SELECTION_CHANGED")).scalars().all()
        )
        assert len(changes) == 4


@INTERACTION_ON
def test_only_optional_lines_of_an_open_proposal_can_be_chosen(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    page = cust.get().data
    included = page["proposal"]["rooms"][0]["lines"][0]["ref"]
    for ref in (included, "L9999"):
        r = cust.post("/selections", {"line_ref": ref, "state": "SELECTED"})
        assert r.status == 422 and r.json["errors"][0]["code"] == "NOT_OPTIONAL", r
    r = cust.post("/selections", {"line_ref": "1; DROP", "state": "SELECTED"})
    assert r.status == 422
    r = cust.post("/selections", {"line_ref": _optional(page)[0]["ref"], "state": "NOT_SELECTED"})
    assert r.status == 422  # NOT_SELECTED is a starting state, not a choice
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        from veda.modules.mtq_commercial.models import Quotation

        s.get(Quotation, q["id"]).valid_until = clock.now().date() - timedelta(days=1)
    r = cust.post("/selections", {"line_ref": _optional(page)[0]["ref"], "state": "SELECTED"})
    assert r.status == 409 and r.code == "PROPOSAL_NOT_OPEN"


@INTERACTION_ON
def test_staff_review_the_choices(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    cust = customer(api, share(c, q))
    item = _optional(cust.get().data)[0]
    cust.post("/selections", {"line_ref": item["ref"], "state": "REQUESTED_FOR_DISCUSSION"})
    act = ok(c.as_(c.estimator).get(f"/api/v1/quotations/{q['id']}/customer-activity"))
    assert act["selections"] == [{**act["selections"][0], "line_ref": item["ref"], "state": "REQUESTED_FOR_DISCUSSION"}]
    assert c.as_(c.designer).get(f"/api/v1/quotations/{q['id']}/customer-activity").status in (403, 404)
    from veda.platform.notifications.models import OutboxEvent

    with db.unit_of_work() as s:
        assert "proposal.optional_selected" in [o.event_type for o in s.execute(sa.select(OutboxEvent)).scalars()]
