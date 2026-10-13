"""MC-3 (PR #87 review): while VEDA_MTQ_SITE_ENABLED is off, nothing of site measurement is discoverable.

Every method on every site-measurement and attachment path answers 404 (never 405), whoever asks; /auth/me reports
the feature as off for every role, so the workspace hides it even from users who hold its permissions. With the flag
on, the workspace may show it to users with the permission (the menu rule is tested in app/test/site.test.ts).
"""

from __future__ import annotations

import pytest

from veda.config import validate_environment

# The site roles load /auth/me on their own since 0204_mtq_self_service (B1-PE-08): no SALES workaround.
ROLES = [
    ((), True),
    (("ADMIN",), False),
    (("SALES",), False),
    (("SURVEYOR",), False),
    (("DESIGNER",), False),
]
GATED = [
    "/api/v1/properties",
    "/api/v1/properties/01a133f83e0b75f28dbab1b4e22da549",
    "/api/v1/properties/01a133f83e0b75f28dbab1b4e22da549/spaces",
    "/api/v1/spaces/01a133f83e0b75f28dbab1b4e22da549",
    "/api/v1/measurement-visits",
    "/api/v1/measurement-sets/01a133f83e0b75f28dbab1b4e22da549",
    "/api/v1/measurement-sets/01a133f83e0b75f28dbab1b4e22da549/sync",
    "/api/v1/mtq/templates",
    "/api/v1/attachments",
    "/api/v1/attachments/01a133f83e0b75f28dbab1b4e22da549/complete",
]
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def _user(factory, roles, founder):
    return factory.user(founder=True) if founder else factory.user(*roles)


@pytest.mark.parametrize(("role", "founder"), ROLES, ids=["FOUNDER", "ADMIN", "SALES", "SURVEYOR", "DESIGNER"])
def test_flag_off_every_role_sees_the_feature_off_and_every_method_is_404(api, factory, role, founder):
    user = _user(factory, role, founder)
    factory.login(api, user)
    me = api.get("/api/v1/auth/me")
    assert me.status == 200, me
    assert me.data["features"] == {"mtq_site": False, "mtq_estimation": False, "mtq_quotation": False}
    for path in GATED:
        for method in METHODS:
            r = api.call(method, path, {} if method in ("POST", "PUT", "PATCH") else None)
            assert r.status == 404, (role, method, path, r.status)
            assert r.json["code"] == "NOT_FOUND"


@pytest.mark.parametrize("role", ["SURVEYOR", "DESIGNER"])
def test_flag_off_bare_site_roles_get_404_on_every_method(api, factory, role):
    factory.login(api, factory.user(role))
    for path in GATED:
        for method in METHODS:
            assert api.call(method, path, {} if method in ("POST", "PUT", "PATCH") else None).status == 404, (
                method,
                path,
            )


def test_flag_off_unauthenticated_requests_are_404_too(api):
    for path in GATED:
        for method in METHODS:
            assert api.call(method, path, None, anonymous=True).status == 404, (method, path)


def test_flag_off_leaves_v1_routes_untouched(api, factory):
    factory.login(api, factory.user(founder=True))
    assert api.get("/api/v1/leads").status == 200
    assert api.call("PATCH", "/api/v1/leads", {}).status == 405  # V1 keeps its own method answers


# B1-PE-09: every spelling Werkzeug would route to a gated rule (merged slashes answer 308, other methods 405).
X = GATED[1].rsplit("/", 1)[1]  # the id the GATED paths use
VARIANTS = [
    "/api/v1//properties",
    "/api/v1///properties",
    "/api//v1/properties",
    "/api/v1/properties//",
    "/api/v1/%2Fproperties",
    "/api/v1/%2fproperties",
    "/api/v1/./properties",
    "/api/v1/x/../properties",
    f"/api/v1//properties/{X}/spaces",
    f"/api/v1//spaces/{X}",
    "/api/v1//measurement-visits",
    f"/api/v1//measurement-sets/{X}/sync",
    f"/api/v1/measurement-sets//{X}//sync",
    "/api/v1///mtq/templates",
    "/api/v1//attachments",
    f"/api/v1//attachments/{X}/complete",
]
RAW_PATHS = ["//api/v1/properties", f"//api/v1//measurement-sets/{X}/sync"]  # the test client reads // as a host


def _raw(api, method, path, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return api.client.open("/", method=method, headers=headers, environ_overrides={"PATH_INFO": path})


@pytest.mark.parametrize("anonymous", [False, True], ids=["authenticated", "anonymous"])
def test_flag_off_double_slash_and_encoded_variants_are_404(api, factory, anonymous):
    token = None if anonymous else factory.login(api, factory.user(founder=True))
    for path in VARIANTS:
        for method in METHODS:
            r = api.call(method, path, {} if method in ("POST", "PUT", "PATCH") else None, anonymous=anonymous)
            assert r.status == 404 and r.json["code"] == "NOT_FOUND", (method, path, r.status)
            assert "Location" not in r.headers, (method, path)
    for path in RAW_PATHS:
        for method in METHODS:
            r = _raw(api, method, path, token)
            assert r.status_code == 404 and "Location" not in r.headers, (method, path, r.status_code)


def test_flag_off_v1_double_slash_behaviour_is_unchanged(api, factory):
    factory.login(api, factory.user(founder=True))
    r = api.get("/api/v1//leads")
    assert r.status == 308 and r.headers["Location"].endswith("/api/v1/leads")  # Werkzeug merge_slashes, as before
    assert api.call("PUT", "/api/v1//leads", {}).status == 405
    assert api.get("/api/v1//nothing").status == 404


@pytest.mark.settings(mtq_site_enabled=True)
def test_flag_on_double_slash_routes_as_werkzeug_does(api, factory):
    factory.login(api, factory.user("SURVEYOR"))
    r = api.get("/api/v1//mtq/templates")
    assert r.status == 308 and r.headers["Location"].endswith("/api/v1/mtq/templates")


@pytest.mark.settings(mtq_site_enabled=True)
def test_flag_on_reports_the_feature_and_opens_the_routes(api, factory):
    factory.login(api, factory.user("SURVEYOR"))
    assert api.get("/api/v1/auth/me").data["features"] == {
        "mtq_site": True,
        "mtq_estimation": False,
        "mtq_quotation": False,
    }
    assert api.get("/api/v1/mtq/templates").status == 200
    assert api.call("PATCH", "/api/v1/mtq/templates", {}).status == 405  # with the flag on, normal routing applies


def test_production_refuses_the_flag(monkeypatch):
    from tests.unit.test_config_environments import deployed_env

    on = deployed_env(monkeypatch, "production", VEDA_MTQ_SITE_ENABLED="true")
    assert "VEDA_MTQ_SITE_ENABLED is not authorised in production (MTQ B1)" in validate_environment(on)
