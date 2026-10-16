"""Project lifecycle test harness: SYNTHETIC accepted quotations made through the real B1-B4 API, a SYNTHETIC lifecycle
policy (refused outside tests) and the project personas. Nothing here is a real site, customer, rate or Veda policy.

Personas:

- ``ops``: the operations / project lead persona, which has no repository role: an ESTIMATOR account granted the
  project codes individually at OWN scope (it acts on projects whose team it joins);
- ``approver``: an independent approver (SALES_MANAGER granted ``project.approve_transition``);
- ``manager``: SALES_MANAGER (books projects, assigns the first team);
- ``designer``, ``surveyor``: their repository roles (OWN: member projects only);
- ``outsider``: a DESIGNER who is on no project's team;
- ``quality``: the independent quality persona (PEX): an ESTIMATOR granted ``project.view``, ``project.manage_qc`` and
  ``project.verify_snag`` at OWN scope, a team member, who verifies what ops fixed.

Project delivery (PEX): the harness installs a SYNTHETIC delivery policy with no commercial condition (PEX-D02 NONE)
and no customer portal actions (PEX-D01 null); tests of those decisions install their own (``delivery``).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.support.commercial import Commercial, approved_estimate, install_full_policy, load_card, ok, step
from veda.modules.project import lifecycle

ON = pytest.mark.settings(mtq_site_enabled=True, mtq_estimation_enabled=True, mtq_quotation_enabled=True,
                          project_lifecycle_enabled=True)  # fmt: skip
BASE = "/api/v1/projects"
OPS_CODES = ("project.view", "project.assign_team", "project.manage_stage", "project.complete_checklist",
             "project.checklist.not_applicable", "project.manage_milestone", "project.raise_blocker",
             "project.resolve_blocker", "project.manage_site_readiness", "project.manage_qc", "project.manage_snag",
             "project.complete_handover", "project.view_commercial_baseline", "project.view_audit",
             "project.manage_work")  # fmt: skip
QUALITY_CODES = ("project.view", "project.manage_qc", "project.verify_snag")
FOUR_EYES = ("SNAGGING>READY_FOR_HANDOVER",)
QC_REQUIRED = ("DIMENSIONS_AND_ALIGNMENT", "FINISH_AND_SURFACES")


def synthetic_policy(**decisions: Any) -> dict:
    """Every engine-read slot decided, SYNTHETIC: the current definition approved, the default gates adopted as the
    owner's gates, four-eyes on the move to READY_FOR_HANDOVER, two QC categories, both handover evidences."""
    d = lifecycle.current()
    doc: dict[str, Any] = {
        "schema": "veda.project.lifecycle-policy/1", "version": "PLB-SYNTHETIC-1", "status": "SYNTHETIC_TEST_ONLY",
        "note": "Synthetic test policy; never a Veda decision.",
        "decisions": {
            "PLB-OD-01": {"lifecycle_version": d.version, "lifecycle_sha256": d.sha256, "reference": "SYNTHETIC"},
            "PLB-OD-02": {"lifecycle_version": d.version,
                          "transitions": {t.key: list(t.default_gates) for t in d.transitions}},
            "PLB-OD-03": {"lifecycle_version": d.version, "transitions": list(FOUR_EYES)},
            "PLB-OD-04": None, "PLB-OD-05": None, "PLB-OD-06": None, "PLB-OD-07": None,
            "PLB-OD-08": {"required_categories": list(QC_REQUIRED)},
            "PLB-OD-09": {"acknowledgement_required": True, "evidence_required": True},
            "PLB-OD-10": None, "PLB-OD-11": None, "PLB-OD-12": None, "PLB-OD-13": None,
        },
    }  # fmt: skip
    for k, v in decisions.items():
        doc["decisions"][k.replace("_", "-")] = v
    return doc


def delivery(pex_d01: dict | None = None, pex_d02: str | None = "NONE") -> None:
    """A SYNTHETIC project-delivery policy (never a Veda decision): PEX-D02 as ``pex_d02`` (None: undecided)."""
    from veda.modules.project import delivery_policy

    delivery_policy.install_for_tests({
        "schema": "veda.project.delivery-policy/1", "version": "PEX-SYNTHETIC-1", "status": "SYNTHETIC_TEST_ONLY",
        "note": "Synthetic test policy; never a Veda decision.",
        "decisions": {"PEX-D01": {**pex_d01, "reference": "SYNTHETIC"} if pex_d01 else None,
                      "PEX-D02": {"condition": pex_d02, "reference": "SYNTHETIC"} if pex_d02 else None},
    })  # fmt: skip


def install(doc: dict | None) -> None:
    from veda.modules.project import policy

    policy.install_for_tests(copy.deepcopy(doc) if doc is not None else None)


@pytest.fixture
def lifecycle_policy(app):
    install(synthetic_policy())
    yield
    install(None)


class Projects:
    """The commercial team (to make accepted quotations) plus the project personas."""

    def __init__(self, api, factory):
        install_full_policy()
        load_card()
        self.api, self.factory = api, factory
        self.c = Commercial(api, factory)
        self.manager = self.c.manager
        self.ops = factory.user("ESTIMATOR")
        for code in OPS_CODES:
            factory.grant(self.ops, code, scope="OWN")
        self.approver = factory.user("SALES_MANAGER", mfa=True)
        factory.grant(self.approver, "project.approve_transition")
        self.founder = self.c.founder
        self.designer = factory.user("DESIGNER")
        self.surveyor = factory.user("SURVEYOR")
        self.outsider = factory.user("DESIGNER")
        self.quality = factory.user("ESTIMATOR")
        for code in QUALITY_CODES:
            factory.grant(self.quality, code, scope="OWN")
        delivery()

    def as_(self, user):
        if getattr(user, "token", None) is None:
            self.factory.login(self.api, user)
        else:
            self.api.token = user.token
        return self.api

    # --- commercial ----------------------------------------------------------------------------------------------------
    def quotation(self, key: str = "2BHK", *, optional: str = "EXCLUDED") -> tuple[dict, dict, dict]:
        """(property, estimate, quotation DRAFT)."""
        prop, est = approved_estimate(self.c, key, optional=optional)
        q = ok(self.c.as_(self.c.estimator).post(f"/api/v1/cost-estimates/{est['id']}/quotations", {}), 201)
        return prop, est, q

    def issued(self, key: str = "2BHK") -> tuple[dict, dict, dict]:
        prop, est, q = self.quotation(key)
        step(self.c, q, "submit", self.c.estimator)
        step(self.c, q, "approve", self.c.manager)
        q = ok(step(self.c, q, "issue", self.c.manager))
        return prop, est, q

    def accepted(self, key: str = "2BHK", method: str = "SIGNED_COPY") -> tuple[dict, dict, dict]:
        prop, est, q = self.issued(key)
        q = ok(step(self.c, q, "decision", self.c.sales, {"decision": "ACCEPTED", "method": method}))
        return prop, est, q

    def changed_estimate(self, prop: dict) -> dict:
        """The customer adds a TV unit in Bedroom 2 (a priced change to the accepted scope)."""
        api = self.c.as_(self.c.estimator)
        spaces = {sp["label"]: sp for sp in ok(api.get(f"/api/v1/properties/{prop['id']}/spaces"))}
        ok(api.post(f"/api/v1/properties/{prop['id']}/requirements",
                    {"space_id": spaces["Bedroom 2"]["id"], "requirement_type_code": "TV_UNIT",
                     "source_code": "CUSTOMER_REQUEST", "necessity_code": "RECOMMENDED"}), 201)  # fmt: skip
        scope = self.c.fill_staff_inputs(self.c.draft_scope(prop))
        tv = next(i for i in scope["items"] if i["item_type_code"] == "TV_UNIT" and i["space_label"] == "Bedroom 2")
        ok(api.patch(f"/api/v1/scope-items/{tv['id']}", {"dimension_overrides": {"WIDTH": 6},
                     "override_reason": "No TV wall tagged; width from the design"}, if_match=tv["version"]))  # fmt: skip
        boq = self.c.boq(self.c.confirm(scope))
        ok(self.c.review(boq))
        est = ok(api.post(f"/api/v1/boqs/{boq['id']}/cost-estimates", {"tier_code": "ESSENTIAL"}), 201)
        return ok(
            self.c.as_(self.c.manager).post(f"/api/v1/cost-estimates/{est['id']}/approve", if_match=est["version"])
        )

    def variation(self, base: dict, prop: dict) -> dict:
        est = self.changed_estimate(prop)
        return ok(self.c.as_(self.c.sales).post(f"/api/v1/quotations/{base['id']}/variations",
                                                {"cost_estimate_id": est["id"]}), 201)  # fmt: skip

    def accept_variation(self, v: dict) -> dict:
        step(self.c, v, "submit", self.c.sales)
        step(self.c, v, "approve", self.c.manager)
        v = ok(step(self.c, v, "issue", self.c.manager))
        return ok(step(self.c, v, "decision", self.c.sales, {"decision": "ACCEPTED", "method": "STAFF_RECORDED"}))

    # --- projects ------------------------------------------------------------------------------------------------------
    def book(self, q: dict, prop: dict, user=None, status: int = 201, **headers):
        r = self.as_(user or self.manager).post(BASE, {"quotation_id": q["id"], "property_id": prop["id"]},
                                                headers=headers or None)  # fmt: skip
        assert r.status == status, r
        return r.data if status in (200, 201) else r

    def token(self, user) -> str:
        if getattr(user, "token", None) is None:
            self.factory.login(self.api, user, set_default=False)
        return user.token

    def get(self, p: dict | str, user=None) -> dict:
        """A read that never changes whom the shared client acts as (it is often evaluated as an argument)."""
        pid = p if isinstance(p, str) else p["id"]
        return ok(self.api.get(f"{BASE}/{pid}", token=self.token(user or self.founder)))

    def team(self, p: dict, user, responsibility: str, by=None, status: int = 200, reason: str | None = None):
        cur = self.get(p)
        body = {"user_id": user.id, "responsibility": responsibility, **({"reason": reason} if reason else {})}
        r = self.as_(by or self.manager).post(f"{BASE}/{p['id']}/team", body, if_match=cur["version"])
        assert r.status == status, r
        return r.data if status == 200 else r

    def staff(self, p: dict) -> dict:
        """The default team: ops owns PROJECT, SITE, QUALITY and HANDOVER, the designer owns DESIGN, the surveyor is a
        member, and the manager is the commercial owner."""
        for user, resp in ((self.ops, "PROJECT"), (self.ops, "SITE"), (self.ops, "QUALITY"), (self.ops, "HANDOVER"),
                           (self.designer, "DESIGN"), (self.surveyor, "MEMBER"), (self.manager, "COMMERCIAL"),
                           (self.quality, "MEMBER")):  # fmt: skip
            self.team(p, user, resp)
        return self.get(p)

    def transition(self, p: dict, to: str, user=None, status: int = 201, reason: str | None = None):
        cur = self.get(p)
        r = self.as_(user or self.ops).post(f"{BASE}/{p['id']}/transitions",
                                            {"to_stage": to, **({"reason": reason} if reason else {})},
                                            if_match=cur["version"])  # fmt: skip
        assert r.status == status, r
        return r.data if status in (200, 201) else r

    def checklist(self, p: dict, stage: str | None = None, *, user=None, not_applicable: tuple[str, ...] = ()):
        """Complete every open item of ``stage`` (default: the current stage)."""
        cur = self.get(p)
        stage = stage or cur["stage"]["code"]
        group = next(g for g in cur["checklist"] if g["stage_code"] == stage)
        for item in group["items"]:
            if item["state"] != "OPEN":
                continue
            body = ({"state": "NOT_APPLICABLE", "not_applicable_reason": "Not part of this synthetic job"}
                    if item["code"] in not_applicable else {"state": "DONE", "note": "Done (synthetic)"})  # fmt: skip
            fresh = self._item(p, item["id"])
            ok(self.as_(user or self.ops).post(f"{BASE}/{p['id']}/checklist/{item['id']}/complete", body,
                                               if_match=fresh["version"]))  # fmt: skip
        return self.get(p)

    def _item(self, p: dict, item_id: str) -> dict:
        cur = self.get(p)
        return next(i for g in cur["checklist"] for i in g["items"] if i["id"] == item_id)

    def advance(self, p: dict, to: str) -> dict:
        """Complete the current stage's checklist and move to ``to`` (no approval step)."""
        self.checklist(p)
        r = self.transition(p, to)
        assert r["outcome"] == "COMPLETED", r["transition"]["blockers"]
        return r["project"]

    def package(self, p: dict, user=None, status: int = 201):
        """Prepare the handover package (READY_FOR_HANDOVER, every gate but the evidence met)."""
        r = self.as_(user or self.ops).post(f"{BASE}/{p['id']}/handover-package", {}, if_match=self.get(p)["version"])
        assert r.status == status, r
        return r.data if status == 201 else r

    def snag_through(self, p: dict, snag_id: str, to: str = "RESOLVED") -> dict:
        """Take a snag through its flow: ops owns and fixes it, the quality persona verifies (and closes)."""
        url = f"{BASE}/{p['id']}/snags/{snag_id}"

        def cur() -> dict:
            return next(x for x in self.get(p)["snags"] if x["id"] == snag_id)

        if cur()["owner"] is None:
            ok(self.as_(self.ops).patch(url, {"owner_user_id": self.ops.id}, if_match=cur()["version"]))
        steps = [("IN_PROGRESS", self.ops, None), ("READY_FOR_RECHECK", self.ops, "Fixed (synthetic)"),
                 ("RESOLVED", self.quality, "Rechecked and verified (synthetic)"), ("CLOSED", self.quality, None)]  # fmt: skip
        for status, user, note in steps:
            if cur()["status"] == to:
                break
            if status not in cur()["allowed_next"]:
                continue
            ok(self.as_(user).post(f"{url}/status", {"status": status, **({"note": note} if note else {})},
                                   if_match=cur()["version"]))  # fmt: skip
        return cur()

    def ready_site(self, p: dict, user=None) -> dict:
        cur = self.get(p)
        if not cur["site_readiness"]:
            ok(self.as_(user or self.ops).post(f"{BASE}/{p['id']}/site-readiness",
                                               {"kind": "READINESS", "category": "ACCESS",
                                                "label": "Lift access for material"}), 201)  # fmt: skip
            cur = self.get(p)
        for r in cur["site_readiness"]:
            if not r["satisfied"]:
                ok(self.as_(user or self.ops).patch(f"{BASE}/{p['id']}/site-readiness/{r['id']}", {"status": "READY"},
                                                    if_match=r["version"]))  # fmt: skip
        return self.get(p)


ORDER = ("DESIGN_FINALISATION", "SCOPE_FROZEN", "SITE_READINESS", "PRODUCTION_READINESS", "IN_PRODUCTION",
         "READY_FOR_INSTALLATION", "INSTALLATION", "QUALITY_CHECK", "SNAGGING", "READY_FOR_HANDOVER")  # fmt: skip


def advance_to(t: Projects, p: dict, stage: str, *, qc: tuple[str, ...] = QC_REQUIRED) -> dict:
    """Move a staffed project stage by stage to ``stage`` (needs a policy without four-eyes on the moves crossed). Before
    SNAGGING it records PASS for ``qc``."""
    current = t.get(p)["stage"]["code"]
    for to in ORDER[ORDER.index(current) + 1 if current in ORDER else 0 :]:
        if to == "PRODUCTION_READINESS":
            t.ready_site(p)
        if to == "SNAGGING":
            for cat in qc:
                ok(t.as_(t.ops).post(f"{BASE}/{p['id']}/qc-checks", {"category": cat, "result": "PASS"}), 201)
        p = t.advance(p, to)
        if to == stage:
            break
    return t.get(p)


def no_four_eyes() -> dict:
    return synthetic_policy(PLB_OD_03={"lifecycle_version": lifecycle.current().version, "transitions": []})


def race(app, monkeypatch, first_token: str, first, second, *, module=None, name: str = "require"):
    """Run ``first(client)`` paused right after its permission check (before the project lock) while ``second()`` runs;
    the first resumes once the second has returned or is waiting for a lock the first owns (``tests.support.race``).
    Returns (first's response, second's result)."""
    import threading

    from tests.support.api import ApiClient
    from tests.support.race import Hold
    from veda.modules.project import access

    module = module or access
    a = ApiClient(app.test_client())
    a.token = first_token
    hold = Hold()
    threads: dict[str, threading.Thread] = {}
    original = getattr(module, name)

    def wrapped(*args, **kw):
        result = original(*args, **kw)
        if threading.current_thread() is threads.get("first") and not hold.reached.is_set():
            hold.wait()
        return result

    monkeypatch.setattr(module, name, wrapped)
    out: dict = {}

    def run_first():
        out["first"] = first(a)

    def run_second():
        assert hold.reached.wait(timeout=20), "the first request never reached its pause"
        out["second"] = second()
        hold.done()

    threads["first"], threads["second"] = threading.Thread(target=run_first), threading.Thread(target=run_second)
    with hold.racing(held=threads["first"], other=threads["second"]):
        for th in threads.values():
            th.start()
        for th in threads.values():
            th.join(timeout=60)
    monkeypatch.setattr(module, name, original)
    assert "first" in out and "second" in out, out
    for r in out.values():
        assert getattr(r, "status", 200) < 500, r
    return out["first"], out["second"]
