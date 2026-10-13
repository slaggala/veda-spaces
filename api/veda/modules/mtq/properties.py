"""Property and space-tree service (MTQ B1-T04; blueprint §4.1, §5; B1-SCOPE §2.2, §2.7, §2.9.4).

- A property belongs to a lead; its spaces form a tree (a toilet or dressing inside a bedroom).
- A property template seeds a starting tree; nothing else depends on it. BHK is never stored: the bedroom, toilet and
  level counts are derived from the live, in-scope spaces every time the tree changes, and the display label is
  derived from those counts.
- ``property_space.id`` is stable for life: archiving a space soft-deletes it and keeps the id (B1-SCOPE §2.7).
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import clock, sequences
from veda.kernel.errors import ApiError, field_error, not_found

from . import scope, templates
from . import vocab as V
from .models import MeasurementSet, Property, PropertySpace

MAX_DEPTH = 3  # property → room → attached room → nested (a niche-sized closet inside a dressing)
SPACE_LIMIT = 200


def _zone_for(space_type_code: str, requested: str | None) -> str:
    if requested:
        return requested
    attrs = next(r[3] for r in V.SPACE_TYPE_ROWS if r[0] == space_type_code)
    return attrs.get("default_zone", "INDOOR")


def live_spaces(s: Session, property_id: str) -> list[PropertySpace]:
    return list(
        s.execute(
            sa.select(PropertySpace)
            .where(PropertySpace.property_id == property_id)
            .order_by(PropertySpace.level_index, PropertySpace.sort_order, PropertySpace.id)
        ).scalars()
    )


def derive(s: Session, prop: Property) -> None:
    """Recompute the derived counts from the live, in-scope spaces (B1-SCOPE §2.9.4)."""
    spaces = [sp for sp in live_spaces(s, prop.id) if sp.is_in_scope]
    prop.derived_bedroom_count = sum(1 for sp in spaces if sp.space_type_code in V.BEDROOM_TYPES)
    prop.derived_toilet_count = sum(1 for sp in spaces if sp.space_type_code in V.TOILET_TYPES)
    prop.derived_level_count = max(1, len({sp.level_index for sp in spaces}))


def display_label(prop: Property) -> str:
    """The derived residential label: "3 BHK apartment", "4 BHK independent house, 2 levels"."""
    beds = prop.derived_bedroom_count
    head = f"{beds} BHK" if beds else "No bedrooms yet"
    if prop.property_type_code == "INDEPENDENT_HOUSE":
        levels = prop.derived_level_count
        return f"{head} independent house, {levels} level{'s' if levels != 1 else ''}"
    return f"{head} apartment"


def get_visible(s: Session, ctx, property_id: str, permission: str = "property.read") -> Property:
    prop = s.execute(
        sa.select(Property).where(Property.id == property_id, scope.condition(ctx, permission, Property.lead_id))
    ).scalar_one_or_none()
    if prop is None:
        raise not_found()
    return prop


def get_space(s: Session, ctx, space_id: str, permission: str = "property.read") -> tuple[PropertySpace, Property]:
    row = s.execute(
        sa.select(PropertySpace, Property)
        .join(Property, Property.id == PropertySpace.property_id)
        .where(PropertySpace.id == space_id, scope.condition(ctx, permission, Property.lead_id))
    ).first()
    if row is None:
        raise not_found()
    return row[0], row[1]


def _next_instance(s: Session, property_id: str, space_type_code: str) -> int:
    current = s.execute(
        sa.select(sa.func.max(PropertySpace.instance_no))
        .where(PropertySpace.property_id == property_id, PropertySpace.space_type_code == space_type_code)
        .execution_options(include_deleted=True)  # an archived instance number is never reused (stable labels)
    ).scalar()
    return int(current or 0) + 1


def _next_sort(s: Session, property_id: str) -> int:
    current = s.execute(
        sa.select(sa.func.max(PropertySpace.sort_order)).where(PropertySpace.property_id == property_id)
    ).scalar()
    return int(current or 0) + 10


def _check_parent(s: Session, prop: Property, parent_id: str | None, space: PropertySpace | None = None) -> None:
    """The parent is a live space of the same property, the move makes no cycle, and nesting stays shallow."""
    if parent_id is None:
        return
    parent = s.get(PropertySpace, parent_id)
    if parent is None or parent.is_deleted or parent.property_id != prop.id:
        raise ApiError(422, "VALIDATION_FAILED", "The parent space must be a live space of the same property.",
                       errors=[field_error("parent_space_id", "INVALID", "Not a space of this property.")])  # fmt: skip
    ancestors = [parent.id]
    next_id = parent.parent_space_id
    while next_id is not None and len(ancestors) <= MAX_DEPTH + 1:
        above = s.get(PropertySpace, next_id)
        if above is None:
            break
        ancestors.append(above.id)
        next_id = above.parent_space_id
    if space is not None and space.id in ancestors:
        raise ApiError(422, "VALIDATION_FAILED", "A space cannot sit inside itself.",
                       errors=[field_error("parent_space_id", "CYCLE", "That would make a cycle.")])  # fmt: skip
    if len(ancestors) >= MAX_DEPTH:
        raise ApiError(422, "VALIDATION_FAILED", f"Spaces nest at most {MAX_DEPTH} levels deep.",
                       errors=[field_error("parent_space_id", "TOO_DEEP", "Too deep.")])  # fmt: skip


def _custom_label(space_type_code: str, custom_label: str | None) -> None:
    if space_type_code == "CUSTOM" and not custom_label:
        raise ApiError(422, "VALIDATION_FAILED", "Name the custom space.",
                       errors=[field_error("custom_type_label", "REQUIRED", "A custom space needs a name.")])  # fmt: skip


def add_space(
    s: Session,
    prop: Property,
    *,
    space_type_code: str,
    label: str,
    custom_type_label: str | None = None,
    parent_space_id: str | None = None,
    level_index: int = 0,
    zone_code: str | None = None,
    sort_order: int | None = None,
    is_in_scope: bool = True,
    attributes: dict | None = None,
    template_key: str | None = None,
    instance_no: int | None = None,
) -> PropertySpace:
    _custom_label(space_type_code, custom_type_label)
    count = s.execute(sa.select(sa.func.count(PropertySpace.id)).where(PropertySpace.property_id == prop.id)).scalar()
    if int(count or 0) >= SPACE_LIMIT:
        raise ApiError(422, "LIMIT_EXCEEDED", f"A property has at most {SPACE_LIMIT} spaces.")
    _check_parent(s, prop, parent_space_id)
    tkey = template_key or templates.space_template_for(space_type_code)[0]
    sp = PropertySpace(
        property_id=prop.id,
        parent_space_id=parent_space_id,
        space_type_code=space_type_code,
        custom_type_label=custom_type_label if space_type_code == "CUSTOM" else None,
        label=label,
        instance_no=instance_no or _next_instance(s, prop.id, space_type_code),
        level_index=level_index,
        zone_code=_zone_for(space_type_code, zone_code),
        sort_order=sort_order if sort_order is not None else _next_sort(s, prop.id),
        is_in_scope=is_in_scope,
        space_template_key=tkey,
        template_version=templates.TEMPLATE_VERSION,
        attributes={k: v for k, v in (attributes or {}).items() if v is not None},
    )
    s.add(sp)
    s.flush()
    return sp


def seed_from_template(s: Session, prop: Property, key: str, include_optional: list[str]) -> list[PropertySpace]:
    tpl = templates.property_template(key)
    if tpl.property_type_code != prop.property_type_code:
        raise ApiError(422, "VALIDATION_FAILED", "The template does not match the property type.")
    known = {sp.ref for sp in tpl.spaces}
    unknown = sorted(set(include_optional) - known)
    if unknown:
        raise ApiError(422, "VALIDATION_FAILED", "Unknown optional spaces.",
                       errors=[field_error("include_optional", "UNKNOWN", ", ".join(unknown))])  # fmt: skip
    if live_spaces(s, prop.id):
        raise ApiError(409, "INVALID_STATE", "This property already has spaces; add them one by one.")
    created: dict[str, PropertySpace] = {}
    order = 0
    for seed in tpl.spaces:
        if seed.optional and seed.ref not in include_optional:
            continue
        if seed.parent is not None and seed.parent not in created:
            continue  # the parent was an optional space that was not included
        order += 10
        created[seed.ref] = add_space(
            s,
            prop,
            space_type_code=seed.space_type_code,
            label=seed.label,
            parent_space_id=created[seed.parent].id if seed.parent else None,
            level_index=seed.level_index,
            zone_code=seed.zone_code,
            sort_order=order,
            template_key=seed.template,
            instance_no=seed.instance_no,
        )
    prop.template_key, prop.template_version = key, templates.TEMPLATE_VERSION
    derive(s, prop)
    return list(created.values())


def create(s: Session, ctx, body) -> Property:
    scope.require_lead(s, ctx, body.lead_id, "property.create")
    tpl = templates.property_template(body.template_key) if body.template_key else None
    prop = Property(
        property_number=sequences.next_number(s, "PROPERTY"),
        lead_id=body.lead_id,
        property_type_code=body.property_type_code,
        usage_code="RESIDENTIAL",
        project_kind_code=body.project_kind_code or (tpl.default_project_kind if tpl else "NEW"),
        configuration_label=body.configuration_label or (tpl.configuration_label if tpl else None),
        built_up_area_sqft_centi=body.built_up_area_sqft_centi,
        carpet_area_sqft_centi=body.carpet_area_sqft_centi,
        plot_area_sqft_centi=body.plot_area_sqft_centi,
        floor_count=body.floor_count,
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        locality=body.locality,
        city=body.city,
        state=body.state,
        pincode=body.pincode,
        geo_lat_e6=body.geo_lat_e6,
        geo_lng_e6=body.geo_lng_e6,
        possession_status_code=body.possession_status_code,
        possession_on=body.possession_on,
        notes=body.notes,
    )
    s.add(prop)
    s.flush()
    if body.template_key:
        seed_from_template(s, prop, body.template_key, list(body.include_optional))
    return prop


PATCHABLE = (
    "project_kind_code",
    "configuration_label",
    "built_up_area_sqft_centi",
    "carpet_area_sqft_centi",
    "plot_area_sqft_centi",
    "floor_count",
    "address_line_1",
    "address_line_2",
    "locality",
    "city",
    "state",
    "pincode",
    "geo_lat_e6",
    "geo_lng_e6",
    "possession_status_code",
    "possession_on",
    "floor_plan_attachment_id",
    "notes",
)


def update(s: Session, ctx, prop: Property, body) -> Property:
    scope.require_in_scope(s, ctx, prop.lead_id, "property.update")
    provided = body.provided()
    if "floor_plan_attachment_id" in provided and body.floor_plan_attachment_id is not None:
        from veda.modules.attachments.models import Attachment

        att = s.get(Attachment, body.floor_plan_attachment_id)
        if att is None or att.lead_id != prop.lead_id or att.category_code != "FLOOR_PLAN":
            raise ApiError(422, "VALIDATION_FAILED", "Not a floor-plan attachment of this property's lead.",
                           errors=[field_error("floor_plan_attachment_id", "INVALID", "Not a floor plan.")])  # fmt: skip
    for name in PATCHABLE:
        if name in provided:
            setattr(prop, name, getattr(body, name))
    if (prop.geo_lat_e6 is None) != (prop.geo_lng_e6 is None):
        raise ApiError(422, "VALIDATION_FAILED", "geo_lat_e6 and geo_lng_e6 go together.")
    return prop


def update_space(s: Session, ctx, sp: PropertySpace, prop: Property, body) -> PropertySpace:
    scope.require_in_scope(s, ctx, prop.lead_id, "property.update")
    provided = body.provided()
    if "parent_space_id" in provided:
        _check_parent(s, prop, body.parent_space_id, sp)
        sp.parent_space_id = body.parent_space_id
    if "label" in provided:
        if not body.label:
            raise ApiError(422, "VALIDATION_FAILED", "A space needs a label.",
                           errors=[field_error("label", "REQUIRED", "Required.")])  # fmt: skip
        sp.label = body.label
    if "custom_type_label" in provided:
        _custom_label(sp.space_type_code, body.custom_type_label)
        sp.custom_type_label = body.custom_type_label if sp.space_type_code == "CUSTOM" else None
    for name in ("level_index", "zone_code", "is_in_scope"):
        if name in provided and getattr(body, name) is not None:
            setattr(sp, name, getattr(body, name))
    if "attributes" in provided and body.attributes is not None:
        sp.attributes = body.attributes.model_dump(exclude_none=True)
    derive(s, prop)
    return sp


def archive_space(s: Session, ctx, sp: PropertySpace, prop: Property) -> None:
    """Soft delete: the id is kept for revision diffs and history (B1-SCOPE §2.7)."""
    scope.require_in_scope(s, ctx, prop.lead_id, "property.update")
    children = s.execute(sa.select(PropertySpace.id).where(PropertySpace.parent_space_id == sp.id)).first()
    if children is not None:
        raise ApiError(409, "INVALID_STATE", "Archive or move the spaces inside this one first.")
    sp.is_deleted = True
    s.flush()
    derive(s, prop)


def reorder(s: Session, ctx, prop: Property, space_ids: list[str]) -> list[PropertySpace]:
    scope.require_in_scope(s, ctx, prop.lead_id, "property.update")
    spaces = {sp.id: sp for sp in live_spaces(s, prop.id)}
    if len(set(space_ids)) != len(space_ids) or set(space_ids) != set(spaces):
        raise ApiError(422, "VALIDATION_FAILED", "List every live space of the property exactly once.",
                       errors=[field_error("space_ids", "INCOMPLETE", "Every live space, once.")])  # fmt: skip
    for i, sid in enumerate(space_ids, start=1):
        spaces[sid].sort_order = i * 10
    return [spaces[sid] for sid in space_ids]


def present_space(sp: PropertySpace) -> dict[str, Any]:
    return {
        "id": sp.id,
        "version": sp.version,
        "property_id": sp.property_id,
        "parent_space_id": sp.parent_space_id,
        "space_type_code": sp.space_type_code,
        "custom_type_label": sp.custom_type_label,
        "label": sp.label,
        "instance_no": sp.instance_no,
        "level_index": sp.level_index,
        "zone_code": sp.zone_code,
        "sort_order": sp.sort_order,
        "is_in_scope": sp.is_in_scope,
        "space_template_key": sp.space_template_key,
        "template_version": sp.template_version,
        "attributes": sp.attributes or {},
        "counts_as_bedroom": sp.space_type_code in V.BEDROOM_TYPES,
        "counts_as_toilet": sp.space_type_code in V.TOILET_TYPES,
    }


def present(s: Session, prop: Property, *, with_spaces: bool = True) -> dict[str, Any]:
    latest_verified = s.execute(
        sa.select(MeasurementSet.id, MeasurementSet.revision_no, MeasurementSet.survey_level_code).where(
            MeasurementSet.property_id == prop.id, MeasurementSet.status == "VERIFIED"
        )
    ).first()
    out = {
        "id": prop.id,
        "version": prop.version,
        "property_number": prop.property_number,
        "lead_id": prop.lead_id,
        "property_type_code": prop.property_type_code,
        "usage_code": prop.usage_code,
        "project_kind_code": prop.project_kind_code,
        "configuration_label": prop.configuration_label,
        "display_label": display_label(prop),
        "derived_bedroom_count": prop.derived_bedroom_count,
        "derived_toilet_count": prop.derived_toilet_count,
        "derived_level_count": prop.derived_level_count,
        "derived_measured_floor_area_sqft_centi": prop.derived_measured_floor_area_sqft_centi,
        "built_up_area_sqft_centi": prop.built_up_area_sqft_centi,
        "carpet_area_sqft_centi": prop.carpet_area_sqft_centi,
        "plot_area_sqft_centi": prop.plot_area_sqft_centi,
        "floor_count": prop.floor_count,
        "address_line_1": prop.address_line_1,
        "address_line_2": prop.address_line_2,
        "locality": prop.locality,
        "city": prop.city,
        "state": prop.state,
        "pincode": prop.pincode,
        "geo_lat_e6": prop.geo_lat_e6,
        "geo_lng_e6": prop.geo_lng_e6,
        "possession_status_code": prop.possession_status_code,
        "possession_on": prop.possession_on.isoformat() if prop.possession_on else None,
        "floor_plan_attachment_id": prop.floor_plan_attachment_id,
        "template_key": prop.template_key,
        "template_version": prop.template_version,
        "notes": prop.notes,
        "latest_verified_set": dict(latest_verified._mapping) if latest_verified else None,
        "created_on": clock.to_rfc3339(prop.created_on),
    }
    if with_spaces:
        out["spaces"] = [present_space(sp) for sp in live_spaces(s, prop.id)]
    return out
