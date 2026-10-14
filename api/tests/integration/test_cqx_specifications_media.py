"""CQX-04 scope, specifications and media: the approved customer specification pinned at issue (digest-checked),
per-line applicability only, and approved reference images that fail closed. SYNTHETIC only; SYNTHETIC_VALIDATED."""

from __future__ import annotations

import copy
import json
import re
from types import SimpleNamespace

from tests.integration.test_estimator_spec import SPEC_DOC, load_spec
from tests.support.proposal import PROPOSAL_ON, customer, setup, share
from veda.kernel import db
from veda.kernel.context import actor, system_context
from veda.modules.customer_proposal import journey, references

pytestmark = PROPOSAL_ON
MONEY_OR_DURATION = re.compile(
    r"₹|\brs\.?\s*\d|\brupees?\b|\b(price|rate|rates|cost|margin)\b|\b\d+\s*(year|years|month|months)\b", re.I
)


def _norm(path: str) -> str:
    return re.sub(r"\.(L|R)\d+", ".*", path)


def _classified(path: str) -> bool:
    p = _norm(path)
    return p in journey.PAGE_FIELDS or any(k.startswith(p + ".") or k.startswith(p + "[]") for k in journey.PAGE_FIELDS)


def test_specifications_are_the_version_active_at_issue_per_line_and_customer_safe(api, factory):
    load_spec(copy.deepcopy(SPEC_DOC))
    c, prop, est, q = setup(api, factory, "3BHK")
    page = customer(api, share(c, q)).get().data
    specs = page["specifications"]
    assert specs["version"] == SPEC_DOC["version"] and specs["lines"]
    wardrobe = [ref for r in page["proposal"]["rooms"] for x in r["lines"] if x["description"].startswith("Wardrobe")
                for ref in [x["ref"]]]  # fmt: skip
    assert any(ref in specs["lines"] for ref in wardrobe)
    text = json.dumps(specs)
    assert not MONEY_OR_DURATION.search(text), MONEY_OR_DURATION.search(text)
    from veda.modules.customer_proposal import projection

    unclassified = sorted(
        p for p in projection.paths({k: v for k, v in page.items() if k != "proposal"}) if not _classified(p)
    )
    assert not unclassified, unclassified
    # a lump-sum or project line without a matching category carries no specification (never generic)
    project = next(r for r in page["proposal"]["rooms"] if r["kind"] == "PROJECT")
    assert not any(x["ref"] in specs["lines"] for x in project["lines"])


def test_a_specification_activated_after_issue_is_not_used(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    load_spec(copy.deepcopy(SPEC_DOC))  # activated after the quotation was issued
    assert customer(api, share(c, q)).get().data["specifications"] is None


def test_a_tampered_specification_is_withheld(api, factory):
    load_spec(copy.deepcopy(SPEC_DOC))
    c, prop, est, q = setup(api, factory, "2BHK")
    from veda.modules.estimator.models import EstimatorCustomerSpec

    with actor(system_context("CLI")), db.unit_of_work(write=True) as s:
        import sqlalchemy as sa

        row = s.execute(sa.select(EstimatorCustomerSpec)).scalar_one()
        row.document = {**row.document, "summary": "Changed after approval."}
    page = customer(api, share(c, q)).get().data
    assert page["specifications"] is None and "Changed after approval" not in json.dumps(page)


def test_media_is_off_unless_catalogue_media_is_served(api, factory):
    c, prop, est, q = setup(api, factory, "2BHK")
    page = customer(api, share(c, q)).get().data
    assert page["media"]["lines"] == {} and all(v is None for v in page["media"]["rooms"].values())
    assert "does not change the scope or the price" in page["media"]["note"]


def test_media_uses_only_approved_images_with_alt_text_and_keeps_labels(api, factory, monkeypatch):
    c, prop, est, q = setup(api, factory, "2BHK")
    from veda.config import settings
    from veda.modules.catalog import compile as catalog_compile
    from veda.modules.catalog import configure, kinds, service

    monkeypatch.setattr(settings(), "catalog_estimator_enabled", True, raising=False)
    monkeypatch.setattr(settings(), "catalog_media_delivery_enabled", True, raising=False)
    img = {"type": "IMAGE", "title": "Wardrobe", "alt": "A two-door laminate wardrobe", "caption": None,
           "label": "Illustrative example", "urls": {"thumb": "/api/v1/public/catalog/media/" + "a" * 64}}  # fmt: skip
    view = {"products": {"wardrobe": {"media": ["m1", "m2", "m3", "m4"]}},
            "media": {"m1": img, "m2": {**img, "alt": None}, "m3": {**img, "type": "EXTERNAL_EMBED"},
                      "m4": {**img, "label": "Design reference", "alt": "Wardrobe interior"}}}  # fmt: skip
    product = SimpleNamespace(variants=[SimpleNamespace(engine_product="WARDROBE", media=())])
    cat = SimpleNamespace(of=lambda kind: {"wardrobe": product} if kind is kinds.Product else {})
    monkeypatch.setattr(configure, "served_catalog", lambda s: (view, 300))
    monkeypatch.setattr(service, "active_release", lambda s: object())
    monkeypatch.setattr(catalog_compile, "load_release", lambda s, release: cat)
    with db.unit_of_work() as s:
        from veda.modules.mtq_commercial.models import Quotation

        found = references.media(s, s.get(Quotation, q["id"]))
    assert found, "the wardrobe lines carry the approved images"
    for images in found.values():
        assert [i["label"] for i in images] == [
            "Illustrative example",
            "Design reference",
        ]  # alt-less and embed skipped
        assert all(i["alt"] for i in images)
    # any failure of the catalogue gives no image at all (never a partial or unchecked one)
    monkeypatch.setattr(configure, "served_catalog", lambda s: (_ for _ in ()).throw(RuntimeError("unavailable")))
    with db.unit_of_work() as s:
        assert references.media(s, s.get(Quotation, q["id"])) == {}
