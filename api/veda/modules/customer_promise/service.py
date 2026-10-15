"""The Customer Promise workflow (CPA-01, CPA-16, CPA-20 to CPA-22, CPA-27, CPA-28).

    DRAFT ─submit─► IN_REVIEW ─(every changed section approved) approve─► APPROVED ─publish─► PUBLISHED ─► SUPERSEDED
      ▲   │discard        │ request changes (a section)          │ return                   (when the next publishes)
      │   ▼               │                                      │
      │ DISCARDED         ▼                                      ▼
      └───────────────────┴──────────────────────────────────────┘

- Only a DRAFT is edited, one section at a time, by the section's edit capability. A version's content never changes
  after it is submitted; a change is a new version (a draft from the published version, or a rollback: a draft from an
  earlier published version, which goes through the same review). There is no other way to make content current.
- Review is per section and only of the sections that differ from the published version. A review is bound to the
  section's digest in that submission round; a request for changes returns the version to DRAFT and keeps the review.
- Four-eyes, every section: nobody who saved a section, submitted the version, or (for a rollback) restored it reviews
  that section, and nobody who contributed to any changed section or submitted the version approves it. The
  contributors are read from the stored list and from the event trail, so clearing one never clears the other.
- Publication is atomic: the approved digest is checked again, every rule is re-run, the published version becomes
  SUPERSEDED and the new one PUBLISHED, with its customer content frozen and digested, in one transaction. Effective
  immediately: there is no scheduled activation (CPA-32 deferred).
- Every write needs the version the user saw (If-Match); a stale browser gets VERSION_CONFLICT and nothing changes.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.kernel import db
from veda.kernel.errors import ApiError

from . import binding, diff, rules
from . import sections as SEC
from .models import OPEN_STATUSES, CustomerPromiseEvent, CustomerPromisePack, CustomerPromiseReview


def content_version(version_no: int) -> str:
    return f"CPP-{version_no}"


# --- reads -------------------------------------------------------------------------------------------------------------
def get(s: Session, pack_id: str) -> CustomerPromisePack:
    p = s.get(CustomerPromisePack, pack_id)
    if p is None or p.is_deleted:
        raise ApiError(404, "NOT_FOUND", "No such Customer Promise version.")
    return p


def lock(s: Session, p: CustomerPromisePack) -> CustomerPromisePack:
    """Re-read the row under a row lock (PostgreSQL) so concurrent decisions on one version run one after the other."""
    if s.get_bind().dialect.name == "postgresql":
        s.execute(sa.select(CustomerPromisePack.id).where(CustomerPromisePack.id == p.id).with_for_update())
        s.refresh(p)
    return p


def open_version(s: Session) -> CustomerPromisePack | None:
    return s.execute(
        sa.select(CustomerPromisePack).where(CustomerPromisePack.status.in_(OPEN_STATUSES))
    ).scalar_one_or_none()


def versions(s: Session) -> list[CustomerPromisePack]:
    return list(s.execute(sa.select(CustomerPromisePack).order_by(CustomerPromisePack.version_no.desc())).scalars())


def baseline(s: Session, p: CustomerPromisePack) -> CustomerPromisePack | None:
    """What a version is compared with: the published version (a new or open version), else what it superseded."""
    if p.status in (*OPEN_STATUSES, "DISCARDED"):
        return binding.current_published(s)
    return s.execute(
        sa.select(CustomerPromisePack).where(CustomerPromisePack.superseded_by_pack_id == p.id)
    ).scalar_one_or_none()


def changed(s: Session, p: CustomerPromisePack) -> list[str]:
    base = baseline(s, p)
    return SEC.changed_sections(base.content if base else None, p.content)


def reviews(s: Session, p: CustomerPromisePack) -> list[CustomerPromiseReview]:
    return list(s.execute(sa.select(CustomerPromiseReview).where(CustomerPromiseReview.pack_id == p.id)
                          .order_by(CustomerPromiseReview.created_on, CustomerPromiseReview.id)).scalars())  # fmt: skip


def current_reviews(s: Session, p: CustomerPromisePack) -> dict[str, CustomerPromiseReview]:
    """Per section, the latest review of this round that still matches the section as it is."""
    out: dict[str, CustomerPromiseReview] = {}
    for r in reviews(s, p):
        if r.review_round == p.review_round and r.section_sha256 == SEC.section_digest(p.content, r.section_code):
            out[r.section_code] = r
    return out


def events(s: Session, p: CustomerPromisePack) -> list[CustomerPromiseEvent]:
    return list(s.execute(sa.select(CustomerPromiseEvent).where(CustomerPromiseEvent.pack_id == p.id)
                          .order_by(CustomerPromiseEvent.created_on, CustomerPromiseEvent.id)).scalars())  # fmt: skip


def _warranty_terms_decided() -> bool:
    from veda.modules.mtq_commercial import policy

    return policy.decision("OI-MTQ-09") is not None


def problems(s: Session, p: CustomerPromisePack) -> list[dict[str, str]]:
    found = rules.problems(p.content, warranty_terms_decided=_warranty_terms_decided())
    if not changed(s, p):
        found.append({"section": "CONTACTS", "code": "NO_CHANGE",
                      "message": "This version is the same as the published one; there is nothing to publish."})  # fmt: skip
    return found


# --- contributors and four-eyes ---------------------------------------------------------------------------------------
def contributors(s: Session, p: CustomerPromisePack, section: str) -> set[str]:
    """Everyone who saved the section, submitted the version, or created it with this section differing from the
    published version (a rollback restores content: its creator is its author)."""
    found = set((p.contributors or {}).get(section) or [])
    found.update(x for x in (p.submitted_by,) if x)
    for e in events(s, p):
        detail = e.detail or {}
        if (
            (e.event_code == "SECTION_UPDATED" and e.section_code == section)
            or e.event_code == "SUBMITTED"
            or (e.event_code == "DRAFT_CREATED" and section in (detail.get("differs_from_published") or []))
        ):
            found.add(e.created_by)
    return found


def _contribute(p: CustomerPromisePack, section: str, user_id: str) -> None:
    current = dict(p.contributors or {})
    if user_id not in current.get(section, []):
        current[section] = [*current.get(section, []), user_id]
        p.contributors = current


# --- events ------------------------------------------------------------------------------------------------------------
def _event(s: Session, p: CustomerPromisePack, code: str, frm: str | None = None, to: str | None = None, *,
           section: str | None = None, reason: str | None = None, **detail) -> None:  # fmt: skip
    s.add(CustomerPromiseEvent(pack_id=p.id, event_code=code, section_code=section, from_status=frm, to_status=to,
                               reason=reason, detail=detail or None))  # fmt: skip


# --- guards ------------------------------------------------------------------------------------------------------------
def _need(ctx, code: str, what: str) -> None:
    """The capability an action needs (a refusal is recorded as a PERMISSION_DENIED security event)."""
    if not ctx.has(code):
        from veda.platform.auth.request_auth import deny

        deny(ctx, code)


def _status(p: CustomerPromisePack, *allowed: str) -> None:
    if p.status not in allowed:
        raise ApiError(409, "INVALID_STATE", f"Customer Promise version {p.version_no} is "
                       f"{p.status.lower().replace('_', ' ')}.", extra={"status": p.status})  # fmt: skip


def _section(code: str) -> SEC.Section:
    sec = SEC.BY_CODE.get(code)
    if sec is None:
        raise ApiError(404, "NOT_FOUND", "No such Customer Promise section.")
    return sec


def _reason(text: str | None, what: str) -> str:
    value = (text or "").strip()
    if len(value) < 5:
        raise ApiError(422, "VALIDATION_FAILED", f"Say why {what} (at least 5 characters).",
                       errors=[{"field": "reason", "code": "TOO_SHORT", "message": "At least 5 characters."}])  # fmt: skip
    return value


# --- drafting ----------------------------------------------------------------------------------------------------------
def create_draft(s: Session, ctx, based_on_id: str | None, change_summary: str | None) -> CustomerPromisePack:
    """A new DRAFT: a copy of the published version (or of ``based_on_id``, an earlier published version: a rollback),
    or an empty pack when nothing was ever published."""
    _need(ctx, "customer_promise.draft.create", "start a Customer Promise draft")
    found = open_version(s)
    if found is not None:
        raise ApiError(409, "DRAFT_EXISTS", f"Version {found.version_no} is already in progress "
                       f"({found.status.lower().replace('_', ' ')}); continue with it.", extra={"pack_id": found.id})  # fmt: skip
    current = binding.current_published(s)
    source = current
    origin = "REVISION" if current else "NEW"
    if based_on_id is not None:
        source = get(s, based_on_id)
        if source.status not in ("PUBLISHED", "SUPERSEDED"):
            raise ApiError(409, "NOT_APPROVED_CONTENT", "A new version starts from a version that was approved and "
                           "published (the current one, or an earlier one to roll back to).")  # fmt: skip
        origin = "REVISION" if source.status == "PUBLISHED" else "ROLLBACK"
    content = dict(source.content) if source else SEC.empty()
    last = s.execute(sa.select(sa.func.max(CustomerPromisePack.version_no))).scalar() or 0
    p = CustomerPromisePack(version_no=last + 1, status="DRAFT", origin=origin,
                            based_on_pack_id=source.id if source else None,
                            change_summary=(change_summary or "").strip()[:500] or None, content=content,
                            content_sha256=SEC.digest(content), contributors={}, review_round=0)  # fmt: skip
    s.add(p)
    s.flush()
    differs = SEC.changed_sections(current.content if current else None, content)
    for code in differs:  # a rollback restores content: its creator authored those sections in this version
        _contribute(p, code, ctx.user.id)
    _event(s, p, "DRAFT_CREATED", None, "DRAFT", origin=origin, based_on_version=source.version_no if source else None,
           content_sha256=p.content_sha256, differs_from_published=differs)  # fmt: skip
    return p


def save_section(s: Session, ctx, p: CustomerPromisePack, code: str, value: dict[str, Any]) -> CustomerPromisePack:
    """Replace one section of a DRAFT with ``value`` (exactly the section's keys), checked by every content rule."""
    sec = _section(code)
    _need(ctx, sec.edit, f"edit the {sec.title.lower()} section")
    _status(p, "DRAFT")
    if set(value) != set(sec.keys):
        raise ApiError(422, "VALIDATION_FAILED", f"The {sec.title.lower()} section has exactly these fields: "
                       f"{', '.join(sec.keys)}.", errors=[{"field": k, "code": "UNKNOWN_FIELD" if k not in sec.keys
                                                          else "REQUIRED", "message": "not a field of this section"
                                                          if k not in sec.keys else "required"}
                                                         for k in sorted(set(value) ^ set(sec.keys))])  # fmt: skip
    candidate = {**p.content, **value}
    try:
        SEC.check(candidate)
    except SEC.ContentError as err:
        raise ApiError(422, "VALIDATION_FAILED", "Some content is not allowed in customer copy.",
                       errors=err.errors) from err  # fmt: skip
    before = SEC.section_digest(p.content, code)
    after = SEC.section_digest(candidate, code)
    if before == after:
        return p
    p.content, p.content_sha256 = candidate, SEC.digest(candidate)
    _contribute(p, code, ctx.user.id)
    _event(s, p, "SECTION_UPDATED", "DRAFT", "DRAFT", section=code, before_sha256=before, after_sha256=after,
           content_sha256=p.content_sha256)  # fmt: skip
    return p


def set_summary(s: Session, ctx, p: CustomerPromisePack, summary: str | None) -> CustomerPromisePack:
    _need(ctx, "customer_promise.draft.create", "change a draft's summary")
    _status(p, "DRAFT")
    p.change_summary = (summary or "").strip()[:500] or None
    _event(s, p, "SUMMARY_UPDATED", "DRAFT", "DRAFT")
    return p


def discard(s: Session, ctx, p: CustomerPromisePack, reason: str) -> CustomerPromisePack:
    """A DRAFT nobody wants: kept as DISCARDED (never deleted), so its history stays readable."""
    _need(ctx, "customer_promise.draft.create", "discard a Customer Promise draft")
    _status(p, "DRAFT")
    why = _reason(reason, "the draft is discarded")
    p.status, p.discarded_on = "DISCARDED", db.tx_time(s)
    _event(s, p, "DRAFT_DISCARDED", "DRAFT", "DISCARDED", reason=why)
    return p


# --- review ------------------------------------------------------------------------------------------------------------
def submit(s: Session, ctx, p: CustomerPromisePack) -> CustomerPromisePack:
    _need(ctx, "customer_promise.submit", "submit a Customer Promise draft")
    _status(p, "DRAFT")
    found = problems(s, p)
    if found:
        raise ApiError(422, "NOT_PUBLISHABLE", f"{len(found)} problem(s) must be fixed before review.",
                       extra={"problems": found})  # fmt: skip
    p.status, p.submitted_by, p.submitted_on = "IN_REVIEW", ctx.user.id, db.tx_time(s)
    p.review_round += 1
    p.approved_by = p.approved_on = p.approved_sha256 = None
    _event(s, p, "SUBMITTED", "DRAFT", "IN_REVIEW", review_round=p.review_round, content_sha256=p.content_sha256,
           sections=changed(s, p))  # fmt: skip
    return p


def review(
    s: Session, ctx, p: CustomerPromisePack, code: str, decision: str, comment: str | None
) -> CustomerPromisePack:
    sec = _section(code)
    _need(ctx, sec.review, f"review the {sec.title.lower()} section")
    lock(s, p)
    _status(p, "IN_REVIEW")
    if code not in changed(s, p):
        raise ApiError(409, "SECTION_UNCHANGED", f"The {sec.title.lower()} section is the same as the published "
                       "version; only changed sections are reviewed.")  # fmt: skip
    if ctx.user.id in contributors(s, p, code):
        raise ApiError(409, "FOUR_EYES_REQUIRED", f"You saved or submitted the {sec.title.lower()} section; someone "
                       "else reviews it.")  # fmt: skip
    note = (comment or "").strip()[:1000] or None
    if decision == "CHANGES_REQUESTED":
        note = _reason(note, "changes are requested")
    s.add(CustomerPromiseReview(pack_id=p.id, review_round=p.review_round, section_code=code, decision=decision,
                                section_sha256=SEC.section_digest(p.content, code), comment=note))  # fmt: skip
    if decision == "CHANGES_REQUESTED":
        p.status = "DRAFT"
        _event(s, p, "CHANGES_REQUESTED", "IN_REVIEW", "DRAFT", section=code, reason=note,
               review_round=p.review_round)  # fmt: skip
    else:
        p.updated_on = db.tx_time(s)  # the version moves on: a stale screen cannot act on the earlier state
        _event(s, p, "SECTION_APPROVED", "IN_REVIEW", "IN_REVIEW", section=code, reason=note,
               review_round=p.review_round, section_sha256=SEC.section_digest(p.content, code))  # fmt: skip
    return p


def pending_reviews(s: Session, p: CustomerPromisePack) -> list[str]:
    done = current_reviews(s, p)
    return [c for c in changed(s, p) if c not in done or done[c].decision != "APPROVED"]


def approve(s: Session, ctx, p: CustomerPromisePack, note: str | None) -> CustomerPromisePack:
    _need(ctx, "customer_promise.approve", "approve a Customer Promise version")
    lock(s, p)
    _status(p, "IN_REVIEW")
    waiting = pending_reviews(s, p)
    if waiting:
        raise ApiError(409, "REVIEW_INCOMPLETE", "Every changed section needs an approving review first.",
                       extra={"sections": waiting})  # fmt: skip
    involved = set().union(*(contributors(s, p, c) for c in changed(s, p)))
    if ctx.user.id in involved:
        raise ApiError(409, "FOUR_EYES_REQUIRED", "You contributed to this version or submitted it; someone else "
                       "approves it.")  # fmt: skip
    found = problems(s, p)
    if found:
        raise ApiError(422, "NOT_PUBLISHABLE", f"{len(found)} problem(s) stop this version.", extra={"problems": found})
    p.status, p.approved_by, p.approved_on, p.approved_sha256 = "APPROVED", ctx.user.id, db.tx_time(s), p.content_sha256
    _event(s, p, "APPROVED", "IN_REVIEW", "APPROVED", reason=(note or "").strip()[:1000] or None,
           content_sha256=p.content_sha256, sections=changed(s, p))  # fmt: skip
    return p


def return_to_draft(s: Session, ctx, p: CustomerPromisePack, reason: str) -> CustomerPromisePack:
    if not (ctx.has("customer_promise.submit") or ctx.has("customer_promise.approve")):
        _need(ctx, "customer_promise.submit", "return a Customer Promise version to draft")
    lock(s, p)
    _status(p, "IN_REVIEW", "APPROVED")
    why = _reason(reason, "the version returns to draft")
    frm = p.status
    p.status, p.approved_by, p.approved_on, p.approved_sha256 = "DRAFT", None, None, None
    _event(s, p, "RETURNED_TO_DRAFT", frm, "DRAFT", reason=why)
    return p


# --- publication -------------------------------------------------------------------------------------------------------
def publish(s: Session, ctx, p: CustomerPromisePack) -> CustomerPromisePack:
    _need(ctx, "customer_promise.publish", "publish a Customer Promise version")
    lock(s, p)
    _status(p, "APPROVED")
    if p.approved_sha256 != p.content_sha256 or SEC.digest(p.content) != p.content_sha256:
        raise ApiError(409, "APPROVAL_STALE", "The content no longer matches what was approved; it must be reviewed "
                       "and approved again.")  # fmt: skip
    if pending_reviews(s, p):
        raise ApiError(409, "REVIEW_INCOMPLETE", "A changed section has no current approving review.")
    found = problems(s, p)
    if found:
        raise ApiError(422, "NOT_PUBLISHABLE", f"{len(found)} problem(s) stop publication.", extra={"problems": found})
    now = db.tx_time(s)
    previous = binding.current_published(s)
    if previous is not None:
        lock(s, previous)
        if previous.status != "PUBLISHED":
            raise ApiError(409, "VERSION_CONFLICT", "The published version changed while you were publishing.")
        previous.status, previous.superseded_on, previous.superseded_by_pack_id = "SUPERSEDED", now, p.id
        _event(s, previous, "SUPERSEDED", "PUBLISHED", "SUPERSEDED", superseded_by_version=p.version_no)
        s.flush()  # one PUBLISHED row at a time (ux_customer_promise_pack__one_published)
    published = SEC.customer_content(p.content, content_version(p.version_no))
    p.published_content, p.published_sha256 = published, SEC.digest(published)
    p.status, p.published_by, p.published_on = "PUBLISHED", ctx.user.id, now
    approvals = [r.id for r in current_reviews(s, p).values()]
    _event(s, p, "PUBLISHED", "APPROVED", "PUBLISHED", published_sha256=p.published_sha256,
           content_sha256=p.content_sha256, content_version=content_version(p.version_no), approved_by=p.approved_by,
           review_ids=sorted(approvals), superseded_version=previous.version_no if previous else None)  # fmt: skip
    s.flush()
    return p


# --- preview -----------------------------------------------------------------------------------------------------------
PREVIEW_LABEL = "PREVIEW / NOT PUBLISHED"


def preview(s: Session, ctx, p: CustomerPromisePack) -> dict[str, Any]:
    """The version as customers would see it, through the CQX projection of the customer information block. Creates
    no quotation, link, acceptance or commitment; only a PREVIEWED event (who looked, at which digest)."""
    from veda.modules.customer_proposal import projection
    from veda.modules.mtq_commercial import customer_pack

    _need(ctx, "customer_promise.preview", "preview the Customer Promise")
    label = {"PUBLISHED": "PUBLISHED", "SUPERSEDED": "SUPERSEDED / NO LONGER PUBLISHED"}.get(p.status, PREVIEW_LABEL)
    try:
        pack = SEC.customer_content(p.content, content_version(p.version_no))
    except ValueError as err:
        raise ApiError(422, "NOT_PREVIEWABLE", "This version has content that is not valid customer copy.") from err
    info = projection.information({"customer_information": customer_pack.information(pack, None)})
    _event(s, p, "PREVIEWED", p.status, p.status, content_sha256=p.content_sha256)
    return {"label": label, "published": p.status == "PUBLISHED", "pack_id": p.id, "version_no": p.version_no,
            "status": p.status, "content_version": content_version(p.version_no), "information": info,
            "creates": {"quotation": False, "customer_link": False, "acceptance_evidence": False}}  # fmt: skip


def comparison(s: Session, p: CustomerPromisePack, against_id: str | None) -> dict[str, Any]:
    other = get(s, against_id) if against_id else baseline(s, p)
    return {"from": {"pack_id": other.id, "version_no": other.version_no, "status": other.status} if other else None,
            "to": {"pack_id": p.id, "version_no": p.version_no, "status": p.status},
            "changes": diff.diff(other.content if other else None, p.content)}  # fmt: skip
