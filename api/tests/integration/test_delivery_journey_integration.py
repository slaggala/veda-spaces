"""The staging journey across modules (decision log 49): an accepted quotation opens a commercial record, the project
is booked from the same acceptance, executed, and can be handed over only once Project Commercials says the obligation
is satisfied (the committed PEX-D02); the handover registers the warranty entitlement and the customer then sees the
delivery view and can raise a service request. Every flag the staging enablement turns on is on, plus warranty
service. The project-delivery decisions are the committed record (PEX-D01, PEX-D02); the lifecycle, commercials and
warranty policies are SYNTHETIC test policies. SYNTHETIC data only, both engines."""

from __future__ import annotations

import pytest

from tests.support.commercial import ok
from tests.support.commercials import BASE as CBASE
from tests.support.commercials import Commercials, install_policy
from tests.support.mtq import photo
from tests.support.portal import PUBLIC
from tests.support.project import BASE, advance_to, install, no_four_eyes
from tests.support.warranty import WARRANTY, Service, policy
from veda.kernel import clock
from veda.platform.notifications import worker

FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True, customer_portal_enabled=True,
             project_lifecycle_enabled=True, project_commercials_enabled=True, project_delivery_portal_enabled=True,
             warranty_service_enabled=True)  # fmt: skip
pytestmark = pytest.mark.settings(**FLAGS)
GATE = "COMMERCIAL_CONDITION"


class Journey(Service):
    """The service harness plus the accountant and the commercial calls of ``Commercials``."""

    def __init__(self, api, factory):
        super().__init__(api, factory)
        self.accountant = factory.user("ACCOUNTANT", mfa=True)

    def call(self, method: str, path: str, body=None, user=None, **kw):
        return self.api.call(method, path, body, token=self.token(user or self.accountant), **kw)

    open = Commercials.open
    pay = Commercials.pay

    def account(self, acc: dict) -> dict:
        return ok(self.call("GET", f"{CBASE}/{acc['id']}"))


@pytest.fixture
def journey(api, factory):
    from veda.modules.project import delivery_policy

    install(no_four_eyes())
    t = Journey(api, factory)
    install_policy()
    delivery_policy.install_for_tests(None)  # the committed owner decisions, not the harness's synthetic NONE
    yield t
    install(None)
    policy(None)


def _commercial_codes(t: Journey, p: dict) -> set[str]:
    return {b["code"] for b in t.get(p)["handover_readiness"]["blockers"] if b["gate"] == GATE}


def test_acceptance_to_commercials_to_handover_to_warranty_and_the_customer_view(journey):
    t = journey
    prop, _, q = t.accepted("2BHK")
    acc = t.open(q)  # the commercial record of the accepted quotation
    p = t.book(q, prop)  # the project, from the same acceptance
    assert p["quotation_number"] == acc["quotation_number"]  # one chain: the record and the project
    t.staff(p)
    me = t.invite(prop["lead_id"], "journey-owner@example.test")

    p = advance_to(t, t.get(p), "SNAGGING")
    assert _commercial_codes(t, p) == {"COMMERCIAL_OBLIGATION_OUTSTANDING"}  # PEX-D02: nothing paid yet
    t.checklist(p)
    refused = t.transition(p, "READY_FOR_HANDOVER")
    assert refused["outcome"] == "REFUSED"
    assert GATE in {b["gate"] for b in refused["transition"]["blockers"]}  # no override: refused, recorded

    view = me.api.call("GET", f"{PUBLIC}/properties/{prop['id']}", headers={"X-Veda-Portal": me.token},
                       anonymous=True)  # fmt: skip
    assert view.status == 200, view
    assert view.data["delivery"] is not None  # the customer's delivery view with every staging flag on

    total = t.account(acc)["position"]["value_minor"]
    t.pay(acc, total)  # Project Commercials: nothing outstanding
    assert _commercial_codes(t, p) == set()

    p = advance_to(t, t.get(p), "READY_FOR_HANDOVER")
    t.checklist(p)
    t.package(p)
    att = photo(t.as_(t.founder), "property", p["property"]["id"])
    body = {"handover_on": clock.now().date().isoformat(), "acknowledgement_reference": "HS-SYN-J1",
            "evidence_attachment_id": att["id"]}  # fmt: skip
    done = ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=t.get(p)["version"]), 201)
    assert done["outcome"] == "COMPLETED", done

    worker.drain_all()  # the project.handed_over outbox handler runs the post-handover subscribers
    e = t.register(t.get(p), status=200)  # already registered by the warranty subscriber
    assert e["registered_via"] == "HANDOVER_EVENT" and e["status"] == "NOT_RECORDED"  # WSV-D01 null: no invented terms
    assert ok(t.as_(t.care).get(f"{WARRANTY}/projects/{p['id']}"))["registered"] is True

    r = t.submit(me, prop, t.get(p))
    assert r.status == 201, r
    req = r.data["request"]
    assert req["status"] == "REPORTED"
    assert t.resolved(req["id"])["status"] != "REPORTED"  # triage, coverage decision, visit, resolution
