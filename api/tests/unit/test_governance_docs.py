"""Governance-document validation (technical-conditions closure): amendment format and status, SHA references,
gates, and the disabled public intake. These checks read the repository only; they approve nothing."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
AMEND = REPO / "docs/proposals/amendments"
REVIEWED = "6ec2e76f156e963c7363c4ad9ce93d0bccb11f41"
NONEXISTENT = "6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41"
STATUS = "PROPOSED, NOT APPROVED"
REQUIRED_FIELDS = (
    "Status", "Certified behavior", "Proposed behavior", "Affected requirements", "Security impact", "Data impact",
    "API impact", "UI impact", "Compatibility impact", "Rollback or forward-fix", "Required tests", "Staging evidence",
    "Production evidence", "Owner decision required", "Failure behavior",
)  # fmt: skip
GOVERNANCE_DOCS = [
    *sorted(AMEND.glob("*.md")),
    AMEND / "amendments.json",
    REPO / "docs/implementation/P0-owner-decision-package.md",
    REPO / "docs/implementation/P0-owner-decision-package.json",
    REPO / "docs/implementation/P0-merge-safety-plan.md",
    REPO / "docs/implementation/P0-final-merge-blocker-matrix.md",
    REPO / "docs/implementation/P0-implementation-report.md",
    REPO / "docs/implementation/P0-open-issues.md",
]


def test_amendments_live_outside_the_certified_tree():
    assert not (REPO / "docs/architecture/amendments").exists()
    assert sorted(p.stem for p in AMEND.glob("AM-*.md")) == sorted(f"AM-{i}" for i in range(1, 14))


@pytest.mark.parametrize("n", range(1, 14))
def test_amendment_format_and_status(n):
    text = (AMEND / f"AM-{n}.md").read_text()
    rows = dict(re.findall(r"^\| ([^|]+?) \| (.+) \|$", text, re.MULTILINE))
    for field in REQUIRED_FIELDS:
        assert field in rows and rows[field].strip() not in ("", "—"), f"AM-{n}: {field}"
    assert rows["Status"] == f"**{STATUS}**"
    assert f"Status: {STATUS}" in text
    assert not re.search(r"\bStatus\b[^|\n]*\|\s*\**APPROVED", text)


def test_amendment_json_status():
    data = json.loads((AMEND / "amendments.json").read_text())
    assert data["status"] == STATUS and data["reviewed_sha"] == REVIEWED
    assert [a["status"] for a in data["amendments"]] == [STATUS] * 13


def test_owner_package_records_no_decision():
    pkg = json.loads((REPO / "docs/implementation/P0-owner-decision-package.json").read_text())
    assert pkg["reviewed_sha"] == REVIEWED
    assert {a["owner_decision_recorded"] for a in pkg["amendments"]} == {"NONE"}
    assert {a["status"] for a in pkg["amendments"]} == {STATUS}
    assert {a["proposed_owner_disposition"] for a in pkg["amendments"]} <= {
        "APPROVE",
        "APPROVE WITH CONDITIONS",
        "REJECT",
        "DEFER",
    }
    assert {g["id"]: g["status"] for g in pkg["gates"]} == {
        "TG-01": "PENDING", "TG-08": "PENDING", "Merge-safety decision": "PENDING", "Production deployment approval": "PENDING",
    }  # fmt: skip
    assert all("AWAITING FORMAL OWNER CONFIRMATION" in o["record_status"] for o in pkg["owner_confirmations"])


def test_sha_references():
    for path in GOVERNANCE_DOCS:
        for line in path.read_text().splitlines():
            if NONEXISTENT in line:
                assert "does not exist" in line, f"{path.name}: cites the nonexistent SHA as if valid"
    assert REVIEWED in (REPO / "docs/implementation/P0-owner-decision-package.md").read_text()
    assert REVIEWED in (REPO / "docs/implementation/P0-merge-safety-plan.md").read_text()


@pytest.mark.skipif(shutil.which("git") is None or not (REPO / ".git").exists(), reason="needs a git checkout")
def test_cited_shas_exist():
    history = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{REVIEWED}^{{commit}}"], capture_output=True)
    if history.returncode != 0:
        pytest.skip("the project history is not available (fresh copy or shallow clone)")
    text = "\n".join(p.read_text() for p in GOVERNANCE_DOCS)
    shas = set(re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", text)) - {NONEXISTENT}
    missing = []
    for sha in shas:
        r = subprocess.run(["git", "-C", str(REPO), "cat-file", "-e", f"{sha}^{{commit}}"], capture_output=True)
        if r.returncode != 0:
            missing.append(sha)
    shallow = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--is-shallow-repository"], capture_output=True, text=True
    )
    if shallow.stdout.strip() == "true":
        pytest.skip(f"shallow clone; unresolved: {missing}")
    assert not missing, missing


def test_gates_pending():
    gates = {
        g["gate_id"]: g["status"]
        for g in json.loads((REPO / "docs/architecture/gate-registry.json").read_text())["gates"]
    }
    assert gates["TG-01"].startswith("Pending") and gates["TG-08"].startswith("Pending")
    issues = {
        i["id"]: i["status"]
        for i in json.loads((REPO / "docs/implementation/P0-open-issues.json").read_text())["items"]
    }
    assert issues["TG-01"].startswith("PENDING") and issues["TG-08"].startswith("PENDING")


def test_public_intake_disabled():
    html = (REPO / "dist/index.html").read_text()
    assert '<meta name="veda-api-base" content="">' in html
    assert '<meta name="veda-turnstile-sitekey" content="">' in html
