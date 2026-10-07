import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from export_openapi import SPEC_PATH, build_spec, render  # noqa: E402


def test_committed_openapi_matches_the_code() -> None:
    """On failure, regenerate with scripts/export_openapi.py and commit the result."""
    assert SPEC_PATH.read_text(encoding="utf-8") == render(build_spec())


def test_contract_has_no_decision_endpoints() -> None:
    """P-09: nothing in the contract approves, declines, rates or sets a limit."""
    forbidden = ("approve", "decline", "rate", "limit", "decision", "bind")
    for path in build_spec()["paths"]:  # type: ignore[attr-defined]
        assert not any(word in path.lower() for word in forbidden), path
