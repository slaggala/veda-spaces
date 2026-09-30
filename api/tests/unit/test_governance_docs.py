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


# The owner's decisions of 2026-09-30 (docs/implementation/P0-owner-decision-record.json) are the source of truth:
# every governance artifact must agree with them, and nothing undecided may read as decided.
RECORD = REPO / "docs/implementation/P0-owner-decision-record.json"
EXPECTED_DECISIONS = {
    **dict.fromkeys(("AM-1", "AM-3", "AM-8"), "APPROVED"),
    **dict.fromkeys(("AM-2", "AM-4", "AM-5", "AM-6", "AM-7", "AM-11", "AM-12", "AM-13"), "APPROVED WITH CONDITIONS"),
    **dict.fromkeys(("AM-9", "AM-10"), "DEFERRED TO STAGING / PRODUCTION"),
}


def _status(aid):
    return EXPECTED_DECISIONS.get(aid, STATUS)


@pytest.mark.parametrize("n", range(1, 14))
def test_amendment_format_and_status(n):
    text = (AMEND / f"AM-{n}.md").read_text()
    rows = dict(re.findall(r"^\| ([^|]+?) \| (.+) \|$", text, re.MULTILINE))
    for field in REQUIRED_FIELDS:
        assert field in rows and rows[field].strip() not in ("", "—"), f"AM-{n}: {field}"
    assert rows["Status"] == f"**{_status(f'AM-{n}')}**"
    assert f"Status: {_status(f'AM-{n}')}." in text


def test_decision_record_matches_the_owner_instruction():
    rec = json.loads(RECORD.read_text())
    assert rec["date"] == "2026-09-30"
    assert {k: v["decision"] for k, v in rec["owner_decisions"].items()} == {"OD-2": "APPROVED", "OD-3": "APPROVED"}
    assert {k: v["decision"] for k, v in rec["gates"].items()} == {"TG-01": "APPROVED", "TG-08": "APPROVED"}
    assert all(v["registry_evidence"].startswith("WAIVED by the owner") for v in rec["gates"].values())
    assert rec["evidence_waiver"]["gates"] == ["TG-01", "TG-08"]
    assert rec["merge_safety"]["decision"] == "APPROVED — Option C" and rec["merge_safety"]["executed"] is False
    assert {k: v["decision"] for k, v in rec["amendments"].items()} == EXPECTED_DECISIONS
    assert rec["not_decided"] == []


def test_amendment_json_and_package_agree_with_the_record():
    data = json.loads((AMEND / "amendments.json").read_text())
    assert data["reviewed_sha"] == REVIEWED
    assert {a["id"]: a["status"] for a in data["amendments"]} == {f"AM-{n}": _status(f"AM-{n}") for n in range(1, 14)}
    pkg = json.loads((REPO / "docs/implementation/P0-owner-decision-package.json").read_text())
    assert pkg["reviewed_sha"] == REVIEWED
    assert {a["id"]: a["status"] for a in pkg["amendments"]} == {f"AM-{n}": _status(f"AM-{n}") for n in range(1, 14)}
    gates = {g["id"]: g["status"] for g in pkg["gates"]}
    assert gates["TG-01"] == gates["TG-08"] == "APPROVED"
    assert gates["Merge-safety decision"].startswith("APPROVED — Option C (not executed)")
    assert gates["Production deployment approval"] == "PENDING"
    assert all(o["record_status"].startswith("APPROVED by the owner on 2026-09-30") for o in pkg["owner_confirmations"])


def test_no_undecided_item_reads_as_decided():
    docs = [REPO / f"docs/implementation/{n}" for n in (
        "P0-owner-decision-package.md", "P0-final-merge-blocker-matrix.md", "P0-implementation-deviations.md",
        "P0-implementation-report.md", "P0-merge-safety-plan.md", "P0-merge-readiness-report.md",
        "P0-production-gate-report.md", "P0-gate-status-report.md")] + sorted(AMEND.glob("*.md"))  # fmt: skip
    for path in docs:
        text = path.read_text()
        assert not re.search(r"OD-[23][^|\n]{0,15}\bgiven\b", text), path.name
        assert not re.search(r"AM-4\b[^|\n]{0,40}\b(not decided|NOT DECIDED)", text), path.name
        assert not re.search(r"[Pp]roduction deployment approval[^|\n]{0,10}\|\s*\**APPROVED", text), path.name
        assert not re.search(r"\b(merged|deployed) to (main|production)\b", text), path.name
    readiness = (REPO / "docs/implementation/P0-merge-readiness-report.md").read_text()
    assert "READY FOR CONTROLLED MERGE" in readiness and "NOT READY" not in readiness and "AM-4" in readiness
    assert "nothing has been merged or deployed" in readiness


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
    "ca9845c0dd60280fd19cdc9d41843d8567191801": ("Close P0 document conditions", "head when the owner decisions were recorded"),
    "1be68c2": ("Record P0 consolidated owner decisions", "head when the owner confirmation was synchronized"),
    "13276a017a137c4a86b15fea0306ea2e83ac2729": ("Prepare Veda Spaces for Cloudflare Pages", "live site (main)"),
    "c29690326e11e1cc6a995989f103c33c95118031": ("Merge pull request #1 from slaggala/merge-prep/p0-foundation", "main before the staging bootstrap (AUT-001..003 base)"),
    "fca56da706aa2ad3528d71f8c30dfa46f693cfb7": ("Add staging bootstrap infrastructure as code (AUT-001..003)", "staging bootstrap implementation"),
    "74d0724e1de923ce81db2952bc1a7567cc79b315": ("Remediate AUT-001..003 independent review findings F1-F10", "staging bootstrap first remediation"),
    "e8157f31a9e6df23d79c2b4d79bed896a7b65cb0": ("Close AUT-001..003 final-certification blockers RR-01/02/03/05/07", "staging bootstrap certified with pre-bootstrap conditions"),
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


def test_gate_records():
    """The certified registry is not edited by this workstream (it still reads Pending); the owner's approval of
    TG-01 and TG-08 is carried by the decision record and the register, with the registry evidence waived by the
    owner for merge readiness."""
    gates = {
        g["gate_id"]: g["status"]
        for g in json.loads((REPO / "docs/architecture/gate-registry.json").read_text())["gates"]
    }
    assert gates["TG-01"].startswith("Pending") and gates["TG-08"].startswith("Pending")
    issues = {
        i["id"]: i["status"]
        for i in json.loads((REPO / "docs/implementation/P0-open-issues.json").read_text())["items"]
    }
    assert issues["TG-01"].startswith("APPROVED") and issues["TG-08"].startswith("APPROVED")
    assert "waived by the owner" in issues["TG-01"] and "waived by the owner" in issues["TG-08"]
    report = (REPO / "docs/implementation/P0-gate-status-report.md").read_text()
    other = [g for g in gates if g not in ("TG-01", "TG-08")]
    for gid in other:
        assert f"| {gid} |" in report and "APPROVED" not in report.split(f"| {gid} |", 1)[1].split("\n", 1)[0], gid


def test_public_intake_disabled():
    html = (REPO / "app/e2e/site-release/index.html").read_text()
    assert '<meta name="veda-api-base" content="">' in html
    assert '<meta name="veda-turnstile-sitekey" content="">' in html
