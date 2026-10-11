"""The V3 staging approval record (targeted media enablement, Phase 11).

`api/veda/modules/catalog/approved/v3-staging-approval.json` is the owner's record that V3 may be activated on protected
staging. It references by digest every piece of evidence the activation rests on. It does not itself enable anything.
V3 needs, in addition:
- the catalog_v3 flags in infra/config/staging-platform.json, bound to the record's SHA-256;
- the staging build (`app/scripts/staging-build.mjs`), which repeats these checks;
- the API's own production refusal.

Statuses are DRAFT, IN_REVIEW, APPROVED and REVOKED. Only APPROVED satisfies the gate, and only while it is current:
- `review_by` has not been reached (at most 90 days after `approved_at`);
- `expires_at` has not been reached, or an explicit `non_expiring_decision` was recorded instead;
- it is not revoked.

The approver must not be the author (four-eyes review). The record is for protected staging only: the schema refuses
any other environment. The same rules run at plan (Terraform), build (staging-build.mjs), deployment preflight
(deploy.sh) and on every public V3 request on staging (configure._approved_for_this_environment).

No record is committed until the owner approves one: the template in docs/implementation/catalog/ is DRAFT with empty
evidence, and no owner value or date is ever filled in automatically.

    python -m veda.modules.catalog.staging_approval <record.json>   # exit 0 only for a current APPROVED record
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RECORD = Path(__file__).resolve().parent / "approved" / "v3-staging-approval.json"
SCHEMA = "veda.catalog.v3-staging-approval/2"

# The evidence an approval rests on, by name. Commits are git SHAs; everything else is the SHA-256 of an artifact
# kept where its procedure says (never its content: no rates, no personal data, no media).
GIT_EVIDENCE = ("application_commit", "pr69_merge")
DIGEST_EVIDENCE = (
    "application_certification", "real_card_evidence", "infrastructure_plan", "infrastructure_apply",
    "scanner_capacity", "scanner_decision", "media_bucket", "iam", "ssm_settings", "csp", "media_smoke_test",
    "promise_owner_approval", "media_rights_approver",
)  # fmt: skip
REQUIRED_EVIDENCE = (*GIT_EVIDENCE, *DIGEST_EVIDENCE)
MAX_REVIEW_DAYS = 90  # an approval is reviewed at least every 90 days (owner may set an earlier date)

Name = Annotated[str, Field(min_length=1, max_length=120)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
GitSha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Ref = Annotated[str, Field(min_length=8, max_length=300)]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Evidence(_Model):
    sha256: Sha256 | None = None  # the artifact's SHA-256
    git_sha: GitSha | None = None  # for commits
    reference: Ref  # where it is kept (a private path, a workflow run, a PR), never the content


class ApprovalScope(_Model):
    version: Literal["v3"]
    protected: Literal[True]  # behind Cloudflare Access (protected staging), never public
    public_intake: Literal[False]
    media_delivery: bool
    three_d: Literal[False]
    video: Literal[False]


class V3StagingApproval(_Model):
    schema_: Literal["veda.catalog.v3-staging-approval/2"] = Field(alias="schema")
    status: Literal["DRAFT", "IN_REVIEW", "APPROVED", "REVOKED"]
    environment: Literal["staging"]  # a production record cannot be written: the schema refuses it
    release: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{2,31}$")]  # the catalog release it covers
    author: Name
    approver: Name | None = None
    approved_at: date | None = None
    review_by: date | None = None  # mandatory review date of an approval (at most MAX_REVIEW_DAYS after approval)
    expires_at: date | None = None  # null only with an explicit non-expiring owner decision
    non_expiring_decision: Annotated[str, Field(min_length=20, max_length=300)] | None = None
    revoked_at: date | None = None
    revocation_reason: Annotated[str, Field(min_length=10, max_length=300)] | None = None
    approval_scope: ApprovalScope
    evidence: dict[str, Evidence]

    @model_validator(mode="after")
    def _gate(self):
        unknown = set(self.evidence) - set(REQUIRED_EVIDENCE)
        if unknown:
            raise ValueError(f"unknown evidence: {', '.join(sorted(unknown))}")
        if self.status in ("APPROVED", "REVOKED"):
            missing = [k for k in REQUIRED_EVIDENCE if k not in self.evidence]
            if missing:
                raise ValueError(
                    f"an approved record references every piece of evidence; missing: {', '.join(missing)}"
                )
            for k in GIT_EVIDENCE:
                if not self.evidence[k].git_sha:
                    raise ValueError(f"evidence {k} is a git commit SHA")
            for k in DIGEST_EVIDENCE:
                if not self.evidence[k].sha256:
                    raise ValueError(f"evidence {k} needs the SHA-256 of its artifact")
            if not self.approver or not self.approved_at:
                raise ValueError("an approved record names its approver and approval date")
            if _same(self.approver, self.author):
                raise ValueError("the approver is not the author (four-eyes review)")
            if "TO FILL" in self.approver.upper() or "TO FILL" in self.author.upper():
                raise ValueError("a placeholder is not an approver or an author")
            if not self.review_by or not (
                self.approved_at < self.review_by <= self.approved_at + timedelta(days=MAX_REVIEW_DAYS)
            ):
                raise ValueError(f"an approved record has a review date within {MAX_REVIEW_DAYS} days of its approval")
            if (self.expires_at is None) == (self.non_expiring_decision is None):
                raise ValueError(
                    "an approved record has an expiry date or an explicit non-expiring owner decision, exactly one"
                )
            if self.expires_at is not None and self.expires_at <= self.approved_at:
                raise ValueError("an approval expires after it is given")
        if self.status == "REVOKED" and not (self.revoked_at and self.revocation_reason):
            raise ValueError("a REVOKED record says when and why")
        if self.status != "REVOKED" and (self.revoked_at or self.revocation_reason):
            raise ValueError("only a REVOKED record carries a revocation")
        return self


def _same(a: str, b: str) -> bool:
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


def check(document: dict) -> V3StagingApproval:
    """The record, validated; raises ValueError when it is malformed or inconsistent."""
    if document.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} record")
    return V3StagingApproval.model_validate(document)


def problems(document: dict | None, *, today: date | None = None) -> list[str]:
    """Why a record does not authorise V3 on protected staging today (empty when it does). Checked by plan, build,
    deployment preflight and, while the catalog runs, by every public request (so expiry is never silent)."""
    if document is None:
        return ["no V3 staging approval record"]
    try:
        record = check(document)
    except ValueError as err:
        return [str(err).splitlines()[0][:300]]
    today = today or date.today()
    out = []
    if record.status != "APPROVED":
        out.append(f"the record is {record.status}")
    if record.review_by and record.review_by <= today:
        out.append(f"the approval review date {record.review_by.isoformat()} has been reached")
    if record.expires_at and record.expires_at <= today:
        out.append(f"the approval expired on {record.expires_at.isoformat()}")
    if record.approved_at and record.approved_at > today:
        out.append("the approval date is in the future")
    return out


def approves(document: dict | None, *, today: date | None = None) -> bool:
    """True only for a valid, current APPROVED record (what the staging gates accept)."""
    return not problems(document, today=today)


def load(path: Path = RECORD) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else RECORD
    found = problems(load(path))
    if found:
        print(f"refused: {'; '.join(found)}")
        return 1
    print("APPROVED and current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
