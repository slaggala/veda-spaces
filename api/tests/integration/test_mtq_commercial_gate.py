"""MTQ B2-B4 feature gates: off by default, 404 for every commercial path (as B1's MC-3 gate), production refused."""

from __future__ import annotations

import pytest

X = "0190a3d2e5f67a8b9c0d1e2f3a4b5c6d"  # pragma: allowlist secret (a well-formed id, not a secret)
PATHS = (
    "/api/v1/mtq/scope-rules",
    f"/api/v1/requirements/{X}/decision",
    f"/api/v1/scopes/{X}",
    f"/api/v1/scope-items/{X}",
    f"/api/v1/boqs/{X}",
    f"/api/v1/boq-lines/{X}/override",
    f"/api/v1/properties/{X}/requirements",
    f"/api/v1/properties/{X}/commercial",
    f"//api/v1/scopes/{X}",
)


@pytest.mark.settings(mtq_site_enabled=True)
@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE", "PUT"])
def test_estimation_off_every_path_and_method_is_404(api, factory, method):
    founder = factory.user(founder=True)
    factory.login(api, founder)
    for path in PATHS:
        r = api.call(method, path, json={} if method != "GET" else None)
        assert r.status == 404, (method, path, r)
    me = api.get("/api/v1/auth/me").data
    assert me["features"]["mtq_estimation"] is False and me["features"]["mtq_quotation"] is False


def test_estimation_needs_the_site_flag_and_quotation_needs_estimation():
    from tests.conftest import make_settings
    from veda.config import validate_environment

    s = make_settings("sqlite://", mtq_estimation_enabled=True)
    assert any("VEDA_MTQ_ESTIMATION_ENABLED needs VEDA_MTQ_SITE_ENABLED" in p for p in validate_environment(s))
    s = make_settings("sqlite://", mtq_site_enabled=True, mtq_quotation_enabled=True)
    assert any("VEDA_MTQ_QUOTATION_ENABLED needs VEDA_MTQ_ESTIMATION_ENABLED" in p for p in validate_environment(s))


@pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True)
def test_quotation_off_every_quotation_path_is_404(api, factory):
    founder = factory.user(founder=True)
    factory.login(api, founder)
    for path in (f"/api/v1/quotations/{X}", f"/api/v1/quotations/{X}/issue", f"/api/v1/quotation-lines/{X}/trace",
                 f"/api/v1/cost-estimates/{X}/quotations", f"/api/v1/properties/{X}/quotations"):  # fmt: skip
        for method in ("GET", "POST"):
            assert api.call(method, path, json={} if method == "POST" else None).status == 404, (method, path)
    assert api.get("/api/v1/auth/me").data["features"]["mtq_quotation"] is False
