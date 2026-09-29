"""mypy ratchet (IR-39, RR-16): type errors may only go down, and the check fails closed.

The P0 code base carries a known backlog of mypy findings, mostly Optional values that are narrowed by
program logic rather than by the type checker (see docs/implementation/P0-open-issues.md). This check runs
mypy with the configuration in pyproject.toml and fails when:

* mypy is missing, crashes, rejects its configuration, or checks fewer source files than the package holds;
* its output cannot be parsed (a non-zero exit with no findings, or findings with a zero exit);
* the baseline is malformed (not a mapping of existing ``veda/`` files to positive counts), or its total exceeds
  ``CEILING`` — the reviewed maximum, which may only be lowered;
* any file has more errors than recorded, or a file not in the baseline has any (new and renamed files start
  at zero);
* the source uses a broad suppression: a bare ``# type: ignore`` without an error code, ``# mypy: ignore-errors``,
  or ``ignore_errors`` / ``disable_error_code`` in the mypy configuration.

``--update`` is the only way to rewrite the baseline. It refuses to run in CI, never adds a file or raises a
count (it fails instead, listing them), and prints every change for review:

    python tools/mypy_ratchet.py             # check (CI)
    python tools/mypy_ratchet.py --update    # lower the baseline after fixing errors (local, reviewed)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tools" / "mypy-baseline.json"
PACKAGE = "veda"
CEILING = 157  # total recorded at IR-39; lower it together with the baseline, never raise it
_SUMMARY = re.compile(r"(?:Found \d+ errors? in \d+ files? \(checked|Success: no issues found in) (\d+) source files?")
_BARE_IGNORE = re.compile(r"#\s*type:\s*ignore(?!\[)")
_FILE_IGNORE = re.compile(r"#\s*mypy:\s*ignore-errors")


class RatchetError(Exception):
    """The check could not be performed; the ratchet fails closed."""


def source_files(root: Path = ROOT) -> list[Path]:
    return sorted(p for p in (root / PACKAGE).rglob("*.py") if "__pycache__" not in p.parts)


def run_mypy(root: Path = ROOT, python: str = sys.executable) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            [python, "-m", "mypy", "--no-color-output", "--show-error-codes"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RatchetError(f"mypy could not run: {exc}") from exc
    return proc.returncode, proc.stdout, proc.stderr


def parse(returncode: int, stdout: str, stderr: str, expected_files: int) -> Counter:
    """Error counts per file, or RatchetError if mypy did not complete a full check."""
    if returncode not in (0, 1):
        raise RatchetError(f"mypy exited {returncode} (crash or configuration error): {(stderr or stdout)[-500:]}")
    errors = [line for line in stdout.splitlines() if re.match(r"^[^:\s]+\.py:\d+(:\d+)?: error:", line)]
    summary = _SUMMARY.search(stdout)
    if summary is None:
        raise RatchetError(f"mypy produced no summary (not installed or not run?): {(stderr or stdout)[-500:]}")
    checked = int(summary.group(1))
    if checked < expected_files:
        raise RatchetError(f"mypy checked {checked} source files; the package has {expected_files}")
    if (returncode == 1) != bool(errors):
        raise RatchetError(f"mypy exit {returncode} does not match {len(errors)} parsed errors")
    return Counter(line.split(":", 1)[0] for line in errors)


def load_baseline(path: Path = BASELINE, root: Path = ROOT) -> dict[str, int]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise RatchetError(f"baseline {path.name} is unreadable: {exc}") from exc
    if not isinstance(data, dict):
        raise RatchetError("baseline must be a JSON object of file -> error count")
    for name, count in data.items():
        if not isinstance(name, str) or not name.startswith(f"{PACKAGE}/") or not name.endswith(".py"):
            raise RatchetError(f"baseline entry {name!r} is not a {PACKAGE}/ source file")
        if not (root / name).is_file():
            raise RatchetError(f"baseline entry {name} does not exist (renamed files start at zero)")
        if type(count) is not int or count <= 0:
            raise RatchetError(f"baseline count for {name} must be a positive integer")
    if sum(data.values()) > CEILING:
        raise RatchetError(f"baseline total {sum(data.values())} exceeds the reviewed ceiling {CEILING}")
    return data


def broad_suppressions(root: Path = ROOT) -> list[str]:
    found = []
    for path in source_files(root):
        for n, line in enumerate(path.read_text().splitlines(), start=1):
            if _BARE_IGNORE.search(line) or _FILE_IGNORE.search(line):
                found.append(f"{path.relative_to(root)}:{n}: {line.strip()}")
    config = tomllib.loads((root / "pyproject.toml").read_text()).get("tool", {}).get("mypy", {})
    sections = [config, *config.get("overrides", [])]
    for section in sections:
        for key in ("ignore_errors", "disable_error_code"):
            if section.get(key):
                found.append(f"pyproject.toml [tool.mypy] {key} = {section[key]!r}")
    return found


def compare(counts: Counter, baseline: dict[str, int]) -> dict[str, tuple[int, int]]:
    return {f: (baseline.get(f, 0), n) for f, n in counts.items() if n > baseline.get(f, 0)}


def check(counts: Counter, baseline: dict[str, int], suppressions: list[str]) -> int:
    worse = compare(counts, baseline)
    for f, (was, now) in sorted(worse.items()):
        print(f"mypy ratchet: {f}: {now} errors (baseline {was}){' — new file' if not was else ''}")
    for s in suppressions:
        print(f"mypy ratchet: broad suppression not allowed: {s}")
    ok = not worse and not suppressions
    print(f"mypy: {sum(counts.values())} errors (baseline {sum(baseline.values())}); {'OK' if ok else 'FAIL'}")
    return 0 if ok else 1


def update(counts: Counter, baseline: dict[str, int], path: Path = BASELINE) -> int:
    if os.environ.get("CI"):
        print("mypy ratchet: --update never runs in CI")
        return 2
    worse = compare(counts, baseline)
    if worse:
        for f, (was, now) in sorted(worse.items()):
            print(f"mypy ratchet: refusing to admit {f}: {now} errors (baseline {was})")
        return 1
    lowered = {f: n for f, n in sorted(counts.items()) if n > 0}
    for f in sorted(set(baseline) | set(lowered)):
        if baseline.get(f, 0) != lowered.get(f, 0):
            print(f"  {f}: {baseline.get(f, 0)} -> {lowered.get(f, 0)}")
    path.write_text(json.dumps(lowered, indent=2) + "\n")
    print(f"baseline: {sum(lowered.values())} errors in {len(lowered)} files (lower CEILING to match)")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if any(a not in ("--update",) for a in args):
        print(f"mypy ratchet: unknown arguments {args}")
        return 2
    try:
        baseline = load_baseline()
        counts = parse(*run_mypy(), expected_files=len(source_files()))
    except RatchetError as exc:
        print(f"mypy ratchet: FAIL (check not performed): {exc}")
        return 2
    if "--update" in args:
        return update(counts, baseline)
    return check(counts, baseline, broad_suppressions())


if __name__ == "__main__":
    raise SystemExit(main())
