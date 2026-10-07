"""Write the API's OpenAPI spec to docs/api/openapi.json (the contract Codex builds against).

Run from the api/ folder:  uv run python scripts/export_openapi.py
A test fails if the committed spec drifts from the code, so the two cannot disagree.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AppEnv, AuthMode, Settings  # noqa: E402
from app.main import create_app  # noqa: E402

SPEC_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi.json"


def build_spec() -> dict[str, object]:
    app = create_app(Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB))
    return app.openapi()


def render(spec: dict[str, object]) -> str:
    return json.dumps(spec, indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text(render(build_spec()), encoding="utf-8")
    print(f"wrote {SPEC_PATH}")
