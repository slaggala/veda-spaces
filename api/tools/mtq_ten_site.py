"""Ten-site validation evidence from files (MTQ B1-T12). Reads, evaluates, writes; no database, no network.

    .venv/bin/python tools/mtq_ten_site.py --reference ref.json --measured measured.json [--events events.json] \
        --database-engine postgresql --out evidence.json

- ``ref.json``: the reference measurements (``veda.modules.mtq.ten_site.Reference``): exactly ten anonymous site ids
  S01..S99, no id twice, the independent reference method and its readings (walls, openings, staircase, levels,
  optional surveyor minutes). For a LIVE dataset it is owner data and stays private.
- ``measured.json``: ``{"S01": {"set": <GET /api/v1/measurement-sets/{id}>, "property": <GET /api/v1/properties/{id}>},
  ...}`` exported from protected staging by a staff user. Only dimensions and verdicts reach the evidence.
- ``events.json``: optional ``{"S05": {"second_surveyor_conflict": true}, "S03": {"offline_retry": true}}``, as
  observed during the visits.

The evidence is bound to its inputs: the generator commit (``VEDA_GIT_SHA`` or ``GITHUB_SHA``, else the checkout's
HEAD, else "unknown"), the database engine the measured sets came from (``--database-engine``), the generation time,
the reference file's SHA-256 and the template version.

Without ``--reference`` the tool writes an UNVALIDATED_NO_REFERENCE document for the dataset id given: nothing is
claimed without reference measurements. Exit 0 when the label is LIVE_VALIDATED or SYNTHETIC_VALIDATED, 1 for any
other label, 2 when an input is malformed (including more than ten sites, a repeated site id, or a measured set for a
site the reference does not list).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from veda.modules.mtq import templates, ten_site  # noqa: E402

VALIDATED = ("LIVE_VALIDATED", "SYNTHETIC_VALIDATED")
ENGINES = ("sqlite", "postgresql", "unknown")


def generator_commit() -> str:
    """The commit that produced the evidence: VEDA_GIT_SHA, GITHUB_SHA, the checkout's HEAD (suffixed "-dirty" when
    tracked files differ from it), or "unknown"."""
    for name in ("VEDA_GIT_SHA", "GITHUB_SHA"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    here = Path(__file__).resolve().parent

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=here, capture_output=True, text=True, timeout=10, check=False)

    try:
        head = git("rev-parse", "HEAD")
        status = git("status", "--porcelain", "--untracked-files=no")
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    sha = head.stdout.strip()
    if head.returncode != 0 or len(sha) != 40:
        return "unknown"
    return f"{sha}-dirty" if status.returncode != 0 or status.stdout.strip() else sha


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--reference", type=Path)
    p.add_argument("--measured", type=Path)
    p.add_argument("--events", type=Path)
    p.add_argument("--dataset-id", default="LIVE-STAGING-B1")
    p.add_argument("--database-engine", choices=ENGINES, default="unknown")
    p.add_argument("--generated-at", help="RFC 3339 time to record (default: now)")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        reference_sha256 = "none: no reference file"
        if a.reference is None:
            reference = ten_site.Reference(dataset_id=a.dataset_id, dataset_kind="LIVE", sites=[])
            measured: dict = {}
        else:
            raw = a.reference.read_bytes()
            reference = ten_site.Reference.model_validate_json(raw)
            reference_sha256 = "sha256:" + hashlib.sha256(raw).hexdigest()
            measured = json.loads(a.measured.read_text()) if a.measured else {}
        events = json.loads(a.events.read_text()) if a.events else {}
        if not isinstance(measured, dict) or not isinstance(events, dict):
            raise ValueError("measured and events are objects keyed by site id")
        provenance = {"generator_commit": generator_commit(), "database_engine": a.database_engine,
                      "generated_at": a.generated_at or "", "reference_sha256": reference_sha256}  # fmt: skip
        evidence = ten_site.evaluate(
            reference, measured, events, template_version=templates.TEMPLATE_VERSION, provenance=provenance
        )
    except (OSError, ValueError, ValidationError, KeyError, TypeError) as err:
        print(f"refused: {type(err).__name__}: {str(err).splitlines()[0]}", file=sys.stderr)
        return 2
    a.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(f"{evidence['dataset_id']} ({evidence['dataset_kind']}): {evidence['label']} "
          f"(gate {evidence['gate_verdict']}, {evidence['sites_evaluated']} of {evidence['sites_referenced']} sites "
          f"evaluated; without a measured set: {evidence['sites_without_a_measured_set'] or 'none'}; "
          f"coverage missing: {evidence['coverage']['missing'] or 'none'})")  # fmt: skip
    return 0 if evidence["label"] in VALIDATED else 1


if __name__ == "__main__":
    raise SystemExit(main())
