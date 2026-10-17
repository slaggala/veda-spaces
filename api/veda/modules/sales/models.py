"""Sales & Customer Acquisition tables (SCA, migration 0215): the site's anonymous funnel counts.

One table, which names no person, page, address or device: ``acquisition_event_daily`` holds one count per day,
event and acquisition channel. De-duplication of a browser session's repeated beacons happens in memory
(``analytics``), as the platform's idempotency store does, so nothing per session is ever written.

Everything else the sales layer shows is read from the records of the lead, estimator, MTQ, proposal and project
modules; it keeps no copy.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from veda.kernel.base import AuditedBase, in_check, live_where

from .vocab import CHANNELS, EVENTS


class AcquisitionEventDaily(AuditedBase):
    __tablename__ = "acquisition_event_daily"

    day: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # YYYY-MM-DD, India business day
    event: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(20), nullable=False)
    count: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    __table_args__ = (
        in_check("acquisition_event_daily", "event", EVENTS),
        in_check("acquisition_event_daily", "channel", CHANNELS),
        CheckConstraint("count >= 0", name="ck_acquisition_event_daily__count"),
        Index("ux_acquisition_event_daily__key", "day", "event", "channel", unique=True, **live_where()),
    )
