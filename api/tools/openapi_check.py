"""OpenAPI diff gate (12 §5; IR-14): the generated contract must match the committed snapshot.

Any route, schema or error-code change shows up as a diff that has to be committed deliberately
(``--update``) and reviewed against 08 and the endpoint register.

    python tools/openapi_check.py [--update]
"""

from __future__ import annotations

import difflib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SNAPSHOT = ROOT / "openapi.snapshot.json"


def generate() -> str:
    from veda import config
    from veda.app import create_app
    from veda.kernel.openapi import build_openapi

    with tempfile.TemporaryDirectory() as tmp:
        create_app(config.load_settings(env="test", database_url=f"sqlite:///{tmp}/openapi.db"))
        return json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    current = generate()
    if "--update" in sys.argv:
        SNAPSHOT.write_text(current)
        print(f"wrote {SNAPSHOT.name}")
        return 0
    committed = SNAPSHOT.read_text() if SNAPSHOT.exists() else ""
    if current == committed:
        print("openapi: matches snapshot")
        return 0
    sys.stdout.writelines(
        difflib.unified_diff(
            committed.splitlines(True), current.splitlines(True), "openapi.snapshot.json", "generated", n=2
        )
    )
    print("openapi: contract changed; review it and run tools/openapi_check.py --update")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
