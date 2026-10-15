"""What the portal shows: the landing page (CPA-25 completeness, CPA-33 history), a version with its sections, reviews
and history, and the actions the signed-in user may take (a hint for the page; every action is checked again)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from veda.kernel import clock
from veda.platform.identity.models import User

from . import binding, service
from . import sections as SEC
from .models import OPEN_STATUSES, CustomerPromisePack


def _when(value) -> str | None:
    return clock.to_rfc3339(value) if value else None


class People:
    def __init__(self, s: Session):
        self.s = s
        self.cache: dict[str, dict[str, Any]] = {}

    def __call__(self, uid: str | None) -> dict[str, Any] | None:
        if not uid:
            return None
        if uid not in self.cache:
            u = self.s.get(User, uid)
            self.cache[uid] = {"id": uid, "display_name": u.display_name if u else None}
        return self.cache[uid]


def summary(s: Session, p: CustomerPromisePack, people: People, usage: dict[str, dict[str, int]]) -> dict[str, Any]:
    return {
        "id": p.id, "version": p.version, "version_no": p.version_no, "status": p.status, "origin": p.origin,
        "content_version": service.content_version(p.version_no), "change_summary": p.change_summary,
        "based_on_version": _version_no(s, p.based_on_pack_id), "content_sha256": p.content_sha256,
        "created_on": _when(p.created_on), "created_by": people(p.created_by),
        "updated_on": _when(p.updated_on),
        "submitted_on": _when(p.submitted_on), "submitted_by": people(p.submitted_by),
        "approved_on": _when(p.approved_on), "approved_by": people(p.approved_by),
        "published_on": _when(p.published_on), "published_by": people(p.published_by),
        "published_sha256": p.published_sha256,
        "superseded_on": _when(p.superseded_on), "superseded_by_version": _version_no(s, p.superseded_by_pack_id),
        "effective": "CURRENT" if p.status == "PUBLISHED" else ("HISTORICAL" if p.status == "SUPERSEDED" else "NOT_EFFECTIVE"),
        "quotations": usage.get(p.id, {}),
    }  # fmt: skip


def _version_no(s: Session, pack_id: str | None) -> int | None:
    if not pack_id:
        return None
    row = s.get(CustomerPromisePack, pack_id)
    return row.version_no if row else None


def _contributor_refs(s: Session, p: CustomerPromisePack, code: str, people: People) -> list[dict[str, Any]]:
    return [x for x in (people(u) for u in sorted(service.contributors(s, p, code))) if x]


def detail(s: Session, ctx, p: CustomerPromisePack) -> dict[str, Any]:
    people = People(s)
    usage = binding.usage(s)
    changed = service.changed(s, p)
    done = service.current_reviews(s, p)
    me = ctx.user.id
    sections = []
    for sec in SEC.SECTIONS:
        involved = service.contributors(s, p, sec.code)
        r = done.get(sec.code)
        sections.append({
            "code": sec.code, "title": sec.title, "keys": list(sec.keys), "sensitive": sec.sensitive,
            "edit_permission": sec.edit, "review_permission": sec.review, "changed": sec.code in changed,
            "value": SEC.section_value(p.content, sec.code), "sha256": SEC.section_digest(p.content, sec.code),
            "review": {"decision": r.decision, "by": people(r.created_by), "on": _when(r.created_on),
                       "comment": r.comment} if r else None,
            "contributors": _contributor_refs(s, p, sec.code, people),
            "can_edit": p.status == "DRAFT" and ctx.has(sec.edit),
            "can_review": (p.status == "IN_REVIEW" and sec.code in changed and ctx.has(sec.review)
                           and me not in involved),
        })  # fmt: skip
    pending = service.pending_reviews(s, p) if p.status == "IN_REVIEW" else []
    everyone = set().union(*(service.contributors(s, p, c) for c in changed)) if changed else set()
    problems = service.problems(s, p) if p.status in OPEN_STATUSES else []
    out = {
        **summary(s, p, people, usage),
        "sections": sections,
        "changed_sections": changed,
        "pending_reviews": pending,
        "problems": problems,
        "reviews": [{"id": r.id, "round": r.review_round, "section": r.section_code, "decision": r.decision,
                     "comment": r.comment, "by": people(r.created_by), "on": _when(r.created_on),
                     "current": done.get(r.section_code) is r} for r in service.reviews(s, p)],
        "actions": {
            "save": p.status == "DRAFT" and any(x["can_edit"] for x in sections),
            "summary": p.status == "DRAFT" and ctx.has("customer_promise.draft.create"),
            "discard": p.status == "DRAFT" and ctx.has("customer_promise.draft.create"),
            "submit": p.status == "DRAFT" and ctx.has("customer_promise.submit") and not problems,
            "approve": (p.status == "IN_REVIEW" and ctx.has("customer_promise.approve") and not pending
                        and me not in everyone),
            "return": p.status in ("IN_REVIEW", "APPROVED") and (ctx.has("customer_promise.submit")
                                                                 or ctx.has("customer_promise.approve")),
            "publish": p.status == "APPROVED" and ctx.has("customer_promise.publish"),
            "preview": ctx.has("customer_promise.preview"),
            "history": ctx.has("customer_promise.audit.read"),
        },
    }  # fmt: skip
    if ctx.has("customer_promise.audit.read"):
        out["events"] = [{"code": e.event_code, "section": e.section_code, "from": e.from_status, "to": e.to_status,
                          "reason": e.reason, "detail": e.detail, "by": people(e.created_by), "on": _when(e.created_on)}
                         for e in service.events(s, p)]  # fmt: skip
    return out


def _area_status(code: str, published: dict | None, open_p: CustomerPromisePack | None, s: Session) -> str:
    area = next(a for a in SEC.AREAS if a.code == code)
    has_published = bool(SEC.area_value(code, published))
    if open_p is not None and area.section is not None and area.section in service.changed(s, open_p):
        if open_p.status == "DRAFT":
            return "DRAFT"
        if open_p.status == "APPROVED":
            return "APPROVED"
        r = service.current_reviews(s, open_p).get(area.section)
        return "APPROVED" if r is not None and r.decision == "APPROVED" else "NEEDS_REVIEW"
    return "PUBLISHED" if has_published else "NOT_STARTED"


def landing(s: Session, ctx) -> dict[str, Any]:
    from veda.modules.mtq_commercial import policy

    people = People(s)
    usage = binding.usage(s)
    current = binding.current_published(s)
    open_p = service.open_version(s)
    authority = binding.authority_state()
    delegated = authority["state"] == binding.DELEGATED
    published = binding.verified(current) if current else None
    terms = policy.decision("OI-MTQ-09")
    areas = []
    for a in SEC.AREAS:
        if a.section is None:  # Veda Spaces' service and workmanship commitments: contract terms (OI-MTQ-09)
            decided = bool(terms and terms.service_support)
            areas.append({"code": a.code, "title": a.title, "section": None, "governed_by": "OI-MTQ-09",
                          "status": "PUBLISHED" if decided else "TO_BE_CONFIRMED", "structure_exists": True,
                          "owner_approved_content": decided,
                          "customer_sees": "APPROVED_CONTENT" if decided else "TO_BE_CONFIRMED"})  # fmt: skip
            continue
        has = bool(SEC.area_value(a.code, published))
        sees = (
            "APPROVED_CONTENT"
            if has and delegated
            else "PACK_RECORDED_IN_OI_MTQ_18"
            if authority["state"] == binding.RECORDED_INLINE
            else "TO_BE_CONFIRMED"
        )
        areas.append({"code": a.code, "title": a.title, "section": a.section, "governed_by": "OI-MTQ-18",
                      "status": _area_status(a.code, published, open_p, s), "structure_exists": True,
                      "owner_approved_content": has and delegated, "customer_sees": sees})  # fmt: skip
    return {
        "authority": {**authority, "message": {
            binding.NOT_RECORDED: "Owner decision OI-MTQ-18 is not recorded: quotations show every customer "
                                  "information section as to be confirmed, whatever is published here.",
            binding.RECORDED_INLINE: "Owner decision OI-MTQ-18 records a pack directly; the published Customer "
                                     "Promise Pack is not used by quotations until the owner records this portal as "
                                     "its source.",
            binding.DELEGATED: "Owner decision OI-MTQ-18 names this portal as the source: new quotation versions "
                               "freeze the published Customer Promise Pack.",
        }[authority["state"]]},
        "published": summary(s, current, people, usage) if current else None,
        "open": summary(s, open_p, people, usage) if open_p else None,
        "pending_reviews": service.pending_reviews(s, open_p) if open_p and open_p.status == "IN_REVIEW" else [],
        "areas": areas,
        "versions": len(service.versions(s)),
        "effective_dating": "IMMEDIATE_ON_PUBLISH",
        "actions": {"create_draft": open_p is None and ctx.has("customer_promise.draft.create"),
                    "preview": ctx.has("customer_promise.preview"),
                    "history": ctx.has("customer_promise.audit.read")},
    }  # fmt: skip


def history(s: Session) -> list[dict[str, Any]]:
    people = People(s)
    usage = binding.usage(s)
    return [summary(s, p, people, usage) for p in service.versions(s)]
