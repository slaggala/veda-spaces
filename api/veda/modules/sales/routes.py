"""Sales & Customer Acquisition endpoints (SCA). Every route answers 404, before authentication, unless
VEDA_SALES_EXPERIENCE_ENABLED is on (off by default; production refuses it).

Staff routes are read-only projections over records other modules own (``pipeline``, ``funnel``, ``demo``); the one
public route counts the site's anonymous funnel beacons (RBX-011). Nothing here writes a lead, a quotation or a
customer row.
"""

from __future__ import annotations

from datetime import timedelta

import sqlalchemy as sa

from veda.kernel import clock
from veda.kernel.errors import ApiError, field_error, not_found, validation_failed
from veda.kernel.http import Api, Req, no_content, ok, problem_response, request_reaches
from veda.modules.crm.leads.models import Lead

from . import access, analytics, demo, funnel, pipeline
from . import schemas as S

api = Api("sales", "/api/v1/sales", tags=("sales",))
public_api = Api("sales_public", "/api/v1/public", tags=("sales",))
GATED_PREFIXES = ("/api/v1/sales", "/api/v1/public/acquisition")
FUNNEL_MAX_DAYS = 366


@api.blueprint.before_app_request
def _enabled():
    if not access.enabled() and request_reaches(("sales", "sales_public"), GATED_PREFIXES):
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


def _private(result):
    result.headers["Cache-Control"] = "no-store"
    return result


def _ip(prefix: str):
    def key():
        from veda.kernel.ratelimit import ip_key

        return f"{prefix}:ip:" + ip_key()

    return key


# --- staff -------------------------------------------------------------------------------------------------------------
@api.route("GET", "/pipeline", permission="sales.pipeline.view", write=False, query=S.PipelineQuery, requirement="SCA-006",
           summary="The sales pipeline: live leads with their evidence-derived stage, facts, follow-up state and channel")  # fmt: skip
def get_pipeline(req: Req):
    rows, meta = pipeline.listing(req.session, req.ctx, req.query, now=clock.now())
    return _private(ok(rows, meta=meta))


@api.route("GET", "/leads/<lead_id>/progression", permission="sales.pipeline.view", write=False, requirement="SCA-006",
           summary="One lead's derived sales progression and the records behind it")  # fmt: skip
def get_progression(req: Req, lead_id: str):
    lead = req.session.execute(
        sa.select(Lead).where(Lead.id == lead_id, access.pipeline_predicate(req.ctx))
    ).scalar_one_or_none()
    if lead is None:
        raise not_found()
    return _private(ok(pipeline.one(req.session, req.ctx, lead, now=clock.now())))


@api.route("GET", "/funnel", permission="sales.funnel.view", write=False, query=S.FunnelQuery, requirement="SCA-007",
           summary="The acquisition funnel over a period: counts per stage with their basis, channels, lost reasons")  # fmt: skip
def get_funnel(req: Req):
    now = clock.now()
    today = analytics.business_day()
    day_to = req.query.date_to or today
    day_from = req.query.date_from or (day_to - timedelta(days=29))
    if day_from > day_to:
        raise validation_failed([field_error("from", "OUT_OF_RANGE", "The start is after the end.")])
    if (day_to - day_from).days >= FUNNEL_MAX_DAYS:
        raise validation_failed([field_error("to", "OUT_OF_RANGE", "At most one year at a time.")])
    return _private(ok(funnel.report(req.session, day_from, day_to, now=now)))


@api.route("GET", "/demo", permission="sales.demo.view", write=False, requirement="SCA-009",
           summary="The customer-journey demo: a synthetic proposal and project-portal model (no customer data)")  # fmt: skip
def get_demo(req: Req):
    return _private(ok(demo.model(analytics.business_day())))


# --- public (RBX-011) ---------------------------------------------------------------------------------------------------
@public_api.route("POST", "/acquisition/events", rbx="RBX-011", auth="public", body=S.PublicEventIn, status=204,
                  max_body=1024, requirement="SCA-008",
                  limits=[("60 per minute", _ip("acquisition-events")), ("600 per hour", _ip("acquisition-events"))],
                  summary="An anonymous funnel beacon: counted once per browser session, event and day (no person)")  # fmt: skip
def public_event(req: Req):
    analytics.record(req.session, req.body)
    return no_content()
