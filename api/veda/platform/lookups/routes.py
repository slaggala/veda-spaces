"""Reference data endpoints (08 §7)."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any

import sqlalchemy as sa
from pydantic import Field

from veda.kernel.dto import Closed, Query, optional_text, text
from veda.kernel.errors import ApiError, not_found
from veda.kernel.http import Api, Req, ok

from . import service
from .models import LookupCategory, LookupValue

api = Api("lookups", "/api/v1/lookups", tags=("lookups",))


@api.route("GET", "", permission="lookup.read", write=False, requirement="PLAT-009")
def all_lookups(req: Req):
    cats = req.session.execute(sa.select(LookupCategory).order_by(LookupCategory.code)).scalars().all()
    data = [
        {
            "code": c.code,
            "name": c.name,
            "description": c.description,
            "module": c.module,
            "values": [service.present_value(v) for v in service.all_values(req.session, c.code)],
        }
        for c in cats
    ]
    result = ok(data)
    digest = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]
    result.headers["Cache-Control"] = "private, max-age=300"
    result.etag = None
    result.headers["ETag"] = f'W/"{digest}"'
    return result


class LookupQuery(Query):
    include_inactive: bool = False


@api.route("GET", "/<category_code>", permission="lookup.read", query=LookupQuery, write=False, requirement="PLAT-009")
def category_values(req: Req, category_code: str):
    if service.category(req.session, category_code) is None:
        raise not_found()
    return ok(
        [
            service.present_value(v)
            for v in service.all_values(req.session, category_code, include_inactive=req.query.include_inactive)
        ]
    )


class ValueIn(Closed):
    code: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9_]{0,49}$")]
    label: Annotated[str, text(120, min_len=1)]
    description: Annotated[str | None, optional_text(500)] = None
    sort_order: int = 100
    is_active: bool = True
    attributes: dict[str, Any] | None = None


@api.route(
    "POST", "/<category_code>/values", permission="lookup.manage", body=ValueIn, status=201, requirement="PLAT-009"
)
def create_value(req: Req, category_code: str):
    cat = service.category(req.session, category_code)
    if cat is None:
        raise not_found()
    if service.resolve_code(req.session, category_code, req.body.code, active_only=False):
        raise ApiError(409, "DUPLICATE", "This code exists in the category.")
    v = LookupValue(
        category_id=cat.id,
        code=req.body.code,
        label=req.body.label,
        description=req.body.description,
        sort_order=req.body.sort_order,
        is_active=req.body.is_active,
        attributes=req.body.attributes,
    )
    req.session.add(v)
    req.session.flush()
    return ok(service.present_value(v), status=201)


class ValuePatch(Closed):
    __immutable__ = frozenset({"code", "category_id"})
    label: Annotated[str | None, text(120, min_len=1)] = None
    description: Annotated[str | None, optional_text(500)] = None
    sort_order: int | None = None
    is_active: bool | None = None
    attributes: dict[str, Any] | None = None


@api.route(
    "PATCH",
    "/<category_code>/values/<value_id>",
    permission="lookup.manage",
    body=ValuePatch,
    if_match=True,
    requirement="PLAT-009",
)
def patch_value(req: Req, category_code: str, value_id: str):
    v = req.session.get(LookupValue, value_id)
    if v is None or not service.belongs_to(req.session, value_id, category_code):
        raise not_found()
    req.require_version(v.version)
    body = req.body
    for field in ("label", "description", "sort_order", "is_active", "attributes"):
        if field in body.provided() and (getattr(body, field) is not None or field in ("description", "attributes")):
            setattr(v, field, getattr(body, field))
    req.session.flush()
    return ok(service.present_value(v))
