"""Canonical customer-copy closure, Phase 8 (server side): the Cloudflare siteverify path for V3 estimates.

Cloudflare is simulated: `urlopen` is replaced by a fake siteverify that answers as Cloudflare does, so no network
call is made and no real secret is used. Each case below is refused with `422 CAPTCHA_FAILED`, and nothing is
created:
- a rejected token;
- a used token (`timeout-or-duplicate`);
- a token solved for another hostname;
- an unreachable siteverify;
- an empty or oversized token.

A token is single-use, and a replay with its own idempotency key is answered before the check."""

import io
import json

import pytest
import sqlalchemy as sa

from tests.integration.test_catalog import SITE, approve_all, living, new_key, release, seed_slice
from tests.support.dbh import rows
from veda.kernel import turnstile
from veda.modules.estimator.models import BudgetEstimate

pytestmark = pytest.mark.settings(catalog_estimator_enabled=True, catalog_admin_enabled=True,
                                  estimate_turnstile_required=True, turnstile_mode="cloudflare",
                                  turnstile_secret="test-only-not-a-secret")  # fmt: skip  # pragma: allowlist secret


@pytest.fixture
def people(factory):
    return factory.user("FOUNDER").id, factory.user("FOUNDER").id


class FakeSiteverify:
    """Cloudflare's siteverify, simulated: each token verifies once, for our own hostname."""

    def __init__(self):
        self.seen: list[str] = []
        self.used: set[str] = set()
        self.hostname = "localhost"
        self.down = False

    def __call__(self, url, data=None, timeout=None):
        assert url == turnstile.SITEVERIFY_URL and timeout
        if self.down:
            raise OSError("siteverify unreachable")
        form = dict(p.split("=", 1) for p in data.decode().split("&"))
        token = form["response"]
        self.seen.append(token)
        if token.startswith("bad"):
            answer = {"success": False, "error-codes": ["invalid-input-response"]}
        elif token in self.used:
            answer = {"success": False, "error-codes": ["timeout-or-duplicate"]}
        else:
            self.used.add(token)
            answer = {"success": True, "hostname": self.hostname, "action": "estimate"}
        return io.BytesIO(json.dumps(answer).encode())


@pytest.fixture
def siteverify(monkeypatch):
    fake = FakeSiteverify()
    monkeypatch.setattr(turnstile.urllib.request, "urlopen", fake)
    return fake


def live(people):
    a, b = people
    seed_slice(a)
    approve_all(a, b)
    release(a, b)


def post(api, token, key=None):
    return api.post("/api/v1/public/catalog/estimates", {"configuration": living(), "turnstile_token": token},
                    anonymous=True, headers={"Origin": SITE, "Idempotency-Key": key or new_key()})  # fmt: skip


def refused(r):
    return r.status == 422 and r.json["code"] == "CAPTCHA_FAILED"


def test_a_verified_token_is_accepted_once(api, people, siteverify):
    live(people)
    assert post(api, "tok-good-1").status == 201
    assert refused(post(api, "tok-good-1")), "a used token is refused by Cloudflare (timeout-or-duplicate)"
    assert len(rows(sa.select(BudgetEstimate))) == 1


def test_a_replay_of_an_answered_request_does_not_spend_a_token(api, people, siteverify):
    live(people)
    key = new_key()
    assert post(api, "tok-good-2", key).status == 201
    replay = post(api, "tok-good-2", key)
    assert replay.status == 201 and replay.headers.get("Idempotent-Replayed") == "true"
    assert siteverify.seen == ["tok-good-2"], "the replay is answered before siteverify"


@pytest.mark.parametrize("token", ["bad-token", ""])
def test_rejected_and_empty_tokens_are_refused(api, people, siteverify, token):
    live(people)
    assert refused(post(api, token))
    assert not rows(sa.select(BudgetEstimate))
    if not token:
        assert siteverify.seen == [], "an empty token is refused without calling Cloudflare"


def test_a_token_for_another_hostname_is_refused(api, people, siteverify):
    live(people)
    siteverify.hostname = "attacker.example"
    assert refused(post(api, "tok-elsewhere"))
    assert not rows(sa.select(BudgetEstimate))


def test_an_unreachable_siteverify_fails_closed(api, people, siteverify):
    live(people)
    siteverify.down = True
    assert refused(post(api, "tok-good-3"))
    assert not rows(sa.select(BudgetEstimate))


def test_an_oversized_token_is_refused_without_calling_cloudflare(api, people, siteverify):
    live(people)
    r = post(api, "t" * 2049)
    assert r.status == 422 and siteverify.seen == []
