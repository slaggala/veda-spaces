"""Business number sequences (03 §6.3, PLAT-010).

Allocation is a single ``UPDATE … RETURNING`` inside the business transaction,
so concurrent allocations serialize on the row. Values are internal staff
display numbers: never API identifiers, never public (ADR-002).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.context import require_actor


def _period(reset_period: str, zone_now) -> str | None:
    if reset_period == "YEAR":
        return f"{zone_now.year:04d}"
    if reset_period == "MONTH":
        return f"{zone_now.year:04d}{zone_now.month:02d}"
    return None


def next_number(session: Session, key: str, *, timezone: str = "Asia/Kolkata") -> str:
    from zoneinfo import ZoneInfo

    from veda.platform.lookups.models import NumberSequence as NS

    now = db.tx_time(session)
    actor_id = require_actor().actor_id
    row = session.execute(sa.select(NS.reset_period).where(NS.sequence_key == key)).first()
    if row is None:
        raise RuntimeError(f"number sequence {key} is not seeded")
    period = _period(row.reset_period, now.astimezone(ZoneInfo(timezone)))
    # Period rollover and allocation in one statement per case; RETURNING gives the allocated value.
    table = NS.__table__
    stmt = (
        sa.update(table)
        .where(table.c.sequence_key == key, table.c.is_deleted == sa.false())
        .values(
            next_value=sa.case((table.c.current_period.is_distinct_from(period), 2), else_=table.c.next_value + 1),
            current_period=period,
            updated_on=now,
            updated_by=actor_id,
            version=table.c.version + 1,
        )
        .returning((table.c.next_value - 1).label("allocated"), table.c.prefix, table.c.padding)
    )
    # RETURNING yields post-update values, so the allocated number is next_value - 1.
    allocated, prefix, padding = session.execute(stmt, execution_options={"synchronize_session": False}).one()
    number = f"{allocated:0{padding}d}"
    return f"{prefix}{period}-{number}" if period else f"{prefix}{number}"
