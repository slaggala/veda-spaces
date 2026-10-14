"""CQX-03 project and room overview: room cards, counts, state, capabilities, history and notices for every supported
configuration, from one generic structure (no per-BHK component). SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.support.proposal import INTERACTION_ON, PROPOSAL_ON, customer, ok, setup, share, step
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context


@PROPOSAL_ON
@pytest.mark.parametrize("key", ["2BHK", "3BHK", "4BHK", "5BHK", "IH"])
def test_room_overview_for_every_configuration(api, factory, key):
    c, prop, est, q = setup(api, factory, key)
    page = customer(api, share(c, q)).get().data
    p = page["proposal"]
    rooms = [r for r in p["rooms"] if r["kind"] == "ROOM"]
    beds = {"2BHK": 2, "3BHK": 3, "4BHK": 4, "5BHK": 5, "IH": 3}[key]
    assert f"{beds} BHK" in p["property"]["configuration"]
    assert ("independent house" in p["property"]["configuration"]) == (key == "IH")
    assert len(rooms) >= beds  # at least one card per bedroom
    for r in p["rooms"]:
        assert r["included_count"] == len([x for x in r["lines"] if x["status"] != "Optional"])
        assert r["optional_count"] == len([x for x in p["optional_items"] if x["room_ref"] == r["ref"]])
    assert sum(r["optional_count"] for r in p["rooms"]) <= len(p["optional_items"])
    assert page["state"] == "OPEN" and page["history"] == [] and page["notices"] == []
    assert page["capabilities"] == {"interaction": False, "acceptance": False}  # only viewing is on


@INTERACTION_ON
def test_capabilities_follow_flags_and_state_and_history_lists_issued_versions(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    assert customer(api, share(c, q)).get().data["capabilities"]["interaction"] is True
    q2 = ok(step(c, q, "versions", c.estimator, {"cost_estimate_id": est["id"]}, code=201))
    step(c, q2, "submit", c.estimator)
    step(c, q2, "approve", c.manager)
    q2 = ok(step(c, q2, "issue", c.manager))
    g2 = share(c, q2)
    page = customer(api, g2).get().data
    assert page["history"] == [{"version_no": 1, "issued_on": q["issued_on"][:10]}]
    assert page["proposal"]["version_no"] == 2
    # past its validity: viewable, marked, and no customer action is offered
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        from veda.modules.mtq_commercial.models import Quotation

        s.get(Quotation, q2["id"]).valid_until = clock.now().date() - timedelta(days=1)
    page = customer(api, g2).get().data
    assert page["state"] == "EXPIRED" and page["capabilities"] == {"interaction": False, "acceptance": False}
    assert page["notices"][0]["code"] == "EXPIRED"


@PROPOSAL_ON
def test_a_link_close_to_its_expiry_says_so(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    page = customer(api, share(c, q, days=1)).get().data
    assert any(n["code"] == "LINK_EXPIRES_SOON" for n in page["notices"])
