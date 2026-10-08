"""R3: dead-lettered outbox events are listed, retired or requeued by an operator, with a reason, never silently."""

import json

import pytest

from veda.kernel import db, outbox
from veda.kernel.context import actor, system_context
from veda.kernel.ids import new_id
from veda.platform.notifications import dead_letters
from veda.platform.notifications.models import OutboxEvent
from veda.platform.notifications.worker import outbox_stats

REASON = "invite already accepted through the link (AUT-204 I2)"


def _event(status="DEAD") -> str:
    with actor(system_context()), db.unit_of_work(write=True) as s:
        outbox.enqueue(s, "user.invited", "app_user", new_id(), token_id="secret-token-id")
        s.flush()
        ev = s.query(OutboxEvent).order_by(OutboxEvent.created_on.desc()).first()
        ev.status, ev.attempts, ev.last_error = status, 8, "ClientError fingerprint"
        return ev.id


def _get(event_id):
    with db.unit_of_work(write=False) as s:
        ev = s.get(OutboxEvent, event_id)
        return ev.status, ev.attempts, ev.last_error


def test_R3_dead_events_are_listed_without_payloads(app):
    event_id = _event()
    listed = dead_letters.list_dead()
    assert [e["id"] for e in listed] == [event_id] and listed[0]["event_type"] == "user.invited"
    assert "secret-token-id" not in json.dumps(listed) and "payload" not in listed[0]


def test_R3_retire_clears_the_dead_count_and_never_runs_again(app):
    event_id = _event()
    assert outbox_stats()["dead"] == 1
    dead_letters.retire(event_id, REASON)
    status, _, note = _get(event_id)
    assert status == "DONE" and note == f"RETIRED: {REASON}"
    assert outbox_stats()["dead"] == 0 and outbox_stats()["depth"] == 0


def test_R3_requeue_runs_again_from_the_first_attempt(app):
    event_id = _event()
    dead_letters.requeue(event_id, "SES permission fixed in PR #40")
    assert _get(event_id) == ("PENDING", 0, "REQUEUED: SES permission fixed in PR #40")
    assert outbox_stats()["dead"] == 0


@pytest.mark.parametrize("status", ["PENDING", "FAILED", "DONE"])
def test_R3_only_dead_events_can_be_retired_or_requeued(app, status):
    event_id = _event(status)
    for fn in (dead_letters.retire, dead_letters.requeue):
        with pytest.raises(dead_letters.DeadLetterError, match="not DEAD"):
            fn(event_id, REASON)
    assert _get(event_id)[0] == status


def test_R3_a_reason_is_required(app):
    event_id = _event()
    with pytest.raises(dead_letters.DeadLetterError, match="reason"):
        dead_letters.retire(event_id, "ok")
    assert _get(event_id)[0] == "DEAD"


def test_R3_cli(app, capsys):
    from veda.cli.main import main

    event_id = _event()
    assert main(["outbox", "dead"]) == 0
    assert [e["id"] for e in json.loads(capsys.readouterr().out.strip().splitlines()[-1])] == [event_id]
    assert main(["outbox", "retire", "--reason", REASON]) == 2, "--id is required"
    assert main(["outbox", "retire", "--id", "not-an-id", "--reason", REASON]) == 2
    assert main(["outbox", "retire", "--id", event_id, "--reason", REASON]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["action"] == "retired"
    assert main(["outbox", "dead"]) == 0 and json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == []
