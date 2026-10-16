"""The outbox worker, scheduler and CLI register every module's outbox handlers (staging finding, 2026-10-16).

The API registers handlers while building the app; the worker never builds it. A module whose ``@handler`` was missing
from the worker had its events dead-lettered ("no handler"): the Customer Project Portal's sign-in emails were never
sent on staging. These tests keep the worker's list complete and prove it in a fresh process.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from veda.cli.main import HANDLER_MODULES

API = Path(__file__).resolve().parents[2]


def _modules_with_handlers() -> set[str]:
    found = set()
    for path in (API / "veda").rglob("*.py"):
        rel = path.relative_to(API).with_suffix("")
        if rel.parts[:3] == ("veda", "platform", "notifications"):
            continue  # the platform's own handlers live beside the worker and are always loaded
        if re.search(r"^@handler\(", path.read_text(encoding="utf-8"), re.MULTILINE):
            found.add(".".join(rel.parts))
    return found


def test_every_module_that_registers_an_outbox_handler_is_loaded_by_the_worker():
    missing = _modules_with_handlers() - set(HANDLER_MODULES)
    assert not missing, f"add these to veda.cli.main.HANDLER_MODULES: {sorted(missing)}"


def test_a_fresh_worker_process_has_the_portal_and_project_handlers():
    code = (
        "import json\n"
        "from veda.cli.main import _settings\n"
        "from veda.platform.notifications.handlers import HANDLERS\n"
        "_settings()\n"
        "print(json.dumps(sorted(HANDLERS)))\n"
    )
    env = {**os.environ, "VEDA_ENV": "test", "VEDA_DATABASE_URL": "sqlite://"}
    out = subprocess.run([sys.executable, "-c", code], cwd=API, env=env, capture_output=True, text=True, check=True)
    handlers = set(json.loads(out.stdout.strip().splitlines()[-1]))
    for event_type in ("portal.sign_in_link", "portal.sign_in_requested", "project.handed_over", "user.invited"):
        assert event_type in handlers, event_type
