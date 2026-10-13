"""MTQ B1 endpoints (blueprint §11.1, the B1 subset). Staff only, bearer-authenticated, scoped by lead.

Every route answers 404, before authentication, unless VEDA_MTQ_SITE_ENABLED is on (off by default; production
refuses it). There is no public route and nothing here returns a price.
"""

from __future__ import annotations

import sqlalchemy as sa

from veda.config import settings
from veda.kernel.errors import ApiError
from veda.kernel.http import Api, Req, no_content, offset_meta, ok, problem_response
from veda.kernel.ids import is_valid_id
from veda.kernel.ratelimit import ip_key

from . import (
    bindings,  # noqa: F401  (registers the attachment bindings)
    electrical,  # noqa: F401  (electrical points: hooks, checks, binding)
    geometry,  # noqa: F401  (L-shape and staircase checks)
    scope,
    sets,
    sync,
    templates,
    verification,
    visits,
)
from . import capture as C
from . import properties as P
from . import schemas as S
from . import sync_schemas as SY
from .models import MeasurementNote, MeasurementSet, MeasurementVisit, Property

api = Api("mtq", "/api/v1", tags=("mtq",))
CAPTURE_LIMITS = [("600 per minute", ip_key)]


@api.blueprint.before_request
def _site_enabled():
    if not settings().mtq_site_enabled:
        return problem_response(ApiError(404, "NOT_FOUND", "Not found."))
    return None


# --- templates ---------------------------------------------------------------------------------------------------------
@api.route("GET", "/mtq/templates", permission="property.read", write=False, requirement="PROP-004",
           summary="The B1 property and space templates (version 2026.10.1)")  # fmt: skip
def get_templates(req: Req):
    return ok(templates.public_view())


# --- properties --------------------------------------------------------------------------------------------------------
@api.route("GET", "/properties", permission="property.read", query=S.PropertyListQuery, write=False,
           requirement="PROP-001", summary="List properties within scope")  # fmt: skip
def list_properties(req: Req):
    q = req.query
    stmt = sa.select(Property).where(scope.condition(req.ctx, "property.read", Property.lead_id))
    if q.lead_id:
        stmt = stmt.where(Property.lead_id == q.lead_id)
    if q.city:
        stmt = stmt.where(sa.func.lower(Property.city) == q.city.lower())
    if q.property_type_code:
        stmt = stmt.where(Property.property_type_code == q.property_type_code)
    total = req.session.execute(sa.select(sa.func.count()).select_from(stmt.subquery())).scalar()
    rows = (
        req.session.execute(
            stmt.order_by(Property.created_on.desc(), Property.id).offset((q.page - 1) * q.page_size).limit(q.page_size)
        )
        .scalars()
        .all()
    )
    meta, links = offset_meta(
        q.page, q.page_size, int(total or 0), "/api/v1/properties", q.model_dump(exclude_none=True)
    )
    return ok([P.present(req.session, p, with_spaces=False) for p in rows], meta=meta, links=links)


@api.route("POST", "/properties", permission="property.create", body=S.PropertyCreateIn, status=201,
           idempotent_create=True, requirement="PROP-002",
           summary="Create a property for a lead, optionally seeding its space tree from a template")  # fmt: skip
def create_property(req: Req):
    prop = P.create(req.session, req.ctx, req.body)
    req.session.flush()
    return ok(P.present(req.session, prop), status=201)


@api.route("GET", "/properties/<property_id>", permission="property.read", write=False, requirement="PROP-001",
           summary="One property with its space tree and derived counts")  # fmt: skip
def get_property(req: Req, property_id: str):
    return ok(P.present(req.session, P.get_visible(req.session, req.ctx, property_id)))


@api.route("PATCH", "/properties/<property_id>", permission="property.update", body=S.PropertyPatchIn,
           if_match=True, requirement="PROP-003", summary="Edit a property")  # fmt: skip
def patch_property(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id)
    req.require_version(prop.version)
    P.update(req.session, req.ctx, prop, req.body)
    req.session.flush()
    return ok(P.present(req.session, prop))


@api.route("GET", "/properties/<property_id>/summary", permission="property.read", write=False,
           requirement="PROP-001", summary="Derived counts and the latest verified measurement set")  # fmt: skip
def property_summary(req: Req, property_id: str):
    data = P.present(req.session, P.get_visible(req.session, req.ctx, property_id), with_spaces=False)
    keys = ("id", "property_number", "display_label", "derived_bedroom_count", "derived_toilet_count",
            "derived_level_count", "derived_measured_floor_area_sqft_centi", "latest_verified_set", "version")  # fmt: skip
    return ok({k: data[k] for k in keys})


# --- spaces ------------------------------------------------------------------------------------------------------------
@api.route("GET", "/properties/<property_id>/spaces", permission="property.read", write=False,
           requirement="PROP-001", summary="The live space tree in walk order")  # fmt: skip
def list_spaces(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id)
    return ok([P.present_space(sp) for sp in P.live_spaces(req.session, prop.id)])


@api.route("POST", "/properties/<property_id>/spaces", permission="property.update", body=S.SpaceCreateIn,
           status=201, requirement="PROP-003", summary="Add a space to a property's tree")  # fmt: skip
def create_space(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id)
    scope.require_in_scope(req.session, req.ctx, prop.lead_id, "property.update")
    b = req.body
    sp = P.add_space(
        req.session,
        prop,
        space_type_code=b.space_type_code,
        label=b.label,
        custom_type_label=b.custom_type_label,
        parent_space_id=b.parent_space_id,
        level_index=b.level_index,
        zone_code=b.zone_code,
        sort_order=b.sort_order,
        is_in_scope=b.is_in_scope,
        attributes=b.attributes.model_dump(exclude_none=True),
    )
    P.derive(req.session, prop)
    req.session.flush()
    return ok(P.present_space(sp), status=201)


@api.route("POST", "/properties/<property_id>/spaces/from-template", permission="property.update",
           body=S.SpacesFromTemplateIn, status=201, requirement="PROP-004",
           summary="Seed an empty property's space tree from a template")  # fmt: skip
def spaces_from_template(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id)
    scope.require_in_scope(req.session, req.ctx, prop.lead_id, "property.update")
    P.seed_from_template(req.session, prop, req.body.template_key, list(req.body.include_optional))
    req.session.flush()
    return ok(P.present(req.session, prop), status=201)


@api.route("PUT", "/properties/<property_id>/spaces/order", permission="property.update", body=S.SpaceOrderIn,
           requirement="PROP-003",
           summary="Set the walk order: the list must name every live space exactly once (stale lists are refused)")  # fmt: skip
def order_spaces(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id)
    rows = P.reorder(req.session, req.ctx, prop, list(req.body.space_ids))
    req.session.flush()
    return ok([P.present_space(sp) for sp in rows])


@api.route("PATCH", "/spaces/<space_id>", permission="property.update", body=S.SpacePatchIn, if_match=True,
           requirement="PROP-003", summary="Edit a space (its type and id never change)")  # fmt: skip
def patch_space(req: Req, space_id: str):
    sp, prop = P.get_space(req.session, req.ctx, space_id)
    req.require_version(sp.version)
    P.update_space(req.session, req.ctx, sp, prop, req.body)
    req.session.flush()
    return ok(P.present_space(sp))


@api.route("DELETE", "/spaces/<space_id>", permission="property.update", body=S.SpaceDeleteIn, if_match=True,
           requirement="PROP-003", summary="Archive a space (soft delete; its id is kept)")  # fmt: skip
def delete_space(req: Req, space_id: str):
    sp, prop = P.get_space(req.session, req.ctx, space_id)
    req.require_version(sp.version)
    from veda.kernel.context import reason

    with reason(req.body.reason if req.body else None):
        P.archive_space(req.session, req.ctx, sp, prop)
        req.session.flush()
    return no_content()


# --- measurement visits (B1-T05) ---------------------------------------------------------------------------------------
@api.route("GET", "/measurement-visits", permission="measurement.visit.read", query=S.VisitListQuery, write=False,
           requirement="MEAS-001", summary="List measurement visits within scope")  # fmt: skip
def list_visits(req: Req):
    q = req.query
    stmt = sa.select(MeasurementVisit).where(
        scope.condition(req.ctx, "measurement.visit.read", MeasurementVisit.lead_id)
    )
    if q.property_id:
        stmt = stmt.where(MeasurementVisit.property_id == q.property_id)
    if q.lead_id:
        stmt = stmt.where(MeasurementVisit.lead_id == q.lead_id)
    if q.status:
        stmt = stmt.where(MeasurementVisit.status.in_([x for x in q.status.split(",") if x]))
    if q.assigned_to:
        target = req.ctx.user.id if q.assigned_to == "me" else q.assigned_to
        if target != req.ctx.user.id and not is_valid_id(target):
            raise ApiError(422, "INVALID_ID", "assigned_to must be me or a user id.")
        stmt = stmt.where(MeasurementVisit.assigned_to == target)
    total = req.session.execute(sa.select(sa.func.count()).select_from(stmt.subquery())).scalar()
    rows = (
        req.session.execute(
            stmt.order_by(MeasurementVisit.scheduled_start_on.desc(), MeasurementVisit.id)
            .offset((q.page - 1) * q.page_size)
            .limit(q.page_size)
        )
        .scalars()
        .all()
    )
    meta, links = offset_meta(q.page, q.page_size, int(total or 0), "/api/v1/measurement-visits",
                              q.model_dump(exclude_none=True))  # fmt: skip
    return ok([visits.present(req.session, req.ctx, v) for v in rows], meta=meta, links=links)


@api.route("POST", "/measurement-visits", permission="measurement.visit.create", body=S.VisitCreateIn, status=201,
           idempotent_create=True, requirement="MEAS-002",
           summary="Request a visit; with a start and a surveyor it is scheduled at once")  # fmt: skip
def create_visit(req: Req):
    visit = visits.create(req.session, req.ctx, req.body)
    req.session.flush()
    return ok(visits.present(req.session, req.ctx, visit), status=201)


@api.route("GET", "/measurement-visits/<visit_id>", permission="measurement.visit.read", write=False,
           requirement="MEAS-001", summary="One measurement visit")  # fmt: skip
def get_visit(req: Req, visit_id: str):
    return ok(visits.present(req.session, req.ctx, visits.get_visible(req.session, req.ctx, visit_id)))


@api.route("PATCH", "/measurement-visits/<visit_id>", permission="measurement.visit.schedule", body=S.VisitPatchIn,
           if_match=True, requirement="MEAS-003", summary="Edit a visit's contact and access details")  # fmt: skip
def patch_visit(req: Req, visit_id: str):
    visit = visits.get_visible(req.session, req.ctx, visit_id)
    req.require_version(visit.version)
    visits.update(req.session, req.ctx, visit, req.body)
    req.session.flush()
    return ok(visits.present(req.session, req.ctx, visit))


@api.route("POST", "/measurement-visits/<visit_id>/status", any_of=("measurement.visit.schedule", "measurement.capture"),
           body=S.VisitStatusIn, if_match=True, idempotent_create=True, requirement="MEAS-003",
           summary="Move a visit through its state machine (schedule, reschedule, start, complete, cancel, no-show)")  # fmt: skip
def visit_status(req: Req, visit_id: str):
    visit = visits.get_visible(req.session, req.ctx, visit_id)
    req.require_version(visit.version)
    visits.transition(req.session, req.ctx, visit, req.body)
    req.session.flush()
    return ok(visits.present(req.session, req.ctx, visit))


# --- measurement sets (B1-T06) -----------------------------------------------------------------------------------------
@api.route("POST", "/measurement-visits/<visit_id>/measurement-sets", permission="measurement.capture",
           body=C.SetCreateIn, status=201, idempotent_create=True, requirement="MEAS-004",
           summary="Open the draft revision for a visit in progress (optionally copied from an earlier revision)")  # fmt: skip
def create_set(req: Req, visit_id: str):
    visit = visits.get_visible(req.session, req.ctx, visit_id, "measurement.capture")
    mset = sets.create_for_visit(req.session, req.ctx, visit, req.body)
    req.session.flush()
    return ok(sets.present(req.session, mset), status=201)


@api.route("POST", "/properties/<property_id>/measurement-sets", permission="measurement.capture",
           body=C.PlanSetCreateIn, status=201, idempotent_create=True, requirement="MEAS-004",
           summary="Key in a plan-drawing pre-measure (Lite, no visit)")  # fmt: skip
def create_plan_set(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id, "measurement.capture")
    mset = sets.create_from_plan(req.session, req.ctx, prop, req.body)
    req.session.flush()
    return ok(sets.present(req.session, mset), status=201)


@api.route("GET", "/properties/<property_id>/measurement-sets", permission="measurement.read", write=False,
           requirement="MEAS-005", summary="Every revision of a property's measurements")  # fmt: skip
def list_sets(req: Req, property_id: str):
    prop = P.get_visible(req.session, req.ctx, property_id, "measurement.read")
    rows = req.session.execute(
        sa.select(MeasurementSet).where(MeasurementSet.property_id == prop.id).order_by(MeasurementSet.revision_no)
    ).scalars()
    return ok([sets.present(req.session, m, full=False) for m in rows])


@api.route("GET", "/measurement-sets/<set_id>", permission="measurement.read", write=False, requirement="MEAS-005",
           summary="One revision with its full tree (spaces, walls, openings, notes)")  # fmt: skip
def get_set(req: Req, set_id: str):
    mset, _ = sets.get_visible(req.session, req.ctx, set_id)
    return ok(sets.present(req.session, mset))


@api.route("PATCH", "/measurement-sets/<set_id>", permission="measurement.capture", body=C.SetPatchIn,
           if_match=True, requirement="MEAS-004", summary="Property-level capture and the entry unit of a draft")  # fmt: skip
def patch_set(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    req.require_version(mset.version)
    sets.update_set(req.session, req.ctx, mset, prop, req.body)
    req.session.flush()
    return ok(sets.present(req.session, mset, full=False))


@api.route("PUT", "/measurement-sets/<set_id>/spaces/<space_id>", permission="measurement.capture",
           body=C.SpaceCaptureIn, max_body=512 * 1024, limits=CAPTURE_LIMITS, requirement="MEAS-004",
           summary="Write one space: measurement, walls, openings (base_version required once it exists)")  # fmt: skip
def put_space(req: Req, set_id: str, space_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    sm, created = sets.upsert_space(req.session, req.ctx, mset, prop, space_id, req.body)
    req.session.flush()
    return ok(sets.present_measurement(req.session, sm), status=201 if created else 200)


@api.route("POST", "/measurement-sets/<set_id>/spaces/<space_id>/release", permission="measurement.capture",
           requirement="MEAS-004", summary="Release your claim on a space so another surveyor can take it over")  # fmt: skip
def release_space(req: Req, set_id: str, space_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    sm = sets.release_claim(req.session, req.ctx, mset, prop, space_id)
    req.session.flush()
    return ok(sets.present_measurement(req.session, sm))


@api.route("POST", "/measurement-sets/<set_id>/notes", permission="measurement.capture", body=C.MeasurementNoteIn, status=201,
           requirement="MEAS-004", summary="Add a note (idempotent per client_ref)")  # fmt: skip
def add_note(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    note, created = sets.add_note(req.session, req.ctx, mset, prop, req.body)
    req.session.flush()
    data = {"id": note.id, "version": note.version, "client_ref": note.client_ref, "space_id": note.space_id,
            "note_type_code": note.note_type_code, "body": note.body}  # fmt: skip
    return ok(data, status=201 if created else 200)


@api.route("DELETE", "/measurement-sets/<set_id>/notes/<note_id>", permission="measurement.capture", if_match=True,
           requirement="MEAS-004", summary="Delete a note from a draft")  # fmt: skip
def delete_note(req: Req, set_id: str, note_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    note = req.session.get(MeasurementNote, note_id)
    if note is None or note.is_deleted or note.measurement_set_id != mset.id:
        raise ApiError(404, "NOT_FOUND", "Not found.")
    req.require_version(note.version)
    sets.delete_note(req.session, req.ctx, mset, prop, note)
    req.session.flush()
    return no_content()


@api.route("POST", "/measurement-sets/<set_id>/submit", permission="measurement.capture", if_match=True,
           idempotent_create=True, requirement="MEAS-004",
           summary="Submit the draft (lead surveyor); it becomes immutable")  # fmt: skip
def submit_set(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    req.require_version(mset.version)
    sets.submit(req.session, req.ctx, mset, prop)
    req.session.flush()
    return ok(sets.present(req.session, mset, full=False))


@api.route("POST", "/measurement-sets/<set_id>/reject", permission="measurement.verify", body=C.RejectIn,
           if_match=True, idempotent_create=True, requirement="MEAS-006",
           summary="Return a submitted revision for correction; a new draft revision is opened from it")  # fmt: skip
def reject_set(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.verify")
    req.require_version(mset.version)
    correction = sets.reject(req.session, req.ctx, mset, prop, req.body.reason)
    req.session.flush()
    return ok({"rejected": sets.present(req.session, mset, full=False),
               "correction": sets.present(req.session, correction, full=False)})  # fmt: skip


@api.route("GET", "/measurement-sets/<set_id>/diff/<other_id>", permission="measurement.read", write=False,
           requirement="MEAS-005", summary="Per-space differences between two revisions of a property")  # fmt: skip
def diff_sets(req: Req, set_id: str, other_id: str):
    a, _ = sets.get_visible(req.session, req.ctx, set_id)
    b, _ = sets.get_visible(req.session, req.ctx, other_id)
    return ok(sets.diff(req.session, a, b))


# --- verification (B1-T07) ---------------------------------------------------------------------------------------------
@api.route("GET", "/measurement-sets/<set_id>/checks", permission="measurement.read", write=False,
           requirement="MEAS-006",
           summary="Dry run: what still blocks submission and verification, and the usable wall segments")  # fmt: skip
def set_checks(req: Req, set_id: str):
    mset, _ = sets.get_visible(req.session, req.ctx, set_id)
    return ok(verification.readiness(req.session, mset, req.ctx.user.id))


@api.route("POST", "/measurement-sets/<set_id>/verify", permission="measurement.verify", body=C.VerifyIn,
           if_match=True, idempotent_create=True, requirement="MEAS-006",
           summary="Verify a submitted revision: fail-closed checks, sealed snapshot, the previous verified set superseded")  # fmt: skip
def verify_set(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.verify")
    req.require_version(mset.version)
    verification.verify(req.session, req.ctx, mset, prop, list(req.body.acknowledgements) if req.body else [])
    req.session.flush()
    return ok(sets.present(req.session, mset, full=False))


# --- offline sync (B1-T09) ---------------------------------------------------------------------------------------------
@api.route("POST", "/measurement-sets/<set_id>/sync", permission="measurement.capture", body=SY.SyncBatchIn,
           max_body=2 * 1024 * 1024, idempotent_create=True, limits=CAPTURE_LIMITS, requirement="MEAS-004",
           summary="Apply a batch of offline operations in order; each answers on its own (no last-write-wins)")  # fmt: skip
def sync_set(req: Req, set_id: str):
    mset, prop = sets.get_visible(req.session, req.ctx, set_id, "measurement.capture")
    result = sync.run(req.session, req.ctx, mset, prop, req.body)
    req.session.flush()
    return ok(result)


@api.route("GET", "/measurement-sets/<set_id>/sync-state", permission="measurement.read", write=False,
           requirement="MEAS-005", summary="Per-space versions and claims for a reconnecting client")  # fmt: skip
def sync_state(req: Req, set_id: str):
    mset, _ = sets.get_visible(req.session, req.ctx, set_id)
    return ok(sync.state(req.session, mset))
