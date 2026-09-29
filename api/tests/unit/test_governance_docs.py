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
REVIEWED = "3f5920b17d21214b39414d080d34246746c8c40d"
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
    assert {a["author_proposed_disposition"] for a in pkg["amendments"]} <= {
        "APPROVE",
        "APPROVE WITH CONDITIONS",
        "REJECT",
        "DEFER",
    }
    assert {g["id"]: g["status"] for g in pkg["gates"]} == {
        "TG-01": "PENDING", "TG-08": "PENDING", "Merge-safety decision": "PENDING", "Production deployment approval": "PENDING",
    }  # fmt: skip
    assert {o["id"] for o in pkg["owner_confirmations"]} == {"OD-2", "OD-3"}
    assert all("AWAITING FORMAL OWNER CONFIRMATION" in o["record_status"] for o in pkg["owner_confirmations"])


def test_no_owner_decision_is_implied_anywhere():
    """DC-07: OD-2/OD-3 are never described as given or decided; no amendment, gate or merge is described as approved."""
    docs = [REPO / f"docs/implementation/{n}" for n in (
        "P0-owner-decision-package.md", "P0-final-merge-blocker-matrix.md", "P0-implementation-deviations.md",
        "P0-implementation-report.md", "P0-merge-safety-plan.md")] + sorted(AMEND.glob("*.md"))  # fmt: skip
    for path in docs:
        text = path.read_text()
        assert not re.search(r"OD-[23][^|\n]{0,15}\bgiven\b", text), path.name
        assert not re.search(r"owner decision OD-[23]\b", text), path.name
        assert not re.search(
            r"\bTG-0[18]\b\W{0,6}(?:status\W{0,4})?(?:is\s+)?\**(?:PASS|PASSED|APPROVED|COMPLETE)\b", text
        ), path.name
    package = (REPO / "docs/implementation/P0-owner-decision-package.md").read_text()
    assert "| TG-01 | **PENDING** |" in package and "| TG-08 | **PENDING** |" in package
    for aid, a in ((a["id"], a) for a in json.loads((AMEND / "amendments.json").read_text())["amendments"]):
        assert a["status"] == STATUS, aid


# --- SHA references (DC-04) --------------------------------------------------------------------------------------
#
# Coverage: every tracked Markdown and JSON document under docs/ except the certified architecture (guarded
# unchanged by its own check) and raw tool output under docs/implementation/evidence/, plus the repository and
# component READMEs, deployment.md and api/deploy/deploy.sh. (The CI workflow's action pins are commits of other
# repositories and are not covered here.) Tokens checked: full 40-hex SHAs and
# abbreviated 7–39-hex tokens that contain both a digit and a letter (hex words without digits, e.g. "deadbeef",
# are not treated as SHAs). Every token must name a commit in KNOWN_COMMITS; the one nonexistent SHA may appear
# only on a line that says it does not exist. With history available, every known commit must exist and carry the
# recorded subject; in CI (fetch-depth 0) missing history is a failure, not a skip. A document citing a new commit
# must add it to KNOWN_COMMITS in the same change, where reviewers see it.

KNOWN_COMMITS = {
    "778aa8fdd918da48340319696ada3ff673e9fb8e": ("Fix R-01 conformance exception matching for non-entity string identifiers", "certified architecture baseline"),
    "9236aa3ade38c33d03a57cf7a064ece29937b109": ("Implement Veda Spaces P0 platform", "first reviewed implementation"),
    "2f6b59a0a6a59dbc41a597dddc7e6512dcd581fe": ("Remove pip from the API runtime image", "re-reviewed implementation"),
    "6ec2e76f156e963c7363c4ad9ce93d0bccb11f41": ("Resolve final P0 implementation merge blockers", "implementation logic (merge blockers)"),
    "3f5920b17d21214b39414d080d34246746c8c40d": ("Close P0 technical certification conditions", "tree of the document-level check"),
    "1aaf019b6c872a075d13e9b3a2a2e9c16489f6f4": ("Add independent Veda Spaces P0 implementation review", "independent review"),
    "15d25a759cfc0342bdca45ba4a9c51550270f305": ("Add targeted P0 implementation re-review", "targeted re-review"),
    "56c20ba992b519daa79aa3802a28343aab8c0b41": ("Add final targeted P0 implementation check", "final targeted check"),
    "093cfa6872c209deb9991910c457afcdb4ad2d04": ("Add P0 document-level technical check", "document-level check"),
    "13276a017a137c4a86b15fea0306ea2e83ac2729": ("Prepare Veda Spaces for Cloudflare Pages", "live site (main)"),
}  # fmt: skip
EXTRA_DOCS = (
    "README.md",
    "deployment.md",
    "api/README.md",
    "app/README.md",
    "api/deploy/deploy.sh",
)
_TOKEN = re.compile(r"(?<![0-9A-Za-z_/.-])[0-9a-f]{7,40}(?![0-9A-Za-z_-])")


def sha_documents() -> list[Path]:
    docs = [
        p
        for p in (REPO / "docs").rglob("*")
        if p.suffix in (".md", ".json")
        and not p.is_relative_to(REPO / "docs/architecture")
        and not p.is_relative_to(REPO / "docs/implementation/evidence")
    ]
    return sorted(docs) + [REPO / d for d in EXTRA_DOCS if (REPO / d).exists()]


def sha_problems(text: str, name: str = "doc") -> list[str]:
    problems = []
    for n, line in enumerate(text.splitlines(), start=1):
        for token in _TOKEN.findall(line):
            if not (re.search(r"[0-9]", token) and re.search(r"[a-f]", token)):
                continue
            if token == NONEXISTENT:
                if "does not exist" not in line:
                    problems.append(f"{name}:{n}: nonexistent SHA cited as if valid")
                continue
            if not any(full.startswith(token) for full in KNOWN_COMMITS):
                problems.append(f"{name}:{n}: unknown SHA {token}")
    return problems


def test_every_cited_sha_is_a_known_commit():
    docs = sha_documents()
    assert len(docs) >= 20
    problems = [p for d in docs for p in sha_problems(d.read_text(), str(d.relative_to(REPO)))]
    assert not problems, problems


@pytest.mark.parametrize(
    "line,expected",
    [
        ("Implementation `6ec2e76f156e963c7363c4ad9ce93d0bccb11f42`.", "unknown SHA"),  # one digit off
        ("at 6ec2e77 the fix", "unknown SHA"),  # bad short SHA
        ("reviewed 0123456789abcdef0123456789abcdef01234567", "unknown SHA"),
        ("the implementation is 6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41", "nonexistent SHA"),
    ],
)
def test_invalid_sha_references_are_caught(line, expected):
    assert any(expected in p for p in sha_problems(line))


def test_valid_and_non_sha_tokens_pass():
    assert sha_problems("baseline 778aa8f, head `3f5920b17d21214b39414d080d34246746c8c40d`, word deadbeef") == []
    assert sha_problems("the brief's 6ec2e76f156e963c7363c4ad9ce93d0bc0b11f41 does not exist") == []


def _git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def test_known_commits_exist_with_the_recorded_subjects():
    import os

    have_git = shutil.which("git") is not None and (REPO / ".git").exists()
    history = have_git and _git("cat-file", "-e", f"{REVIEWED}^{{commit}}").returncode == 0
    if not history:
        if os.environ.get("CI"):
            pytest.fail("CI must check out full history (fetch-depth: 0) for the SHA check (DC-04)")
        pytest.skip("the project history is not available (fresh copy); CI runs this with full history")
    wrong = {}
    for sha, (subject, role) in KNOWN_COMMITS.items():
        r = _git("log", "-1", "--format=%s", sha)
        if r.returncode != 0 or r.stdout.strip() != subject:
            wrong[sha] = (role, r.stdout.strip() or r.stderr.strip())
    assert not wrong, wrong


def test_role_specific_references():
    """A real but wrong SHA in a role is caught: the governance records must name these commits in these roles."""
    pkg = json.loads((REPO / "docs/implementation/P0-owner-decision-package.json").read_text())
    am = json.loads((AMEND / "amendments.json").read_text())
    for record in (pkg, am):
        assert record["reviewed_sha"] == "3f5920b17d21214b39414d080d34246746c8c40d"
        assert record["code_sha"] == "6ec2e76f156e963c7363c4ad9ce93d0bccb11f41"
    assert "56c20ba992b519daa79aa3802a28343aab8c0b41" in pkg["final_check"]
    assert "093cfa6872c209deb9991910c457afcdb4ad2d04" in pkg["document_check"]
    plan = (REPO / "docs/implementation/P0-merge-safety-plan.md").read_text()
    assert "`13276a0`" in plan and "3f5920b17d21214b39414d080d34246746c8c40d" in plan


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
