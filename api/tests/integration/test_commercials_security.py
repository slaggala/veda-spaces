"""Project Commercials: staff authorisation, scope and the feature flag (PCM-020 … PCM-025). SYNTHETIC data only.

Only FOUNDER and SALES_MANAGER hold the ``commercials.*`` codes by default; every other role is refused every route.
An individually granted OWN-scope holder reaches only accounts on leads they own; any other account answers 404 (its
existence is not disclosed). With the flag off every route answers 404 before authentication.
"""

from __future__ import annotations

import pytest

from tests.support.commercials import BASE, ON, Commercials, key
from veda.kernel import clock
from veda.modules.commercials import permissions as P
from veda.platform.rbac import registry

pytestmark = ON


def test_the_default_grants_are_the_minimum_mapping():
    for code in P.CODES:
        assert registry.MATRIX[code] == {"FOUNDER": "A", "SALES_MANAGER": "A"}, code
        assert registry.BY_CODE[code].definition.supports_scope
    assert registry.validate_registry() == []


def test_roles_without_a_commercial_code_are_refused_everything(api, factory):
    t = Commercials(api, factory)
    _, q, acc = t.opened()
    line = acc["schedule"]["lines"][0]
    body = {"amount_minor": 100, "received_on": clock.now().date().isoformat(), "method_code": "CASH"}
    for role in ("SALES", "ESTIMATOR", "DESIGNER", "SURVEYOR", "ADMIN"):
        u = factory.user(role, mfa=role == "ADMIN")
        tok = t.tok(u)
        calls = [("GET", BASE, None), ("GET", f"{BASE}/{acc['id']}", None), ("GET", f"{BASE}/candidates", None),
                 ("POST", BASE, {"quotation_id": q["id"]}), ("GET", f"{BASE}/{acc['id']}/history", None),
                 ("POST", f"{BASE}/{acc['id']}/payments", body), ("POST", f"{BASE}/{acc['id']}/invoices",
                                                                   {"instalment_id": line["id"]})]  # fmt: skip
        for method, path, b in calls:
            r = api.call(method, path, b, token=tok, headers={"Idempotency-Key": key()}, if_match=acc["version"])
            assert r.status == 403 and r.code == "PERMISSION_DENIED", (role, method, path, r)


def test_founder_and_sales_manager_hold_every_capability(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    for user in (t.founder, t.manager):
        caps = t.get(acc, user=user)["capabilities"]
        assert caps["manage_schedule"] and caps["record_payment"] and caps["reverse_payment"] and caps["issue_invoice"]
        assert caps["view_audit"]
    history = t.call("GET", f"{BASE}/{acc['id']}/history").data
    assert [e["code"] for e in history][-3:] == ["SCHEDULE_CREATED", "BASELINE_RECORDED", "ACCOUNT_OPENED"]
    assert history[-1]["by"]["id"] == t.manager.id


def test_an_own_scope_holder_reaches_only_their_leads(api, factory):
    t = Commercials(api, factory)
    _, _, acc = t.opened()
    accounts = t.accounts  # commercials.view + commercials.payment.record at OWN scope; owns no lead
    assert api.get(f"{BASE}/{acc['id']}", token=t.tok(accounts)).status == 404  # not disclosed
    assert api.get(BASE, token=t.tok(accounts)).data == []
    r = api.post(f"{BASE}/{acc['id']}/payments", {"amount_minor": 1, "received_on": clock.now().date().isoformat(),
                                                  "method_code": "CASH"}, token=t.tok(accounts),
                 headers={"Idempotency-Key": key()})  # fmt: skip
    assert r.status == 404
    # the sales consultant who owns the lead can be given the codes individually, at OWN scope
    for code in ("commercials.view", "commercials.payment.record"):
        factory.grant(t.sales, code, scope="OWN")
    t.sales.token = None
    assert api.get(f"{BASE}/{acc['id']}", token=t.tok(t.sales)).status == 200
    assert t.pay(acc, 100, user=t.sales)["position"]["paid_minor"] == 100
    assert t.reverse(acc, t.get(acc)["payments"][0]["id"], user=t.sales, status=403).code == "PERMISSION_DENIED"


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                      customer_portal_enabled=True, project_commercials_enabled=False)  # fmt: skip
def test_with_the_flag_off_every_route_answers_404_before_authentication(api, factory):
    for method, path in (("GET", BASE), ("POST", BASE), ("GET", f"{BASE}/x"), ("POST", f"{BASE}/x/payments"),
                         ("GET", "/api/v1/commercial-invoices/x"), ("POST", "/api/v1/commercial-invoices/x/issue"),
                         ("GET", "/api/v1/commercial-receipts/x"), ("PATCH", f"{BASE}/x"), ("GET", f"{BASE}/")):  # fmt: skip
        r = api.call(method, path, {} if method != "GET" else None, anonymous=True)
        assert r.status == 404, (method, path, r)
    me = api.get("/api/v1/auth/me", token=Commercials(api, factory).tok(factory.user("SALES_MANAGER", mfa=True)))
    assert me.data["features"]["project_commercials"] is False


def test_unauthenticated_staff_routes_answer_401(api, factory):
    for method, path in (("GET", BASE), ("GET", f"{BASE}/00000000000070008000000000000001")):
        assert api.call(method, path, anonymous=True).status == 401


def test_no_request_schema_name_is_shared_by_two_models(app):
    """The OpenAPI document names request bodies by class name, so two classes with one name describe one route with the
    other's schema. Five such pairs predate Project Commercials (recorded in PCM-implementation-record, "Found during
    this work"); this keeps the set from growing."""
    from collections import defaultdict

    from veda.kernel import http

    seen: dict[str, set[str]] = defaultdict(set)
    for spec in http.ROUTES:
        for model in (spec.body, spec.query):
            if model is not None:
                seen[model.__name__].add(f"{model.__module__}.{model.__qualname__}")
    shared = {name for name, owners in seen.items() if len(owners) > 1}
    assert shared == {"DeleteIn", "NoteIn", "ReasonIn", "DecisionIn", "GrantIn"}
    assert not any(o.startswith("veda.modules.commercials") for n in shared for o in seen[n])
