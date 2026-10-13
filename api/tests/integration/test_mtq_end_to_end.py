"""MTQ B2-B4 end-to-end on the five supported configurations (B1-01): 2, 3, 4, 5 BHK apartments and an independent
house, each from a SYNTHETIC verified measurement set to a quotation.

Two runs per configuration:

- **as committed** (every owner decision blank): the pipeline drafts the quotation and shows exactly why it is not
  customer-issuable (never a guessed value);
- **SYNTHETIC decisions** (test-only policy, refused elsewhere): the same pipeline reaches ISSUED and ACCEPTED, the
  frozen document reconciles with its estimate, and every included line traces back to the measurement set.

Status of these results: SYNTHETIC_VALIDATED. No live site, real rate or owner decision is involved. With
``MTQ_E2E_EVIDENCE=<path>`` the run writes its per-configuration summary there (the committed evidence file).
"""

from __future__ import annotations

import json
import os

import pytest

from tests.support.commercial import (
    ALL_ON,
    SITES,
    Commercial,
    approved_estimate,
    install_full_policy,
    load_card,
    ok,
    step,
)
from veda.modules.mtq_commercial import policy

pytestmark = ALL_ON
_EVIDENCE: dict[str, dict] = {}


def _summary(key: str, mode: str, prop: dict, est: dict, q: dict, extra: dict) -> None:
    lines = [x for sec in q["sections"] for x in sec["lines"]]
    _EVIDENCE.setdefault(key, {})[mode] = {
        "status": "SYNTHETIC_VALIDATED",
        "derived_bedrooms": prop["derived_bedroom_count"],
        "derived_levels": prop["derived_level_count"],
        "spaces": len(prop["spaces"]),
        "estimate_lines": len(est["lines"]),
        "unpriced_lines": est["unpriced_lines"],
        "quotation_lines": len(lines),
        "optional_lines": sum(1 for x in lines if x["is_optional"]),
        "subtotal_minor": est["subtotal_minor"],
        "total_minor": q["total_minor"],
        "quotation_status": q["status"],
        "customer_issuable": q["customer_issuable"],
        "blockers": sorted({f"{b['code']}:{b.get('decision') or ''}".rstrip(":") for b in q["blockers"]}),
        **extra,
    }


@pytest.mark.parametrize("key", list(SITES))
def test_pipeline_as_committed_drafts_and_explains_every_blocker(api, factory, key):
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, key)
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    codes = {(b["code"], b.get("decision")) for b in q["blockers"]}
    assert ("GST_POLICY_REQUIRED", "OI-MTQ-07") in codes and ("RULESET_NOT_APPROVED", "OI-MTQ-03") in codes
    if key in ("5BHK", "IH"):  # the preparation-package driver is the owner's (OI-MTQ-15)
        assert ("OWNER_DECISION_REQUIRED", "OI-MTQ-15") in codes
    assert q["customer_issuable"] is False
    prop = ok(c.as_(c.estimator).get(f"/api/v1/properties/{prop['id']}"))
    assert prop["derived_bedroom_count"] == SITES[key]["bedrooms"]
    _summary(key, "as_committed", prop, est, q, {})


@pytest.mark.parametrize("key", list(SITES))
def test_pipeline_with_synthetic_decisions_reaches_acceptance(api, factory, key):
    decisions = {}
    if key in ("5BHK", "IH"):  # SYNTHETIC drivers so the preparation lines price (never a real decision)
        decisions["OI_MTQ_15"] = {"home_size_by_bedrooms": {"5": "4BHK"}, "independent_house_factor_bp": 13_000}
    install_full_policy(**decisions)
    load_card()
    c = Commercial(api, factory)
    prop, est = approved_estimate(c, key)
    assert est["unpriced_lines"] == sum(1 for x in est["lines"] if x["rate_status"] != "PRICED")
    included_unpriced = [x for x in est["lines"] if x["rate_status"] != "PRICED" and not x["is_optional"]]
    q = ok(c.as_(c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
    if included_unpriced:  # an accepted item with no catalogue line keeps the quotation from being issued
        assert any(b["code"] == "UNPRICED_LINES" for b in q["blockers"])
        _summary(key, "synthetic_decisions", prop, est, q, {"stopped_at": "UNPRICED_LINES"})
        return
    assert q["blockers"] == [], q["blockers"]
    step(c, q, "submit", c.estimator)
    step(c, q, "approve", c.manager)
    q = ok(step(c, q, "issue", c.manager))
    lines = [x for sec in q["sections"] for x in sec["lines"]]
    included = [x for x in lines if not x["is_optional"]]
    # the frozen document reconciles with the approved estimate, to the paisa
    assert q["base_total_minor"] == est["subtotal_minor"] == sum(x["amount_minor"] for x in included)
    assert (
        q["tax_minor"] == sum(x["tax_minor"] for x in included)
        and q["total_minor"] == q["taxable_minor"] + q["tax_minor"]
    )
    # every included measured line traces back to the measurement set
    traced = 0
    for x in included:
        if x["line_key"].split(":")[0] in ("FLOOR_PROTECTION", "PLY_PROTECTION", "FREIGHT", "DEBRIS", "DEEP_CLEANING",
                                           "PEST_CONTROL"):  # fmt: skip
            continue
        t = ok(c.as_(c.estimator).get(f"/api/v1/quotation-lines/{x['id']}/trace"))
        assert t["measurement"]["measurement_set_id"] == est["measurement_set_id"], x["description"]
        traced += 1
    q = ok(step(c, q, "decision", c.sales, {"decision": "ACCEPTED", "method": "SIGNED_COPY"}))
    assert q["status"] == "ACCEPTED" and q["snapshot_verified"] is True
    _summary(
        key, "synthetic_decisions", prop, est, q, {"traced_lines": traced, "policy_version": policy.current().version}
    )


def teardown_module(module):
    out = os.environ.get("MTQ_E2E_EVIDENCE")
    if out and _EVIDENCE:
        doc = {"evidence": "MTQ B2-B4 end-to-end, five supported configurations", "status": "SYNTHETIC_VALIDATED",
               "note": "Synthetic sites (tests/support/ten_site.py), the SYNTHETIC test rate card and, for the decided "
                       "runs, the SYNTHETIC test policy. No live site, real rate or owner decision.",
               "configurations": _EVIDENCE}  # fmt: skip
        with open(out, "w") as fh:
            json.dump(doc, fh, indent=1, sort_keys=True)
