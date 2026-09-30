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

REVIEWED = (
    '[tool.mypy]\npython_version = "3.13"\nfiles = ["veda"]\nwarn_unused_ignores = true\nwarn_redundant_casts = true\n'
    "no_implicit_optional = true\ncheck_untyped_defs = true\ndisallow_any_generics = false\n\n"
    '[[tool.mypy.overrides]]\nmodule = ["boto3", "boto3.*"]\nignore_missing_imports = true\n'
)
OK_OUT = "veda/a.py:3: error: Bad  [arg-type]\nFound 1 error in 1 file (checked 5 source files)\n"
CLEAN_OUT = "Success: no issues found in 5 source files\n"


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "veda").mkdir()
    for name in ("a.py", "b.py"):
        (tmp_path / "veda" / name).write_text("x = 1\n")
    (tmp_path / "pyproject.toml").write_text(REVIEWED)
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
    (tree / "veda" / "a.py").write_text("x = 1  # type: ignore[attr-defined]  # stdlib stub gap\n")
    assert ratchet.broad_suppressions(tree) == [], "a coded, justified ignore is allowed"
    (tree / "veda" / "a.py").write_text("x = 1  # type: ignore[attr-defined]\n")
    assert any("justification" in s for s in ratchet.broad_suppressions(tree))
    (tree / "veda" / "a.py").write_text("x = 1\n")
    (tree / "veda" / "b.py").write_text("y = 1  # type: ignore\n")
    assert any("b.py:1" in s and "error code" in s for s in ratchet.broad_suppressions(tree))
    assert ratchet.check(Counter(), {}, ["x"]) == 1


@pytest.mark.parametrize(
    "line",
    [
        "# mypy: ignore-errors",
        "# mypy: ignore_errors",
        '# mypy: disable-error-code="union-attr"',
        "# mypy: strict-optional=False",
        "#MYPY: allow-untyped-defs",
    ],
)
def test_FC11_inline_mypy_configuration_is_refused(tree, line):
    (tree / "veda" / "b.py").write_text(f"{line}\ny = 1\n")
    assert any("inline mypy configuration" in s for s in ratchet.broad_suppressions(tree))


@pytest.mark.parametrize(
    "extra",
    [
        'exclude = ["veda/b.py"]\n',
        "strict_optional = false\n",
        'follow_imports = "skip"\n',
        "ignore_errors = true\n",
        'disable_error_code = ["union-attr"]\n',
    ],
)
def test_FC11_config_outside_the_reviewed_set_is_refused(tree, extra):
    text = (tree / "pyproject.toml").read_text().replace("[[tool.mypy.overrides]]", extra + "\n[[tool.mypy.overrides]]")
    (tree / "pyproject.toml").write_text(text)
    assert any("outside the reviewed configuration" in s for s in ratchet.broad_suppressions(tree))


def test_FC11_files_padding_and_changed_values_are_refused(tree):
    text = (tree / "pyproject.toml").read_text().replace('files = ["veda"]', 'files = ["veda", "migrations"]')
    (tree / "pyproject.toml").write_text(text)
    assert any("files" in s for s in ratchet.broad_suppressions(tree))


@pytest.mark.parametrize(
    "override",
    [
        '[[tool.mypy.overrides]]\nmodule = ["veda.platform.auth.service"]\nstrict_optional = false\n',
        '[[tool.mypy.overrides]]\nmodule = ["veda.*"]\nignore_missing_imports = true\n',
        '[[tool.mypy.overrides]]\nmodule = ["boto3"]\nignore_errors = true\n',
    ],
)
def test_FC11_per_module_overrides_are_refused(tree, override):
    (tree / "pyproject.toml").write_text((tree / "pyproject.toml").read_text() + "\n" + override)
    assert any("overrides" in s for s in ratchet.broad_suppressions(tree))


@pytest.mark.parametrize(
    "name,content",
    [
        ("mypy.ini", "[mypy]\nignore_errors = True\n"),
        (".mypy.ini", "[mypy]\n"),
        ("setup.cfg", "[mypy]\nignore_errors = True\n"),
    ],
)
def test_FC11_shadow_configuration_files_are_refused(tree, name, content):
    (tree / name).write_text(content)
    assert any("shadow mypy configuration" in s for s in ratchet.broad_suppressions(tree))


def test_FC11_a_local_mypy_package_cannot_shadow_the_installed_one(tree):
    (tree / "mypy").mkdir()
    (tree / "mypy" / "__init__.py").write_text("")
    (tree / "mypy" / "__main__.py").write_text('print("Success: no issues found in 999 source files")\n')
    origin = ratchet.mypy_origin(tree)
    assert not origin.is_relative_to(tree), "python -I ignores the working directory"


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
