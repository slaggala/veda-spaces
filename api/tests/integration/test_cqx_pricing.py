"""CQX-05 pricing and package presentation: frozen amounts only, nothing derived without approval, comparisons only of
packages the customer was explicitly given. SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import json

from tests.support.commercial import install_full_policy
from tests.support.proposal import PROPOSAL_ON, customer, ok, setup, share, step

pytestmark = PROPOSAL_ON


def test_pricing_is_the_frozen_amounts_and_derives_nothing_unapproved(api, factory):
    c, prop, est, q = setup(api, factory, "3BHK")
    page = customer(api, share(c, q)).get().data
    pr, summary = page["pricing"], page["proposal"]["summary"]
    assert pr["total"] == summary["total"] and pr["gst"] == summary["gst"] and pr["base_total"] == summary["base_total"]
    assert [r["subtotal"] for r in pr["rooms"]] == [r["subtotal"] for r in page["proposal"]["rooms"]]
    assert pr["milestones"] == page["proposal"]["payment_schedule"]
    assert all(set(m) == {"label", "share", "trigger"} for m in pr["milestones"])  # no rupee amount per milestone
    assert pr["unit_rates_shown"] is False and '"unit_rate":' not in json.dumps(page)
    assert pr["days_left"] == 30 and pr["alternatives"] == []
    assert pr["package"] is None  # no approved specification pinned: the package is not named by invention


def test_unit_rates_follow_the_owner_decision(api, factory):
    install_full_policy(OI_MTQ_10={"show_unit_rates": True})
    c, prop, est, q = setup(api, factory, "2BHK", policy=False)
    page = customer(api, share(c, q)).get().data
    assert page["pricing"]["unit_rates_shown"] is True


def test_comparison_lists_only_packages_shared_with_the_same_recipient(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    other = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    step(c, other, "submit", c.estimator)
    step(c, other, "approve", c.manager)
    other = ok(step(c, other, "issue", c.manager))
    assert other["quotation_number"] != q["quotation_number"]
    g = share(c, q)
    assert customer(api, g).get().data["pricing"]["alternatives"] == []  # not shared yet
    share(c, other, kind="CO_OWNER")
    assert customer(api, g).get().data["pricing"]["alternatives"] == []  # shared, but with someone else
    share(c, other)
    alts = customer(api, g).get().data["pricing"]["alternatives"]
    assert [a["reference"] for a in alts] == [f"{other['quotation_number']} v1"]
    assert set(alts[0]) == {"reference", "package", "total", "valid_until"}
    assert other["id"] not in json.dumps(alts)
