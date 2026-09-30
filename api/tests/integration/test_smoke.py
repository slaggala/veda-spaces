def test_login_and_me(api, factory):
    sales = factory.user("SALES")
    factory.login(api, sales)
    r = api.get("/api/v1/auth/me")
    assert r.status == 200, r
    assert "security_event.read" not in r.data["permissions"]
    assert r.data["permissions"]["lead.read"] == "OWN"


def test_admin_login_with_mfa(api, factory):
    admin = factory.user("ADMIN")
    factory.login(api, admin)
    r = api.get("/api/v1/auth/me")
    assert r.status == 200, r
    assert r.data["permissions"]["user.role.manage"] == "ALL"
    assert r.data["suspended_permissions"] == []
