"""Customer Project Portal concurrency (review): one sign-in link redeemed twice at once yields exactly one session,
on SQLite and PostgreSQL, through the paused-request harness (no fixed waits). SYNTHETIC data only."""

from __future__ import annotations

import sqlalchemy as sa

from tests.support import dbh
from tests.support.portal import ON, PUBLIC, Portal
from tests.support.project import race
from veda.modules.portal import identity
from veda.modules.portal.models import PortalSession

pytestmark = ON


def test_a_link_redeemed_twice_at_once_opens_exactly_one_session(api, app, factory, monkeypatch):
    t = Portal(api, factory)
    prop, _, _ = t.issued()
    t.grant(prop["lead_id"], "race@example.test")
    token = t.link_token("race@example.test")
    redeem = lambda c: c.post(f"{PUBLIC}/session", {"token": token}, anonymous=True)  # noqa: E731
    from tests.support.api import ApiClient

    other = ApiClient(app.test_client())
    first, second = race(app, monkeypatch, "", redeem, lambda: redeem(other), module=identity, name="active_access")
    assert sorted((first.status, second.status)) == [201, 400]
    assert (first if first.status == 400 else second).code == "PORTAL_LINK_INVALID"
    assert len(dbh.rows(sa.select(PortalSession))) == 1
