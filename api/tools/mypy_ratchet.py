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
* the source uses a broad or unreviewed suppression (FC-11): a ``# type: ignore`` without an error code or without
  a justification comment after it, any inline ``# mypy:`` configuration comment, a shadow configuration file
  (``mypy.ini``, ``.mypy.ini``, ``setup.cfg [mypy]``), a ``[tool.mypy]`` key outside the reviewed set (for example
  ``exclude``, ``strict_optional``, ``follow_imports``, ``ignore_errors``, ``disable_error_code``) or a value that
  differs from it, or a per-module override other than ``ignore_missing_imports`` for a third-party module;
* the mypy that would run is not the installed package (a local ``mypy`` module shadowing it).

mypy runs isolated (``python -I``, so the working directory cannot shadow the package) with the configuration
file named explicitly.

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
_TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?P<codes>\[[a-z0-9_, -]+\])?(?P<rest>.*)$")
_INLINE_CONFIG = re.compile(r"#\s*mypy\s*:", re.IGNORECASE)
# The reviewed [tool.mypy] configuration: every key and value is fixed; anything else is a suppression.
REVIEWED_CONFIG = {
    "python_version": "3.13",
    "files": ["veda"],
    "warn_unused_ignores": True,
    "warn_redundant_casts": True,
    "no_implicit_optional": True,
    "check_untyped_defs": True,
    "disallow_any_generics": False,
}
OVERRIDE_KEYS = {"module", "ignore_missing_imports"}
SHADOW_CONFIGS = ("mypy.ini", ".mypy.ini")


class RatchetError(Exception):
    """The check could not be performed; the ratchet fails closed."""


def source_files(root: Path = ROOT) -> list[Path]:
    return sorted(p for p in (root / PACKAGE).rglob("*.py") if "__pycache__" not in p.parts)


def mypy_origin(root: Path = ROOT, python: str = sys.executable) -> Path:
    """Where the isolated interpreter imports mypy from; it must not be inside the checked tree."""
    try:
        out = subprocess.run(
            [python, "-I", "-c", "import mypy, sys; print(mypy.__file__)"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RatchetError(f"mypy could not run: {exc}") from exc
    if out.returncode != 0 or not out.stdout.strip():
        raise RatchetError(f"mypy is not installed for {python}: {(out.stderr or out.stdout)[-300:]}")
    origin = Path(out.stdout.strip()).resolve()
    if origin.is_relative_to(root.resolve()) and ".venv" not in origin.parts and "site-packages" not in origin.parts:
        raise RatchetError(f"mypy resolves to {origin}, inside the checked tree (shadowed package)")
    return origin


def run_mypy(root: Path = ROOT, python: str = sys.executable) -> tuple[int, str, str]:
    mypy_origin(root, python)
    try:
        proc = subprocess.run(
            [python, "-I", "-m", "mypy", "--config-file", "pyproject.toml", "--no-color-output", "--show-error-codes"],
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
            where = f"{path.relative_to(root)}:{n}: {line.strip()}"
            if _INLINE_CONFIG.search(line):
                found.append(f"{where} (inline mypy configuration)")
            m = _TYPE_IGNORE.search(line)
            if m and not m.group("codes"):
                found.append(f"{where} (type: ignore without an error code)")
            elif m and not re.match(r"\s+#\s*\S", m.group("rest")):
                found.append(f"{where} (type: ignore without a justification comment)")
    for name in SHADOW_CONFIGS:
        if (root / name).exists():
            found.append(f"{name} (shadow mypy configuration)")
    setup_cfg = root / "setup.cfg"
    if setup_cfg.exists() and re.search(r"^\[mypy", setup_cfg.read_text(), re.MULTILINE):
        found.append("setup.cfg [mypy] (shadow mypy configuration)")
    config = tomllib.loads((root / "pyproject.toml").read_text()).get("tool", {}).get("mypy", {})
    for key, value in config.items():
        if key == "overrides":
            continue
        if key not in REVIEWED_CONFIG or value != REVIEWED_CONFIG[key]:
            found.append(f"pyproject.toml [tool.mypy] {key} = {value!r} (outside the reviewed configuration)")
    for key in REVIEWED_CONFIG.keys() - config.keys():
        found.append(f"pyproject.toml [tool.mypy] {key} missing from the reviewed configuration")
    for override in config.get("overrides", []):
        modules = override.get("module", [])
        modules = [modules] if isinstance(modules, str) else modules
        extra = set(override) - OVERRIDE_KEYS
        if extra or any(m == PACKAGE or m.startswith(f"{PACKAGE}.") for m in modules):
            found.append(
                f"pyproject.toml [[tool.mypy.overrides]] {modules} {sorted(extra) or ''} (only third-party ignore_missing_imports)"
            )
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
