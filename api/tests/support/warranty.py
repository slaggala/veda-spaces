"""Warranty and service test harness (WSV): a handed-over project of a synthetic customer, the service personas, and
SYNTHETIC warranty policies (never a Veda decision)."""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta
from typing import Any

from tests.support.commercial import ok
from tests.support.mtq import jpeg, photo
from tests.support.portal import PUBLIC, Portal
from tests.support.project import BASE, advance_to

SERVICE = "/api/v1/service-requests"
WARRANTY = "/api/v1/warranty"
FLAGS = dict(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True, customer_portal_enabled=True,
             project_lifecycle_enabled=True, warranty_service_enabled=True)  # fmt: skip
CARE = ("warranty.view", "warranty.manage", "warranty.service.view", "warranty.service.triage",
        "warranty.service.assess", "warranty.service.assign")  # fmt: skip
TECH = ("warranty.service.view", "warranty.service.resolve")
CHECKER = ("warranty.service.view", "warranty.service.verify", "warranty.service.audit")


def india_today() -> str:
    """The business date the server judges visits and reports by (India), never the UTC date."""
    from zoneinfo import ZoneInfo

    from veda.kernel import clock

    return clock.now().astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()


def policy(doc: dict | None) -> None:
    from veda.modules.warranty import policy as wpolicy

    wpolicy.install_for_tests(doc)


def coverage(months: int = 12, *, terms_versions: tuple[str, ...] = ("SYN-T1",), conflict: bool = False) -> dict:
    """A SYNTHETIC WSV-D01 with one HANDOVER class of ``months``."""
    return {"schema": "veda.warranty.policy/1", "version": "WSV-SYNTHETIC-1", "status": "SYNTHETIC_TEST_ONLY",
            "note": "Synthetic test policy; never a Veda decision.",
            "decisions": {"WSV-D01": {"policy_version": "SYN-POLICY-1", "policy_text_sha256": "a" * 64,
                                      "applies_to_terms_versions": list(terms_versions),
                                      "classes": [{"code": "WORKMANSHIP", "label": "Workmanship and fitment",
                                                   "covers": "SYNTHETIC: workmanship and fitment issues.",
                                                   "exclusions": ["SYNTHETIC: misuse."], "duration_months": months,
                                                   "trigger": "HANDOVER", "conflicts_with_statements": conflict}],
                                      "reference": "SYNTHETIC"}}}  # fmt: skip


class Service(Portal):
    def __init__(self, api, factory):
        super().__init__(api, factory)
        self.care = factory.user("ESTIMATOR")
        self.tech = factory.user("ESTIMATOR")
        self.tech2 = factory.user("ESTIMATOR")
        self.checker = factory.user("ESTIMATOR")
        for user, codes in ((self.care, CARE), (self.tech, TECH), (self.tech2, TECH), (self.checker, CHECKER)):
            for code in codes:
                factory.grant(user, code)

    # --- a handed-over project ---------------------------------------------------------------------------------------
    def handed_over(self, key: str = "2BHK", email: str = "owner@example.test", *, days_ago: int = 0):
        from veda.kernel import clock

        prop, _, q = self.accepted(key)
        p = self.book(q, prop)
        self.staff(p)
        p = advance_to(self, self.get(p), "READY_FOR_HANDOVER")
        self.checklist(p)
        self.package(p)
        att = photo(self.as_(self.founder), "property", p["property"]["id"])
        on = (clock.now().date() - timedelta(days=days_ago)).isoformat()
        body = {"handover_on": on, "acknowledgement_reference": "HS-SYN-1", "evidence_attachment_id": att["id"]}
        r = ok(self.as_(self.ops).post(f"{BASE}/{p['id']}/handover", body, if_match=self.get(p)["version"]), 201)
        assert r["outcome"] == "COMPLETED", r
        me = self.invite(prop["lead_id"], email)
        return prop, self.get(p), me

    def register(self, p: dict, user=None, status: int = 201) -> dict:
        r = self.as_(user or self.care).post(f"{WARRANTY}/entitlements", {"project_id": p["id"]})
        assert r.status == status, r
        return r.data

    # --- requests ----------------------------------------------------------------------------------------------------
    def submit(self, me, prop: dict, p: dict, key: str = "req-key-0001", **over) -> Any:
        body = {"project_id": p["id"], "category": "DOOR_OR_DRAWER",
                "description": "The kitchen drawer next to the hob does not close fully", **over}  # fmt: skip
        return me.api.call("POST", f"{PUBLIC}/properties/{prop['id']}/service-requests", body,
                           headers={"X-Veda-Portal": me.token, "Idempotency-Key": key}, anonymous=True)  # fmt: skip

    def req(self, rid: str, user=None) -> dict:
        return ok(self.as_(user or self.care).get(f"{SERVICE}/{rid}"))

    def do(self, rid: str, action: str, body: dict | None = None, user=None, status: int = 200):
        cur = self.req(rid, user or self.care)
        r = self.as_(user or self.care).post(f"{SERVICE}/{rid}/{action}", body or {}, if_match=cur["version"])
        assert r.status == status, r
        return r.data if status in (200, 201) else r

    def customer(self, me, prop: dict, rid: str, action: str, body: dict | None = None, **headers):
        return me.api.call("POST", f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/{action}", body or {},
                           headers={"X-Veda-Portal": me.token, **headers}, anonymous=True)  # fmt: skip

    def covered(self, rid: str, **over) -> dict:
        body = {"outcome": "COVERED", "basis_path": "sources/0/warranty/0",
                "explanation": "This is covered by your warranty; we will fix it.",
                "internal_reason": "Hinge fitment issue within the first year.",
                "period_basis": "Reported within the first year after handover.", **over}  # fmt: skip
        return self.do(rid, "assessments", body)

    def to_in_progress(self, rid: str) -> dict:

        self.do(rid, "triage", {"priority": "NORMAL"})
        self.covered(rid)
        self.do(rid, "assign", {"owner_user_id": self.tech.id})
        return self.do(rid, "visits", {"kind": "SERVICE", "planned_on": india_today(),
                                       "customer_note": "Our technician will visit in the morning."}, user=self.tech,
                       status=201)  # fmt: skip

    def resolved(self, rid: str) -> dict:

        d = self.to_in_progress(rid)
        v = d["visits"][-1]
        self.do(rid, f"visits/{v['id']}/done", {"done_on": india_today(),
                                                 "internal_note": "Hinge re-aligned."}, user=self.tech)  # fmt: skip
        return self.do(rid, "resolve", {"summary": "We re-aligned the drawer channel; it now closes fully."},
                       user=self.tech)  # fmt: skip

    # --- photos ------------------------------------------------------------------------------------------------------
    def photo(self, me, prop: dict, rid: str, key: str = "photo-key-001", complete: bool = True):
        data = jpeg()
        r = self.customer(me, prop, rid, "photos", {"mime_type": "image/jpeg", "byte_size": len(data),
                                                    "sha256": hashlib.sha256(data).hexdigest()},
                          **{"Idempotency-Key": key})  # fmt: skip
        if r.status not in (200, 201):
            return r
        pid = r.data["photo_id"]
        base = f"{PUBLIC}/properties/{prop['id']}/service-requests/{rid}/photos/{pid}"
        put = me.api.call("PUT", f"{base}/content", {"data_base64": base64.b64encode(data).decode()},
                          headers={"X-Veda-Portal": me.token}, anonymous=True)  # fmt: skip
        assert put.status == 200, put
        if complete:
            done = me.api.call("POST", f"{base}/complete", {}, headers={"X-Veda-Portal": me.token}, anonymous=True)
            assert done.status == 200, done
        return r
