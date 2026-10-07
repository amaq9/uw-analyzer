from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.cases.schemas import CaseCreate, CaseFields, information_gaps

FULL = {
    "legal_name": "Acme Holdings Ltd",
    "trading_name": "Acme",
    "registration_number": "123456",
    "jurisdiction": "Ontario, Canada",
    "address": "1 Main St, Toronto",
    "website": "https://acme.example",
    "industry": "Manufacturing",
    "parent_name": "Acme Group",
    "ubo_name": "A. Owner",
    "exposure_amount": "1250000.50",
    "exposure_currency": "CAD",
    "terms": "Net 60",
    "context": "Existing customer since 2019",
}


def gap_fields(**kw: object) -> set[str]:
    return {g.field for g in information_gaps(CaseFields.model_validate(kw))}


def test_only_a_name_is_required() -> None:
    assert CaseCreate.model_validate({"legal_name": "Acme"}).legal_name == "Acme"
    assert CaseCreate.model_validate({"trading_name": "Acme"}).trading_name == "Acme"


@pytest.mark.parametrize("fields", [{}, {"legal_name": "   "}, {"legal_name": "", "context": "x"}])
def test_a_case_without_any_name_is_rejected(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="legal name or a trading name"):
        CaseCreate.model_validate(fields)


def test_whitespace_is_trimmed_and_blank_becomes_missing() -> None:
    case = CaseCreate.model_validate({"legal_name": "  Acme  ", "address": "   "})
    assert case.legal_name == "Acme"
    assert case.address is None


def test_full_case_round_trips_with_exact_money() -> None:
    case = CaseCreate.model_validate(FULL)
    assert case.exposure_amount == Decimal("1250000.50")
    assert information_gaps(case) == []


@pytest.mark.parametrize(
    "bad",
    [
        {"exposure_amount": "-1", "exposure_currency": "CAD"},
        {"exposure_amount": "1.234", "exposure_currency": "CAD"},
        {"exposure_amount": "100", "exposure_currency": "cad"},
        {"exposure_amount": "100", "exposure_currency": "CANADA"},
        {"exposure_amount": "100"},
        {"exposure_currency": "CAD"},
        {"website": "ftp://x.example"},
        {"website": "javascript:alert(1)"},
        {"website": "acme.example"},
        {"legal_name": "x" * 201},
        {"context": "x" * 5001},
        {"status": "ENTITY_RESOLVED"},
        {"tenant_id": "other"},
        {"owner": "someone"},
        {"id": "00000000-0000-0000-0000-000000000000"},
    ],
)
def test_invalid_or_forbidden_fields_are_rejected(bad: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        CaseCreate.model_validate({"legal_name": "Acme", **bad})


def test_a_missing_input_is_a_gap_not_a_value() -> None:
    assert gap_fields(legal_name="Acme") == {
        "registration_number",
        "jurisdiction",
        "address",
        "industry",
        "website",
        "exposure_amount",
        "terms",
        "ownership",
    }


def test_trading_name_only_flags_the_missing_legal_name() -> None:
    assert "legal_name" in gap_fields(trading_name="Acme")


def test_either_parent_or_ubo_closes_the_ownership_gap() -> None:
    assert "ownership" in gap_fields(legal_name="Acme")
    assert "ownership" not in gap_fields(legal_name="Acme", parent_name="Group")
    assert "ownership" not in gap_fields(legal_name="Acme", ubo_name="Owner")
