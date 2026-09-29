"""FC-04: a unit of work never stamps updated_on before created_on (ck_*__updated_after_created, DATA-003/DATA-005).

Two defences: the clock is read after the connection (and on SQLite the write lock) is acquired, and an update of
a row created by a later-clocked transaction is stamped no earlier than the row's creation.
"""

import threading
from datetime import timedelta

import sqlalchemy as sa
from sqlalchemy import event

from tests.support.dbh import get
from veda.kernel import clock, db
from veda.kernel.context import actor, system_context
from veda.platform.auth import service as auth_service
from veda.platform.auth.models import UserActionToken
from veda.platform.identity.models import User


def test_FC04_clock_is_read_after_the_connection_begins(api, monkeypatch):
    order = []
    engine = db.engine()

    def on_begin(conn):
        order.append("begin")

    real_now = clock.now

    def now():
        order.append("clock")
        return real_now()

    event.listen(engine, "begin", on_begin)
    monkeypatch.setattr(db.clock, "now", now)
    try:
        session = db.new_session(write=True)
        session.rollback()
        session.close()
    finally:
        event.remove(engine, "begin", on_begin)
    assert order.index("begin") < order.index("clock"), order


def test_FC04_update_of_a_row_created_by_a_later_clocked_transaction(api, factory):
    """The PostgreSQL interleaving (earlier clock reading, later row) made deterministic on both engines: the row is
    created and committed first, then updated by a unit whose clock reading is earlier than the row's creation."""
    user = factory.user("SALES")
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as other:
        tok, _ = auth_service.create_action_token(
            other, other.get(User, user.id), "PASSWORD_RESET", ttl=timedelta(minutes=30)
        )
        other.flush()
        tok_id, created = tok.id, tok.created_on
    with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
        s.info["tx_time"] = created - timedelta(seconds=5)  # read before the other transaction committed
        row = s.get(UserActionToken, tok_id)
        row.invalidated_on = db.tx_time(s)
    saved = get(UserActionToken, tok_id)
    assert saved.updated_on >= saved.created_on and saved.invalidated_on is not None


def test_FC04_concurrent_create_and_invalidate_never_violates_the_constraint(app, factory):
    user = factory.user("SALES")
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def creator():
        barrier.wait()
        for _ in range(25):
            try:
                with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
                    auth_service.create_action_token(
                        s, s.get(User, user.id), "PASSWORD_RESET", ttl=timedelta(minutes=30)
                    )
            except sa.exc.OperationalError:
                pass  # busy / serialization: retried by callers, never a partial write
            except BaseException as exc:  # noqa: BLE001 - collected for the assertion
                errors.append(exc)

    def invalidator():
        barrier.wait()
        for _ in range(25):
            try:
                with actor(system_context("SYSTEM_JOB")), db.unit_of_work(write=True) as s:
                    auth_service.invalidate_action_tokens(s, user.id, ("PASSWORD_RESET",))
            except sa.exc.OperationalError:
                pass
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

    threads = [threading.Thread(target=creator), threading.Thread(target=invalidator)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not [e for e in errors if isinstance(e, sa.exc.IntegrityError)], errors
    assert not errors, errors
    with db.unit_of_work(write=False) as s:
        bad = s.execute(
            sa.select(sa.func.count())
            .select_from(UserActionToken)
            .where(UserActionToken.updated_on < UserActionToken.created_on)
        ).scalar()
    assert bad == 0
