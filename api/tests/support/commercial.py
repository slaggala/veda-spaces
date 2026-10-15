"""MTQ B2-B4 test harness: SYNTHETIC sites measured and verified through the real B1 API, then driven through scope,
BOQ, estimate and quotation as staff would.

Nothing here is a real site, customer, rate or policy: the rate card is the SYNTHETIC test card, and any commercial
policy a test installs is marked SYNTHETIC and refused outside tests. Results are SYNTHETIC_VALIDATED only.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tests.support.ten_site import TenSite
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.estimator import service as estimator_service

CARD_DOC = json.loads((Path(__file__).parents[1] / "fixtures/estimator/synthetic-rate-card.json").read_text())
APPROVAL = "Owner approval reference (synthetic test card)"
ON = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True)
ALL_ON = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True)

# The five supported configurations (B1-01), one synthetic site each.
SITES: dict[str, dict[str, Any]] = {
    "2BHK": {"site_id": "S41", "template_key": "APARTMENT_2BHK", "survey_level_code": "FULL", "bedrooms": 2},
    "3BHK": {"site_id": "S42", "template_key": "APARTMENT_3BHK", "survey_level_code": "FULL", "bedrooms": 3},
    "4BHK": {"site_id": "S43", "template_key": "APARTMENT_4BHK", "survey_level_code": "FULL", "bedrooms": 4},
    "5BHK": {"site_id": "S44", "template_key": "APARTMENT_5BHK", "survey_level_code": "FULL", "bedrooms": 5},
    "IH": {"site_id": "S45", "template_key": "INDEPENDENT_HOUSE", "survey_level_code": "FULL", "bedrooms": 3,
           "levels": 2},
}  # fmt: skip


def load_card(doc: dict | None = None, *, version: str | None = None, activate: bool = True,
              mutate=None) -> str:  # fmt: skip
    d = copy.deepcopy(doc or CARD_DOC)
    if version:
        d["version"] = version
    if mutate:
        mutate(d)
    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        estimator_service.load_card(s, d)
        if activate:
            estimator_service.activate_card(s, d["version"], APPROVAL)
    return d["version"]


def ok(r, *codes):
    assert r.status in (codes or (200, 201)), r
    return r.data


class Commercial:
    """A measured, verified synthetic site plus the commercial team: estimator, sales manager, designer."""

    def __init__(self, api, factory):
        self.api, self.factory = api, factory
        self.ten = TenSite(api, factory)
        self.estimator = factory.user("ESTIMATOR")
        self.manager = factory.user("SALES_MANAGER", mfa=True)
        self.second_manager = factory.user("SALES_MANAGER", mfa=True)
        self.designer = factory.user("DESIGNER")
        self.sales = self.ten.sales
        self.founder = self.ten.founder

    def as_(self, user):
        self.factory.login(self.api, user)
        return self.api

    def site(self, key: str) -> dict:
        _, measured, _ = self.ten.run_site(SITES[key])
        return measured["property"]

    def remeasure(self, prop: dict, from_set_id: str) -> dict:
        """A re-measure: a new FULL revision copied from ``from_set_id``, photographed, submitted and verified."""
        ten = self.ten
        visit = ten._visit(prop["id"], ten.lead_surveyor, "FULL")
        surveyor = ten.as_(ten.lead_surveyor)
        new = ok(surveyor.post(f"/api/v1/measurement-visits/{visit['id']}/measurement-sets",
                               {"unit_system_code": "MM", "copy_from_set_id": from_set_id}))  # fmt: skip
        ten._photos(new["id"], [], "FULL")
        cur = ok(ten.as_(ten.lead_surveyor).get(f"/api/v1/measurement-sets/{new['id']}"))
        ok(ten.as_(ten.lead_surveyor).post(f"/api/v1/measurement-sets/{new['id']}/submit", if_match=cur["version"]))
        founder = ten.as_(ten.founder)
        checks = ok(founder.get(f"/api/v1/measurement-sets/{new['id']}/checks"))
        acks = [{"code": p["code"], "note": "synthetic"} for p in checks["verify_problems"] if p.get("acknowledgeable")]
        cur = ok(founder.get(f"/api/v1/measurement-sets/{new['id']}"))
        return ok(founder.post(f"/api/v1/measurement-sets/{new['id']}/verify", {"acknowledgements": acks},
                               if_match=cur["version"]))  # fmt: skip

    # --- B2 ---------------------------------------------------------------------------------------------------------
    def seed(self, prop: dict, user=None) -> list[dict]:
        api = self.as_(user or self.estimator)
        ok(api.post(f"/api/v1/properties/{prop['id']}/requirements/seed"))
        return ok(api.get(f"/api/v1/properties/{prop['id']}/requirements"))

    def decide_all(self, prop: dict, *, optional: str = "EXCLUDED", user=None) -> list[dict]:
        """Accept every MANDATORY and RECOMMENDED proposal; decide OPTIONAL ones as ``optional``."""
        api = self.as_(user or self.estimator)
        for r in ok(api.get(f"/api/v1/properties/{prop['id']}/requirements")):
            if r["status"] != "PROPOSED":
                continue
            status = optional if r["necessity_code"] == "OPTIONAL" else "ACCEPTED"
            ok(api.post(f"/api/v1/requirements/{r['id']}/decision", {"status": status, "reason": "synthetic decision"},
                        if_match=r["version"]))  # fmt: skip
        return ok(api.get(f"/api/v1/properties/{prop['id']}/requirements"))

    def draft_scope(self, prop: dict, tier: str = "ESSENTIAL", user=None) -> dict:
        return ok(self.as_(user or self.estimator).post(f"/api/v1/properties/{prop['id']}/scopes", {"tier_code": tier}))

    def fill_staff_inputs(self, scope: dict, user=None) -> dict:
        """Enter the inputs the ruleset leaves to staff (drawer counts, COB counts, side-table sizes)."""
        api = self.as_(user or self.estimator)
        staff = {"DRAWERS": 4, "COB": 2, "WIDTH": 1.5, "HEIGHT": 1.5}
        for item in scope["items"]:
            missing = {n: staff[n] for n, d in item["inputs"].items() if d.get("source") == "MISSING" and n in staff}
            if missing:
                cur = ok(api.get(f"/api/v1/scopes/{scope['id']}"))
                it = next(i for i in cur["items"] if i["id"] == item["id"])
                ok(api.patch(f"/api/v1/scope-items/{item['id']}", {"dimension_overrides": missing,
                             "override_reason": "Entered from the design layout (synthetic)"}, if_match=it["version"]))  # fmt: skip
        return ok(api.get(f"/api/v1/scopes/{scope['id']}"))

    def confirm(self, scope: dict, user=None) -> dict:
        api = self.as_(user or self.estimator)
        cur = ok(api.get(f"/api/v1/scopes/{scope['id']}"))
        return ok(api.post(f"/api/v1/scopes/{scope['id']}/confirm", if_match=cur["version"]))

    def boq(self, scope: dict, user=None) -> dict:
        return ok(self.as_(user or self.estimator).post(f"/api/v1/scopes/{scope['id']}/boqs"), 201)

    def review(self, boq: dict, user=None):
        api = self.as_(user or self.estimator)
        cur = ok(api.get(f"/api/v1/boqs/{boq['id']}"))
        return api.post(f"/api/v1/boqs/{boq['id']}/review", if_match=cur["version"])

    def reviewed_boq(self, key: str, *, optional: str = "EXCLUDED") -> tuple[dict, dict, dict]:
        """A synthetic site of ``key`` all the way to a reviewed BOQ: (property, scope, boq)."""
        prop = self.site(key)
        self.seed(prop)
        self.decide_all(prop, optional=optional)
        scope = self.fill_staff_inputs(self.draft_scope(prop))
        scope = self.confirm(scope)
        boq = self.boq(scope)
        reviewed = ok(self.review(boq))
        return prop, scope, reviewed


# A complete commercial policy for exercising the decided paths. SYNTHETIC: every value is invented for tests, the
# loader refuses this status outside the test environment, and nothing here is a Veda Spaces decision.
SYNTHETIC_POLICY: dict[str, Any] = {
    "schema": "veda.mtq.commercial-policy/1",
    "version": "SYNTHETIC-TEST-1",
    "status": "SYNTHETIC_TEST_ONLY",
    "note": "SYNTHETIC test policy. Not an owner decision.",
    "decisions": {
        "OI-MTQ-03": None,
        "OI-MTQ-04": None,
        "OI-MTQ-05": {
            "staff_tiers": ["PREMIUM"],
            "finish_rates": {"ACRYLIC": {"WARDROBE.BODY": {"ESSENTIAL": 150000}}},
        },
        "OI-MTQ-06": {"self_limit_bp": 200, "max_bp": 1000, "four_eyes": True},
        "OI-MTQ-07": {"mode": "SINGLE_RATE", "rate_bp": 1800, "discount_allocation": "PRO_RATA"},
        "OI-MTQ-08": {"validity_days": 30},
        "OI-MTQ-09": {
            "terms_version": "SYN-T1",
            "payment_milestones": [
                {"label": "Booking", "share_bp": 1000, "trigger": "On acceptance (synthetic)"},
                {"label": "Production", "share_bp": 5000, "trigger": "Before production (synthetic)"},
                {"label": "Handover", "share_bp": 4000, "trigger": "On handover (synthetic)"},
            ],
            "warranty": ["Synthetic warranty text for tests."],
            "assumptions": ["Synthetic assumption for tests."],
            "exclusions": ["Synthetic exclusion for tests."],
            "change_order_terms": "Synthetic change-order terms for tests.",
            "cancellation_terms": "Synthetic cancellation terms for tests.",
        },
        "OI-MTQ-10": {"show_unit_rates": False},
        "OI-MTQ-11": {"methods": ["STAFF_RECORDED", "SIGNED_COPY"]},
        "OI-MTQ-13": {"allowed": True, "rate_changes_allowed": False},
        "OI-MTQ-14": None,
        "OI-MTQ-15": {"home_size_by_bedrooms": {}, "independent_house_factor_bp": None},
        "OI-MTQ-18": None,  # the customer information pack: tests that need it install SYNTHETIC_PACK
    },
}


def install_policy(**decisions) -> dict:
    """Install SYNTHETIC_POLICY with ``decisions`` replaced (OI codes with '-' as '_': OI_MTQ_07=None)."""
    from veda.modules.mtq_commercial import policy

    doc = copy.deepcopy(SYNTHETIC_POLICY)
    for k, v in decisions.items():
        doc["decisions"][k.replace("_", "-")] = v
    policy.install_for_tests(doc)
    return doc


@pytest.fixture
def synthetic_policy(app):
    install_policy()
    yield
    from veda.modules.mtq_commercial import policy

    policy.install_for_tests(None)


def install_full_policy(**decisions) -> dict:
    """SYNTHETIC_POLICY plus OI-MTQ-03/04 recorded for the current ruleset (so scopes are APPROVED-ruleset)."""
    from veda.modules.mtq_commercial import rules

    approved = {"ruleset_version": rules.RULESET_VERSION, "ruleset_sha256": rules.sha256()}
    return install_policy(OI_MTQ_03=approved, OI_MTQ_04=approved, **decisions)


def approved_estimate(c: Commercial, key: str, *, optional: str = "ACCEPTED") -> tuple[dict, dict]:
    """A synthetic site through scope, BOQ and an approved Essential estimate: (property, estimate)."""
    prop, _, boq = c.reviewed_boq(key, optional=optional)
    est = ok(c.as_(c.estimator).post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
    est = ok(c.as_(c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"]))
    return prop, est


def step(c: Commercial, q: dict, action: str, user, body=None, code: int = 200):
    api = c.as_(user)
    cur = ok(api.get(f"/api/v1/quotations/{q['id']}"))
    r = api.post(f"/api/v1/quotations/{q['id']}/{action}", body, if_match=cur["version"])
    assert r.status == code, r
    return r
