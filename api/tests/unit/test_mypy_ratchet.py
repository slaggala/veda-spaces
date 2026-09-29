"""RR-16: the mypy ratchet fails closed (12 §5 types gate)."""

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("mypy_ratchet", ROOT / "tools" / "mypy_ratchet.py")
assert _spec and _spec.loader
ratchet = importlib.util.module_from_spec(_spec)
sys.modules["mypy_ratchet"] = ratchet
_spec.loader.exec_module(ratchet)

OK_OUT = "veda/a.py:3: error: Bad  [arg-type]\nFound 1 error in 1 file (checked 5 source files)\n"
CLEAN_OUT = "Success: no issues found in 5 source files\n"


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "veda").mkdir()
    for name in ("a.py", "b.py"):
        (tmp_path / "veda" / name).write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["veda"]\n')
    return tmp_path


def _baseline(tmp_path, data):
    path = tmp_path / "baseline.json"
    path.write_text(data if isinstance(data, str) else json.dumps(data))
    return path


def test_mypy_missing_or_not_run_fails():
    with pytest.raises(ratchet.RatchetError, match="no summary"):
        ratchet.parse(1, "", "/usr/bin/python: No module named mypy", expected_files=5)
    with pytest.raises(ratchet.RatchetError, match="no summary"):
        ratchet.parse(0, "", "", expected_files=5)
    with pytest.raises(ratchet.RatchetError, match="could not run"):
        ratchet.run_mypy(python="/nonexistent/python")


def test_mypy_crash_or_invalid_config_fails():
    with pytest.raises(ratchet.RatchetError, match="exited 2"):
        ratchet.parse(2, "", "pyproject.toml: [mypy]: Unrecognized option", expected_files=5)


def test_targets_that_do_not_load_fail():
    with pytest.raises(ratchet.RatchetError, match="checked 0 source files"):
        ratchet.parse(0, "Success: no issues found in 0 source files\n", "", expected_files=5)
    with pytest.raises(ratchet.RatchetError, match="checked 3"):
        ratchet.parse(0, "Success: no issues found in 3 source files\n", "", expected_files=5)


def test_exit_code_and_findings_must_agree():
    with pytest.raises(ratchet.RatchetError, match="does not match"):
        ratchet.parse(1, CLEAN_OUT, "", expected_files=5)
    with pytest.raises(ratchet.RatchetError, match="does not match"):
        ratchet.parse(0, OK_OUT, "", expected_files=5)
    assert ratchet.parse(1, OK_OUT, "", expected_files=5) == Counter({"veda/a.py": 1})


@pytest.mark.parametrize(
    "data,message",
    [
        ("{not json", "unreadable"),
        ("[1, 2]", "JSON object"),
        ({"other/a.py": 1}, "not a veda/ source file"),
        ({"veda/gone.py": 1}, "does not exist"),
        ({"veda/a.py": 0}, "positive integer"),
        ({"veda/a.py": "3"}, "positive integer"),
        ({"veda/a.py": 1.5}, "positive integer"),
        ({"veda/a.py": 200}, "exceeds the reviewed ceiling"),
    ],
)
def test_malformed_or_grown_baseline_fails(tree, data, message):
    with pytest.raises(ratchet.RatchetError, match=message):
        ratchet.load_baseline(_baseline(tree, data), root=tree)


def test_new_renamed_or_worse_files_fail(capsys):
    baseline = {"veda/a.py": 2}
    assert ratchet.check(Counter({"veda/a.py": 2}), baseline, []) == 0
    assert ratchet.check(Counter({"veda/a.py": 1}), baseline, []) == 0, "fixing errors never fails"
    assert ratchet.check(Counter({"veda/a.py": 3}), baseline, []) == 1
    assert ratchet.check(Counter({"veda/a.py": 2, "veda/new.py": 1}), baseline, []) == 1
    assert "new file" in capsys.readouterr().out
    # A rename moves the errors to a path the baseline does not know: it fails.
    assert ratchet.check(Counter({"veda/renamed.py": 2}), baseline, []) == 1


def test_broad_suppressions_fail(tree):
    assert ratchet.broad_suppressions(tree) == []
    (tree / "veda" / "a.py").write_text("x = 1  # type: ignore[attr-defined]\n")
    assert ratchet.broad_suppressions(tree) == [], "a coded ignore is allowed"
    (tree / "veda" / "b.py").write_text("y = 1  # type: ignore\n")
    assert any("b.py:1" in s for s in ratchet.broad_suppressions(tree))
    (tree / "veda" / "b.py").write_text("# mypy: ignore-errors\n")
    assert ratchet.broad_suppressions(tree)
    (tree / "veda" / "b.py").write_text("y = 1\n")
    (tree / "pyproject.toml").write_text(
        '[tool.mypy]\n[[tool.mypy.overrides]]\nmodule = ["veda.*"]\nignore_errors = true\n'
    )
    assert any("ignore_errors" in s for s in ratchet.broad_suppressions(tree))
    (tree / "pyproject.toml").write_text('[tool.mypy]\ndisable_error_code = ["union-attr"]\n')
    assert any("disable_error_code" in s for s in ratchet.broad_suppressions(tree))
    assert ratchet.check(Counter(), {}, ["x"]) == 1


def test_update_only_lowers_and_never_runs_in_ci(tmp_path, monkeypatch, capsys):
    path = _baseline(tmp_path, {"veda/a.py": 3, "veda/b.py": 1})
    monkeypatch.setenv("CI", "true")
    assert ratchet.update(Counter({"veda/a.py": 1}), {"veda/a.py": 3, "veda/b.py": 1}, path) == 2
    monkeypatch.delenv("CI")
    assert ratchet.update(Counter({"veda/a.py": 4}), {"veda/a.py": 3}, path) == 1, "never raises a count"
    assert ratchet.update(Counter({"veda/c.py": 1}), {"veda/a.py": 3}, path) == 1, "never admits a new file"
    assert json.loads(path.read_text()) == {"veda/a.py": 3, "veda/b.py": 1}, "refusals write nothing"
    assert ratchet.update(Counter({"veda/a.py": 1}), {"veda/a.py": 3, "veda/b.py": 1}, path) == 0
    assert json.loads(path.read_text()) == {"veda/a.py": 1}
    out = capsys.readouterr().out
    assert "veda/a.py: 3 -> 1" in out and "veda/b.py: 1 -> 0" in out


def test_unknown_arguments_are_refused():
    assert ratchet.main(["--updte"]) == 2


def test_the_repository_baseline_is_well_formed():
    baseline = ratchet.load_baseline()
    assert sum(baseline.values()) <= ratchet.CEILING
    assert ratchet.broad_suppressions() == []
