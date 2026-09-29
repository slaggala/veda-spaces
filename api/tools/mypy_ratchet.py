"""mypy ratchet (IR-39): type errors may only go down.

The P0 code base carries a known backlog of mypy findings, mostly Optional values that are narrowed by
program logic rather than by the type checker (see docs/implementation/P0-open-issues.md). This check runs
mypy with the configuration in pyproject.toml and fails when any file has more errors than recorded in
tools/mypy-baseline.json, or a file not in the baseline has any. Fixing errors never fails the check;
run with --update to lower the baseline after a fix.

    python tools/mypy_ratchet.py [--update]
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tools" / "mypy-baseline.json"


def current() -> Counter:
    out = subprocess.run(
        [sys.executable, "-m", "mypy", "--no-error-summary", "--no-color-output"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout
    return Counter(line.split(":", 1)[0] for line in out.splitlines() if ": error:" in line)


def main() -> int:
    counts = current()
    if "--update" in sys.argv:
        baseline = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
        lowered = {f: min(n, baseline.get(f, n)) for f, n in counts.items()}
        BASELINE.write_text(json.dumps(dict(sorted(lowered.items())), indent=2) + "\n")
        print(f"baseline: {sum(lowered.values())} errors in {len(lowered)} files")
        return 0
    baseline = json.loads(BASELINE.read_text())
    worse = {f: (baseline.get(f, 0), n) for f, n in counts.items() if n > baseline.get(f, 0)}
    for f, (was, now) in sorted(worse.items()):
        print(f"mypy ratchet: {f}: {now} errors (baseline {was})")
    total = sum(counts.values())
    print(f"mypy: {total} errors (baseline {sum(baseline.values())}); {'FAIL' if worse else 'OK'}")
    return 1 if worse else 0


if __name__ == "__main__":
    raise SystemExit(main())
