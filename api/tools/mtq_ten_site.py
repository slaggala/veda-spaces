"""Ten-site validation evidence from files (MTQ B1-T12). Reads, evaluates, writes; no database, no network.

    .venv/bin/python tools/mtq_ten_site.py --reference ref.json --measured measured.json [--events events.json] \
        --out evidence.json

- ``ref.json``: the reference measurements (``veda.modules.mtq.ten_site.Reference``): anonymous site ids S01..S20,
  the independent reference method and its readings. For a LIVE dataset it is owner data and stays private.
- ``measured.json``: ``{"S01": {"set": <GET /api/v1/measurement-sets/{id}>, "property": <GET /api/v1/properties/{id}>},
  ...}`` exported from protected staging by a staff user. Only dimensions and verdicts reach the evidence.
- ``events.json``: optional ``{"S05": {"second_surveyor_conflict": true}, "S03": {"offline_retry": true}}``, as
  observed during the visits.

Without ``--reference`` the tool writes an UNVALIDATED_NO_REFERENCE document for the dataset id given: nothing is
claimed without reference measurements. Exit 0 when the label is LIVE_VALIDATED or SYNTHETIC_VALIDATED, 1 for any
other label, 2 when an input is malformed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

from veda.modules.mtq import templates, ten_site  # noqa: E402

VALIDATED = ("LIVE_VALIDATED", "SYNTHETIC_VALIDATED")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--reference", type=Path)
    p.add_argument("--measured", type=Path)
    p.add_argument("--events", type=Path)
    p.add_argument("--dataset-id", default="LIVE-STAGING-B1")
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.reference is None:
            reference = ten_site.Reference(dataset_id=a.dataset_id, dataset_kind="LIVE", sites=[])
            measured: dict = {}
        else:
            reference = ten_site.Reference.model_validate_json(a.reference.read_text())
            measured = json.loads(a.measured.read_text()) if a.measured else {}
        events = json.loads(a.events.read_text()) if a.events else {}
        if not isinstance(measured, dict) or not isinstance(events, dict):
            raise ValueError("measured and events are objects keyed by site id")
        evidence = ten_site.evaluate(reference, measured, events, template_version=templates.TEMPLATE_VERSION)
    except (OSError, ValueError, ValidationError, KeyError, TypeError) as err:
        print(f"refused: {type(err).__name__}: {str(err).splitlines()[0]}", file=sys.stderr)
        return 2
    a.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(f"{evidence['dataset_id']}: {evidence['label']} (gate {evidence['gate_verdict']}, "
          f"{evidence['sites_evaluated']} sites evaluated; coverage missing: {evidence['coverage']['missing'] or 'none'})")  # fmt: skip
    return 0 if evidence["label"] in VALIDATED else 1


if __name__ == "__main__":
    raise SystemExit(main())
