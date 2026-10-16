"""Project Commercials money (PCM-010): integers only, every split reconciles exactly, deterministic. No database."""

from __future__ import annotations

import random
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from veda.modules.commercials import money, position
from veda.modules.commercials import vocab as V


@pytest.mark.parametrize(
    ("total", "weights", "expected"),
    [
        (100, [1, 1, 1], [34, 33, 33]),  # the remainder goes to the earliest on a tie
        (10, [3, 3, 4], [3, 3, 4]),
        (1, [5, 5], [1, 0]),
        (0, [1, 2], [0, 0]),
        (99_999_999_99, [1000, 5000, 4000], [9_999_999_99 + 1, 49_999_999_99 + 1, 39_999_999_99 - 2 + 1]),
    ],
)
def test_apportion_reconciles_exactly(total, weights, expected):
    parts = money.apportion(total, weights)
    assert parts is not None and sum(parts) == total
    if total != 99_999_999_99:
        assert parts == expected


def test_apportion_refuses_nothing_to_weigh_by():
    assert money.apportion(100, []) is None and money.apportion(100, [1, 0]) is None


def test_random_splits_always_add_up_and_are_deterministic():
    rnd = random.Random(42)
    for _ in range(500):
        total = rnd.randint(0, 10**12)
        weights = [rnd.randint(1, 10**9) for _ in range(rnd.randint(1, 24))]
        a, b = money.apportion(total, weights), money.apportion(total, list(weights))
        assert a == b and sum(a) == total and all(x >= 0 for x in a)


def test_milestone_shares_split_like_the_quotation():
    # 10 / 50 / 40 of ₹ 12,34,567.89: floors, then the paisa left over to the largest remainder
    assert money.by_shares(123_456_789, [1000, 5000, 4000]) == [12_345_679, 61_728_394, 49_382_716]
    assert sum(money.by_shares(123_456_789, [1000, 5000, 4000])) == 123_456_789
    assert money.by_shares(100, [3333, 3333, 3334]) == [33, 33, 34]
    assert money.by_shares(100, [5000, 4000]) is None  # shares must add up to 100 %


@pytest.mark.parametrize(("text", "minor"), [("0", 0), ("1", 100), ("1.5", 150), ("1,23,456.78", 12_345_678),
                                              ("0.01", 1), ("999999999999.99", 99_999_999_999_999)])  # fmt: skip
def test_rupee_strings_parse_exactly(text, minor):
    assert money.parse_rupees(text) == minor


@pytest.mark.parametrize("bad", ["", "1.234", "-1", "1e3", "abc", "01", " ", "1.", ".5", "NaN"])
def test_bad_rupee_strings_are_refused(bad):
    with pytest.raises(ValueError):
        money.parse_rupees(bad)


def test_text_matches_the_quotation_figure():
    assert money.text(12_345_678) == "123,456.78" and money.text(0) == "0.00" and money.text(None) is None


def test_payments_are_applied_in_order():
    assert position.allocate([100, 200, 300], 0) == [0, 0, 0]
    assert position.allocate([100, 200, 300], 150) == [100, 50, 0]
    assert position.allocate([100, 200, 300], 600) == [100, 200, 300]
    assert position.allocate([100, 200, 300], 900) == [100, 200, 300]  # never more than an instalment
    assert position.allocate([100], -5) == [0]


def _inst(amount=1000, requested=False, due=None):
    when = datetime(2026, 1, 1, tzinfo=UTC) if requested else None
    return SimpleNamespace(amount_minor=amount, requested_on=when, due_on=due)


@pytest.mark.parametrize(
    ("inst", "applied", "state"),
    [
        (_inst(), 1000, V.PAID),
        (_inst(requested=True, due=date(2026, 5, 1)), 1000, V.PAID),
        (_inst(requested=True, due=date(2026, 5, 1)), 0, V.OVERDUE),
        (_inst(requested=True, due=date(2026, 5, 1)), 400, V.OVERDUE),
        (_inst(), 400, V.PARTIALLY_PAID),
        (_inst(requested=True), 0, V.DUE),
        (_inst(requested=True, due=date(2026, 7, 1)), 0, V.DUE),
        (_inst(), 0, V.UPCOMING),
    ],
)
def test_instalment_state_follows_the_facts(inst, applied, state):
    assert position.state(inst, applied, date(2026, 6, 1)) == state
