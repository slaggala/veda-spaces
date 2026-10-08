# Post-validation hardening C2: VERSION_CONFLICT always carries current_version (R8)

**Scope:** follow-up R8 (found on PR #41: `test_TD_F_two_writer_conflict[postgresql]` failed once). Application
change only.

## 1. Problem

Two staff edit the same lead at the same moment with the same `If-Match` version N:
1. Both requests read the lead at version N and pass `check_version`.
2. On PostgreSQL (READ COMMITTED), the first commits version N+1.
3. The second's `UPDATE … WHERE version = N` matches no row, and SQLAlchemy raises `StaleDataError`.
4. That maps to `409 VERSION_CONFLICT` **without** `current_version`, `updated_by` or `updated_on`
   (`kernel/http.py`, `_map_db_error`).

A client that relies on `current_version` to offer "reload and retry" cannot recover. SQLite is unaffected: it
serializes writers.

The race is rare (0 failures in 15 local runs) but real (CI on PR #41).

## 2. Change

`modules/crm/leads/service.py` `check_version` (used by every lead write with `If-Match`) first locks the row and
reloads its committed state (`session.refresh(lead, with_for_update=True)`). A concurrent writer now waits for the
first transaction, then sees N+1 and gets the ordinary 409 with `current_version`, `updated_by` and `updated_on`.

- Only when `If-Match` is present: without it the request is already refused with 428.
- No route modifies the lead before `check_version` (checked for all eight call sites), so the refresh discards
  nothing.
- The lock is held only for the rest of that write transaction. On SQLite `FOR UPDATE` is not emitted; behaviour is
  unchanged.
- `_map_db_error` keeps mapping `StaleDataError` to 409, as a backstop for any other versioned writer.

## 3. Tests

| Test | Proves | Fails without the change |
|---|---|---|
| `test_R8_a_writer_that_loses_the_race_always_learns_the_current_version` (new, deterministic) | Writer A pauses after its check; B sends the same edit meanwhile; A gets 200; B gets 409 `VERSION_CONFLICT` with `current_version` equal to A's new version | **Yes on PostgreSQL:** A got the bare 409 ("changed by someone else"), as in CI |
| `test_TD_F_two_writer_conflict` (existing) | Unchanged, now deterministic in outcome | — |

## 4. Validation

- Full API suite on SQLite and PostgreSQL: pass. Ruff, format, mypy ratchet (157 = baseline): pass.
- The new test, run before the fix: fails on PostgreSQL, passes on SQLite (as expected).

## 5. Residual risk

- Row locks extend a writer's wait by the length of a concurrent write transaction (milliseconds). No lock is taken
  for reads.
- Other versioned entities that do not use this helper still return the backstop 409 without `current_version` on a
  database-level conflict. Today only leads use `If-Match`.
