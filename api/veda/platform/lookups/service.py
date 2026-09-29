"""Lookup service interface used by modules (03 §6, PLAT-009).

Modules call ``resolve_code``/``label`` rather than querying lookup tables.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .models import LookupCategory, LookupValue


def category(s: Session, code: str) -> LookupCategory | None:
    return s.execute(sa.select(LookupCategory).where(LookupCategory.code == code)).scalar_one_or_none()


def resolve_code(s: Session, category_code: str, value_code: str | None, *, active_only: bool = True) -> LookupValue | None:
    if value_code is None:
        return None
    q = (sa.select(LookupValue).join(LookupCategory, LookupCategory.id == LookupValue.category_id)
         .where(LookupCategory.code == category_code, LookupValue.code == value_code))
    if active_only:
        q = q.where(LookupValue.is_active == sa.true())
    return s.execute(q).scalar_one_or_none()


def value_ref(s: Session, value_id: str | None) -> dict | None:
    if value_id is None:
        return None
    v = s.get(LookupValue, value_id, execution_options={"include_deleted": True})
    return {"code": v.code, "label": v.label} if v else None


def belongs_to(s: Session, value_id: str, category_code: str) -> bool:
    """Lookup-category guard (04 §2)."""
    q = (sa.select(sa.func.count()).select_from(LookupValue).join(LookupCategory, LookupCategory.id == LookupValue.category_id)
         .where(LookupValue.id == value_id, LookupCategory.code == category_code))
    return bool(s.execute(q).scalar())


def all_values(s: Session, category_code: str, *, include_inactive: bool = False) -> list[LookupValue]:
    q = (sa.select(LookupValue).join(LookupCategory, LookupCategory.id == LookupValue.category_id)
         .where(LookupCategory.code == category_code).order_by(LookupValue.sort_order, LookupValue.label))
    if not include_inactive:
        q = q.where(LookupValue.is_active == sa.true())
    return list(s.execute(q).scalars())


def present_value(v: LookupValue) -> dict:
    return {"id": v.id, "code": v.code, "label": v.label, "description": v.description, "sort_order": v.sort_order,
            "is_active": v.is_active, "attributes": v.attributes, "version": v.version}
