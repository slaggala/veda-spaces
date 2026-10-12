"""Catalog V3 activation preparation, phase 1 (PR #75): the evidence and preparation package stays consistent and
non-activating. These checks read the repository only; they approve nothing, decide nothing and enable nothing.

They pin the corrections of the independent review of 2026-10-12: no abbreviated SHA or digest in the activation
documents, one schema version everywhere, the approval template labelled as a preparation-only DRAFT skeleton, the
t4g.large price marked as an estimate pending owner verification, the proposed 2,048 MiB scanner limit marked as not
yet validated, the scanner Compose work kept out of that pull request, and every owner decision still UNDECIDED. The
scanner implementation that followed (CATALOG-V3-scanner-implementation.md) changed the Compose service and the
harness; the two assertions that pinned the PR #75 boundary now pin the implemented state."""

import json
import re
from pathlib import Path

import pytest

from tests.unit.test_governance_docs import KNOWN_COMMITS, sha_problems

REPO = Path(__file__).resolve().parents[3]
CATALOG = REPO / "docs/implementation/catalog"
PHASE1 = CATALOG / "CATALOG-V3-activation-phase1.md"
MATRIX = CATALOG / "CATALOG-V3-activation-phase1-evidence-references.md"
DECISIONS = CATALOG / "CATALOG-V3-activation-owner-decisions.md"
ENABLEMENT = CATALOG / "CATALOG-V3-media-enablement.md"
REVIEW = CATALOG / "CATALOG-V3-review-package.md"
TEMPLATE = CATALOG / "v3-staging-approval.template.json"
ACCEPTANCE = CATALOG / "media-rights-approver-acceptance.template.md"
POLICY = json.loads((REPO / "api/veda/modules/catalog/v3_approval_policy.json").read_text())
ACTIVATION_DOCS = (PHASE1, MATRIX, DECISIONS, CATALOG / "CATALOG-V3-activation-preparation.md", ACCEPTANCE)
NOT_VALIDATED = "PROPOSED 2048 MiB LIMIT NOT YET VALIDATED"
ESTIMATE = "estimated cost pending owner verification"
SKELETON = "preparation-only DRAFT skeleton"
SCHEMA_REF = re.compile(r"veda\.catalog\.v3-staging-approval/(\d+)")
# A hex string cut short with an ellipsis is an abbreviated reference (the review's "eight-character digest prefixes").
ABBREVIATED = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{6,63}…")
FULL_DIGEST = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])")
# Public commit SHAs (the three merges the record cites) and public evidence digests; none is a credential.
MERGES = (
    "c9b1ba35db33328a7d769dba9d1bad483274d63c",  # pragma: allowlist secret (commit SHA: PR #74 merge)
    "246ffeeddf2b9612c6a55be9aa34ce1366c2f5a6",  # pragma: allowlist secret (commit SHA: PR #73 merge)
    "bb4cbf6405610269d9f23e58e4c6c97dbd30b5ce",  # pragma: allowlist secret (commit SHA: PR #69 merge)
)
DIGESTS = {
    "bound plan": "9d7a13a65808be962d62a30b0e6ca0c526f70f998068653fb096551453a37a85",  # pragma: allowlist secret (SHA-256)
    "image": "b9a55479db3c32df3c8e677d67e1bc5d3d1d9940cc6ea265ea039787241162fe",  # pragma: allowlist secret (SHA-256)
    "release evidence": "47977a7f647d8532e6cc59d029fac01a03c5436796fb25cec525ff94cc56580c",  # pragma: allowlist secret (SHA-256)
    "real card": "0e4e1b11fac8ce4da38df31546ccc05f96dff1c454fdeb101fbe19642f04f9f7",  # pragma: allowlist secret (SHA-256)
    "scanner capacity": "ab25630c5f0e8b2934a8181acd9b55dc5a59de21e05c778d8cefc1da05058517",  # pragma: allowlist secret (SHA-256)
}  # fmt: skip


def section(text: str, heading: str) -> str:
    """The body of a Markdown section, up to the next heading of the same or a higher level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading)
    rest = text[start + len(heading) :]
    stop = re.search(rf"^{re.escape(level)} ", rest, re.MULTILINE)
    return rest if stop is None else rest[: stop.start()]


# --- evidence references ---------------------------------------------------------------------------------------------


def test_the_activation_documents_pass_the_governance_sha_check_and_abbreviate_nothing():
    for path in ACTIVATION_DOCS:
        text = path.read_text()
        assert sha_problems(text, path.name) == []
        assert ABBREVIATED.findall(text) == [], path.name


def test_the_phase1_record_cites_the_three_merges_as_allowlisted_full_shas():
    text = PHASE1.read_text()
    for sha in MERGES:
        subject, _role = KNOWN_COMMITS[sha]
        assert sha in text, sha
        assert subject.startswith("Merge pull request #"), subject
    # No 7-hex abbreviation of these commits remains outside a literal artifact name.
    for token in ("`c9b1ba3`", "`246ffee…`", "`246ffee`", "`bb4cbf6`", "c9b1ba35db33…"):
        assert token not in text, token
    for literal in ("veda-api:c9b1ba35db33", "phase0-release-c9b1ba35db33"):
        assert literal in text, literal  # the ECR tag and the evidence label are exact artifact names


def test_the_evidence_reference_matrix_covers_the_sixteen_findings_with_values_the_record_carries():
    matrix = MATRIX.read_text()
    record = PHASE1.read_text()
    rows = [line for line in matrix.splitlines() if re.match(r"^\| \d+ \|", line)]
    assert len(rows) == 16
    values = set(FULL_DIGEST.findall(matrix)) | set(re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", matrix))
    assert len(values) >= 9
    phase0 = (CATALOG / "CATALOG-V3-activation-preparation.md").read_text()
    for value in values:
        assert value in record or value in phase0, value
    for sha in MERGES:
        assert sha in KNOWN_COMMITS and sha in matrix, sha
    assert "0 SHA-allowlist failures" in matrix or "0 failures" in matrix


def test_every_digest_the_dependency_matrix_cites_is_the_full_value_used_elsewhere_in_the_record():
    text = PHASE1.read_text()
    matrix = section(text, "## 8. Activation dependency matrix")
    for digest in DIGESTS.values():
        assert digest in matrix and text.count(digest) >= 2, digest
    assert DIGESTS["scanner capacity"] in DECISIONS.read_text()


# --- schema version --------------------------------------------------------------------------------------------------


def schema_reference_files() -> list[Path]:
    files = [*CATALOG.glob("*.md"), TEMPLATE, *(REPO / "api/tests/fixtures/v3_approval").glob("*.json"),
             REPO / "api/veda/modules/catalog/staging_approval.py",
             *(REPO / "app/scripts").glob("*.mjs"), *(REPO / "infra/terraform/modules/v3-approval").rglob("*.tf"),
             *(REPO / "infra/terraform/modules/v3-approval").rglob("*.hcl"),
             *(REPO / "infra/terraform/envs/staging-core").rglob("*.tf")]  # fmt: skip
    return sorted(p for p in files if p.exists())


def test_every_schema_version_reference_is_the_certified_policy_version():
    expected = POLICY["schema"].rsplit("/", 1)[1]
    assert expected == "2"
    found = {}
    for path in schema_reference_files():
        for n, line in enumerate(path.read_text(errors="ignore").splitlines(), start=1):
            for version in SCHEMA_REF.findall(line):
                found.setdefault(version, []).append(f"{path.relative_to(REPO)}:{n}")
    assert "2" in found and len(found["2"]) >= 20
    # Negative conformance fixtures that the policy must refuse with the SCHEMA code may carry another version.
    cases = json.loads((REPO / "api/tests/fixtures/v3_approval/cases.json").read_text())["cases"]
    negative = {f"api/tests/fixtures/v3_approval/{c['record']}.json" for c in cases if "SCHEMA" in c["codes"]}
    assert negative, "the conformance set refuses a wrong schema version"
    stale = {
        v: [w for w in where if w.rsplit(":", 1)[0] not in negative] for v, where in found.items() if v != expected
    }
    assert {v: w for v, w in stale.items() if w} == {}, stale
    assert f"veda.catalog.v3-staging-approval/{expected}" in section(
        ENABLEMENT.read_text(), "## 10. The V3 staging approval record"
    )
    assert json.loads(TEMPLATE.read_text())["schema"] == POLICY["schema"]


# --- the approval template -------------------------------------------------------------------------------------------


def test_the_template_is_a_labelled_preparation_skeleton_that_pre_empts_no_owner_decision():
    doc = json.loads(TEMPLATE.read_text())
    assert doc["status"] == "DRAFT" and doc["author"] == "[AUTHOR TO FILL]" and doc["approver"] is None
    assert doc["evidence"] == {} and doc["approved_at"] is None and doc["review_by"] is None
    assert doc["release"] == "V3-STAGING-1" and doc["environment"] == "staging"
    scope = doc["approval_scope"]
    # The restrictive default. Flipping it is owner decision AD-6, recorded by the record's author, not by a template.
    assert scope["media_delivery"] is False and scope["public_intake"] is False
    assert scope["three_d"] is False and scope["video"] is False and scope["protected"] is True
    for path, heading in ((ENABLEMENT, "## 10. The V3 staging approval record"),
                          (PHASE1, "## 7. Approval-record template readiness"),
                          (DECISIONS, "## AD-6. Activation record roles and dates")):  # fmt: skip
        body = section(path.read_text(), heading)
        assert SKELETON in body and "media_delivery" in body, path.name
    ad6 = section(DECISIONS.read_text(), "## AD-6. Activation record roles and dates")
    row = next(line for line in ad6.splitlines() if line.startswith("| `approval_scope.media_delivery`"))
    assert "[OWNER TO FILL]" in row and "AD-6" not in row.split("|")[1]
    assert "| Status | **UNDECIDED** |" in ad6


# --- price provenance ------------------------------------------------------------------------------------------------


def test_the_t4g_large_price_is_an_estimate_pending_owner_verification_with_full_provenance():
    text = PHASE1.read_text()
    provenance = section(text, "### 4.5 Price provenance")
    for required in ("USD", "`ap-south-1`", "2026-10-05", "20260925174521", "compute only", "monthly estimate",
                     "not a billed amount", "excludes tax, data transfer", "**not recorded**", "**extrapolation**",
                     "0.0224", "0.0448", "730", "32.70", "**UNDECIDED**"):  # fmt: skip
        assert required in provenance, required
    assert ESTIMATE in provenance.lower()
    recommendation = section(text, "### 4.3 Recommendation to the owner")
    assert ESTIMATE in recommendation.lower() and "**extrapolated**" in recommendation
    # The derived figure of the first revision appears only where it is withdrawn.
    for line in text.splitlines():
        if "32.68" in line:
            assert "withdrawn" in line, line
    decisions = DECISIONS.read_text()
    for heading in ("## AD-2. Host size and capacity reserve for clamd", "## AD-3. Budget revision (O16)"):
        body = section(decisions, heading)
        assert ESTIMATE in body.lower() and "| Status | **UNDECIDED**" in body, heading
        assert "[OWNER TO FILL]" in body
    ad3 = section(decisions, "## AD-3. Budget revision (O16)")
    assert "| New limit | [OWNER TO FILL] |" in ad3 and "**not approved**" in ad3
    assert "`t4g.large` +24.5." not in decisions and "32.68" not in decisions


# --- scanner memory limit and engineering boundary -------------------------------------------------------------------


def test_the_proposed_scanner_limit_is_marked_not_yet_validated_and_matches_the_harness():
    text = PHASE1.read_text()
    assert text.count(NOT_VALIDATED) >= 4
    for heading in ("### 4.3 Recommendation to the owner", "### 5.5 Required reviewed change",
                    "### 5.6 Scanner-engineering scope", "## 8. Activation dependency matrix",
                    "## 10. Remaining activation blockers and verdict"):  # fmt: skip
        body = section(text, heading)
        assert NOT_VALIDATED in body or "NOT YET VALIDATED" in body, heading
    # The phase-1 record describes the harness as it ran then (3 GiB). The scanner implementation reruns it at the
    # limit the deploy bundle configures: the harness default and the Compose default are the same value.
    harness = (REPO / "infra/scanner-validation/validate.sh").read_text()
    compose = (REPO / "api/deploy/docker-compose.yml").read_text()
    assert 'MEMORY="${SCANNER_VALIDATION_MEMORY:-2048m}"' in harness and "--memory 3g" not in harness
    assert "${VEDA_CLAMD_MEM_LIMIT:-2048m}" in compose
    assert "--memory 3g" in text and "limit 3g, not the proposed 2048m" in text
    assert NOT_VALIDATED in REVIEW.read_text() and NOT_VALIDATED in DECISIONS.read_text()


def test_the_scanner_engineering_scope_is_documented_as_a_separate_pull_request_and_not_implemented_here():
    scope = section(PHASE1.read_text(), "### 5.6 Scanner-engineering scope")
    for required in (
        "/init-unprivileged", "1000:1000", "no `cap_add`", "no `privileged`", "01777", "read-only bind mount",
        "clamav-db", "no published host port", "clamdcheck.sh", "FreshClam", "scanner `none`",
        "actual proposed memory limit", "Terraform plan", "az_id", "NOT this one", "**VALID.**", "**NOT DEPLOYABLE.**",
    ):  # fmt: skip
        assert required in scope, required
    for excluded in ("enabling any V3 flag", "media delivery", "public intake", "production"):
        assert excluded in scope.rsplit("What is **not** in that scope", 1)[1], excluded
    compose = (REPO / "api/deploy/docker-compose.yml").read_text()
    # The boundary held for PR #75; the scanner implementation (CATALOG-V3-scanner-implementation.md) then changed the
    # service to the validated non-root profile, and this assertion with it: tests/unit/test_deploy_scanner.py pins it.
    assert "privileged: true" not in compose and "cap_add" not in compose
    assert 'user: "1000:1000"' in compose and "mode=1777" in compose


# --- owner decisions, dependency matrix, acceptance template, review package ----------------------------------------


def test_every_owner_decision_is_still_undecided_and_every_human_field_blank():
    decisions = DECISIONS.read_text()
    for n in range(1, 9):
        body = section(decisions, f"## AD-{n}.")
        assert "| Status | **UNDECIDED**" in body, f"AD-{n}"
        assert "[OWNER TO FILL]" in body and "[DATE TO FILL]" in body, f"AD-{n}"
    assert "**Owner acceptance of any record above: not recorded.**" in decisions
    assert not re.search(r"^\| Status \| \*\*DECIDED", decisions, re.MULTILINE)
    acceptance = ACCEPTANCE.read_text()
    assert "**Status: TEMPLATE. No approver is named; nothing is accepted.**" in acceptance
    assert acceptance.count("[TO FILL") >= 8 and "| Signed by | [TO FILL] |" in acceptance
    assert "`[TO FILL]`" in acceptance.rsplit("SHA-256 of the signed file", 1)[1]


def test_the_dependency_matrix_marks_no_undecided_item_complete_and_keeps_the_verdict():
    text = PHASE1.read_text()
    matrix = section(text, "## 8. Activation dependency matrix")
    rows = [line for line in matrix.splitlines() if line.startswith("| ") and "---" not in line][1:]
    assert len(rows) >= 27
    for row in rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        item, status = cells[0], cells[1]
        if "owner" in status.lower() or "AD-" in item or "AD-" in status:
            assert "COMPLETE" not in status, row
    assert "No undecided human item is marked complete." in matrix
    assert "**Verdict: ACTIVATION PREPARATION BLOCKED.**" in text
    assert "Nothing was activated, enabled, uploaded, approved or changed in production." in text
    assert "APPROVED by the owner" not in text and "OWNER TO FILL" in text


def test_the_review_package_states_the_phase1_position():
    body = section(REVIEW.read_text(), "## Activation preparation status (phase 1 evidence package")
    for required in (
        "**Complete and sanitized**", "Real-card evidence | **Valid**", "**Supports decision-making**",
        "`t4g.medium` | **Not recommended**", "**Recommended, pending a reviewed plan and owner cost approval**",
        "Scanner image | **Valid**", "**Not deployable**", NOT_VALIDATED, "**OWNER TO FILL**", "**DRAFT**",
        "independently reviewed engineering change", "| V3 | **Off**", "| Media delivery | **Off**",
        "| Production | **Unchanged**",
    ):  # fmt: skip
        assert required in body, required
    assert "approves nothing and enables nothing" in body


@pytest.mark.parametrize("path", ACTIVATION_DOCS + (REVIEW, ENABLEMENT))
def test_no_activation_document_reads_as_an_approval(path):
    text = path.read_text()
    assert not re.search(r"\b(V3|media delivery|scanner) (is|was) (enabled|activated|approved)\b", text), path.name
    assert not re.search(r"(?<!NOT )\bAPPROVED by the owner on 2026-10-1[12]\b", text), path.name
