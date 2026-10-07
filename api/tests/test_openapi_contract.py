from scripts.export_openapi import SPEC_PATH, build_spec, render
from tests.p09 import offending_names


def test_committed_openapi_matches_the_code() -> None:
    """On failure, regenerate with scripts/export_openapi.py and commit the result."""
    assert SPEC_PATH.read_text(encoding="utf-8") == render(build_spec())


def test_contract_keeps_decision_wording_to_the_designated_places() -> None:
    """P-09: only the labelled draft recommendation and the human decision may use outcome words."""
    assert offending_names(build_spec()) == []
