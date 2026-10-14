"""Specifications and reference media for a proposal's lines (CQX-04).

**Specifications** come from the approved customer specification (ADR-012 T9) of the quotation's package that was
ACTIVE when the version was issued: a pinned, immutable, versioned document (a change is a new version), validated to
carry no amount, rate, cost, margin or warranty duration. Its digest is re-checked on every use; a mismatch withholds
every specification (fail closed) rather than showing changed text. A category reaches a line only through the line's
own catalogue product and line (``applies_to.lines``), never generically: a line without a matching category shows no
specification. The material warranty notes it carries are the specification's own approved text and are shown as
such, never merged with Veda Spaces service support (``projection``, OI-MTQ-09).

**Reference media** comes only from the catalogue V3 public view (approved, reachable, scanner-clean, rights-checked
images), and only while V3 serves and media delivery is on; anything else gives no image and the page shows its named
placeholder (gallery fallback). An image without alternative text is not used. Every image keeps its approved label
("Design reference" or "Illustrative example") and is shown with a note that it does not change the scope or the price.
Media is never part of the frozen document: it illustrates, it is not contractual, and a withdrawn image disappears.
3D is never offered here (V3 never serves it to customers).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from veda.config import settings
from veda.modules.mtq_commercial import quotations
from veda.modules.mtq_commercial.models import CostEstimateLine, Quotation

log = logging.getLogger("veda.customer_proposal")
MEDIA_NOTE = "Reference image: it illustrates the kind of item and does not change the scope or the price."
SPEC_FIELDS = ("label", "summary", "requirement", "grade", "thickness", "finish", "brand_examples", "equivalent_rule",
               "final_selection", "warranty_summary")  # fmt: skip


def _codes(s: Session, q: Quotation) -> dict[str, tuple[str, str]]:
    """Customer line reference → (catalogue product, line) of the version's priced lines (server-side only)."""
    lines = quotations.lines(s, q)
    ids = [x.cost_estimate_line_id for x in lines if x.cost_estimate_line_id]
    rows = (
        {}
        if not ids
        else {r.id: r for r in s.execute(sa.select(CostEstimateLine).where(CostEstimateLine.id.in_(ids))).scalars()}
    )
    out = {}
    for x in lines:
        est = rows.get(x.cost_estimate_line_id or "")
        if est is not None and est.card_product_code and est.card_line_code:
            out[f"L{x.position}"] = (est.card_product_code, est.card_line_code)
    return out


def pinned_spec(s: Session, q: Quotation):
    """The customer specification of ``q``'s package that was active when ``q`` was issued, if its digest verifies."""
    from veda.modules.estimator.models import EstimatorCustomerSpec as Spec

    if q.issued_on is None:
        return None
    row = s.execute(
        sa.select(Spec).where(
            Spec.package == q.tier_code, Spec.activated_on.is_not(None), Spec.activated_on <= q.issued_on,
            sa.or_(Spec.retired_on.is_(None), Spec.retired_on > q.issued_on),
        ).order_by(Spec.activated_on.desc()).limit(1)
    ).scalar_one_or_none()  # fmt: skip
    if row is None:
        return None
    digest = hashlib.sha256(json.dumps(row.document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != row.document_sha256:
        log.error("customer_proposal.spec_integrity_refused", extra={"spec_code": row.spec_code})
        return None
    return row


def specifications(s: Session, q: Quotation) -> dict[str, Any] | None:
    """{"name", "version", "summary", "equivalent_policy", "final_selection", "lines": {ref: [category]}} or None."""
    from veda.modules.estimator import customer_spec

    row = pinned_spec(s, q)
    if row is None:
        return None
    try:
        view = customer_spec.customer_view(row.document)
        spec = customer_spec.parse(row.document)
    except Exception:  # an invalid stored document is withheld, never half-shown
        log.error("customer_proposal.spec_invalid", extra={"spec_code": row.spec_code})
        return None
    cats = {c["code"]: c for c in view["categories"]}
    by_line: dict[str, list[dict[str, Any]]] = {}
    for ref, (product, line) in _codes(s, q).items():
        hits = [
            c.code
            for c in spec.categories
            if f"{product}.{line}" in c.applies_to.lines or f"{product}.*" in c.applies_to.lines
        ]
        if hits:
            by_line[ref] = [{k: (", ".join(v) if isinstance(v := cats[code].get(k), list) else v) for k in SPEC_FIELDS}
                            for code in hits]  # fmt: skip
    return {"name": view["name"], "version": view["version"], "summary": view["summary"],
            "equivalent_policy": view["equivalent_policy"], "final_selection": view["final_selection"],
            "lines": by_line}  # fmt: skip


def media(s: Session, q: Quotation) -> dict[str, list[dict[str, Any]]]:
    """Customer line reference → approved reference images, or {} whenever catalogue media cannot be served."""
    cfg = settings()
    if not (cfg.catalog_estimator_enabled and cfg.catalog_media_delivery_enabled):
        return {}
    try:
        from veda.modules.catalog import compile as catalog_compile
        from veda.modules.catalog import configure, kinds, service

        view, _ = configure.served_catalog(s)  # the approved, claim-checked public view (or a refusal)
        release = service.active_release(s)
        cat = catalog_compile.load_release(s, release) if release is not None else None
    except Exception:  # V3 unavailable for any reason: no image, never a partial or unchecked one
        return {}
    if cat is None:
        return {}
    public_media = view.get("media") or {}
    products = view.get("products") or {}
    by_engine: dict[str, list[str]] = {}
    for key, product in cat.of(kinds.Product).items():
        if key not in products:
            continue
        for variant in product.variants:
            keys = [m for m in (*variant.media, *products[key].get("media", ())) if m in public_media]
            by_engine.setdefault(variant.engine_product, []).extend(keys)
    out: dict[str, list[dict[str, Any]]] = {}
    for ref, (product, _line) in _codes(s, q).items():
        images = []
        for mkey in dict.fromkeys(by_engine.get(product, [])):
            m = public_media[mkey]
            urls = m.get("urls") or {}
            if m.get("type") != "IMAGE" or not m.get("alt") or not urls:
                continue  # an image without alternative text is not shown (CQX-04)
            images.append({"title": m["title"], "alt": m["alt"], "caption": m.get("caption"), "label": m["label"],
                           "urls": {k: urls[k] for k in ("thumb", "mobile", "desktop") if k in urls}})  # fmt: skip
        if images:
            out[ref] = images[:6]
    return out


def contribute(s: Session, g, q: Quotation, page: dict[str, Any]) -> None:
    """CQX-04 part of the page model: specifications per line and reference images per line and room."""
    page["specifications"] = specifications(s, q)
    images = media(s, q)
    page["media"] = {"note": MEDIA_NOTE, "lines": images,
                     "rooms": {r["ref"]: next((images[x["ref"]][0] for x in r["lines"] if x["ref"] in images), None)
                               for r in page["proposal"]["rooms"]}}  # fmt: skip
