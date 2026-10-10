"""The V3 staging approval record (targeted media enablement, Phase 11).

`api/veda/modules/catalog/approved/v3-staging-approval.json` is the owner's record that V3 may be activated on protected
staging. It references by digest every piece of evidence the activation rests on. It does not itself enable anything.
V3 needs, in addition:
- the catalog_v3 flags in infra/config/staging-platform.json, bound to the record's SHA-256;
- the staging build (`app/scripts/staging-build.mjs`), which repeats these checks;
- the API's own production refusal.

Statuses are DRAFT, IN_REVIEW, APPROVED and REVOKED. Only APPROVED satisfies the gate. The approver must not be the
author (four-eyes review). No record is committed until the owner approves one: the template in
docs/implementation/catalog/ is DRAFT with empty evidence.

    python -m veda.modules.catalog.staging_approval <record.json>   # exit 0 only for a valid APPROVED record
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RECORD = Path(__file__).resolve().parent / "approved" / "v3-staging-approval.json"
SCHEMA = "veda.catalog.v3-staging-approval/1"

# The evidence an approval rests on, by name. Commits are git SHAs; everything else is the SHA-256 of an artifact
# kept where its procedure says (never its content: no rates, no personal data, no media).
GIT_EVIDENCE = ("application_commit", "pr69_merge")
DIGEST_EVIDENCE = (
    "application_certification", "real_card_evidence", "infrastructure_plan", "infrastructure_apply",
    "scanner_capacity", "scanner_decision", "media_bucket", "iam", "ssm_settings", "csp", "media_smoke_test",
    "promise_owner_approval", "media_rights_approver",
)  # fmt: skip
REQUIRED_EVIDENCE = (*GIT_EVIDENCE, *DIGEST_EVIDENCE)

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


class Scope(_Model):
    environments: tuple[Literal["staging"], ...] = Field(min_length=1, max_length=1)
    version: Literal["v3"]
    public_intake: Literal[False]
    media_delivery: bool
    three_d: Literal[False]
    video: Literal[False]


class V3StagingApproval(_Model):
    schema_: Literal["veda.catalog.v3-staging-approval/1"] = Field(alias="schema")
    status: Literal["DRAFT", "IN_REVIEW", "APPROVED", "REVOKED"]
    release: Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9._-]{2,31}$")]  # the catalog release it covers
    author: Name
    approver: Name | None = None
    approved_on: date | None = None
    revoked_on: date | None = None
    revocation_reason: Annotated[str, Field(min_length=10, max_length=300)] | None = None
    scope: Scope
    evidence: dict[str, Evidence]

    @model_validator(mode="after")
    def _gate(self):
        unknown = set(self.evidence) - set(REQUIRED_EVIDENCE)
        if unknown:
            raise ValueError(f"unknown evidence: {', '.join(sorted(unknown))}")
        if self.status == "APPROVED":
            missing = [k for k in REQUIRED_EVIDENCE if k not in self.evidence]
            if missing:
                raise ValueError(
                    f"an APPROVED record references every piece of evidence; missing: {', '.join(missing)}"
                )
            for k in GIT_EVIDENCE:
                if not self.evidence[k].git_sha:
                    raise ValueError(f"evidence {k} is a git commit SHA")
            for k in DIGEST_EVIDENCE:
                if not self.evidence[k].sha256:
                    raise ValueError(f"evidence {k} needs the SHA-256 of its artifact")
            if not self.approver or not self.approved_on:
                raise ValueError("an APPROVED record names its approver and approval date")
            if _same(self.approver, self.author):
                raise ValueError("the approver is not the author (four-eyes review)")
            if "OWNER TO FILL" in self.approver.upper() or "OWNER TO FILL" in self.author.upper():
                raise ValueError("a placeholder is not an approver")
        if self.status == "REVOKED" and not (self.revoked_on and self.revocation_reason):
            raise ValueError("a REVOKED record says when and why")
        return self


def _same(a: str, b: str) -> bool:
    return " ".join(a.casefold().split()) == " ".join(b.casefold().split())


def check(document: dict) -> V3StagingApproval:
    """The record, validated; raises ValueError when it is malformed or inconsistent."""
    if document.get("schema") != SCHEMA:
        raise ValueError(f"not a {SCHEMA} record")
    return V3StagingApproval.model_validate(document)


def approves(document: dict) -> bool:
    """True only for a valid APPROVED record (what the staging gate accepts)."""
    try:
        return check(document).status == "APPROVED"
    except ValueError:
        return False


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else RECORD
    try:
        record = check(json.loads(path.read_text()))
    except (OSError, ValueError) as err:
        print(f"refused: {str(err).splitlines()[0][:300]}")
        return 1
    print(f"{record.status}: release {record.release}")
    return 0 if record.status == "APPROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
