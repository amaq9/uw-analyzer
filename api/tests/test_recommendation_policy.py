"""The recommendation policy v1.0 as rules: every band, boundary, rounding and decline rule."""

from decimal import Decimal

import pytest

from app.cases.schemas import CaseStatus
from app.recommendation.policy import (
    Band,
    DeclineRule,
    Derived,
    Outcome,
    PolicyInputError,
    derive,
    round_down,
)

D = Decimal
R = D("1000000")  # the amount requested in most tests


def judge(
    ai: str | None,
    requested: Decimal | None = R,
    *,
    weak: bool = False,
    findings: tuple[DeclineRule, ...] = (),
    status: CaseStatus = CaseStatus.ENTITY_RESOLVED,
) -> Derived:
    return derive(
        case_status=status,
        requested=requested,
        ai_proposed=None if ai is None else D(ai),
        financial_findings_weak=weak,
        verified_findings=findings,
    )


# --- the three bands -------------------------------------------------------------------------


@pytest.mark.parametrize("ai", ["800000", "800001", "850000", "999999", "1000000"])
def test_80_percent_or_more_is_the_full_requested_amount(ai: str) -> None:
    result = judge(ai)
    assert (result.outcome, result.band) == (Outcome.APPROVE, Band.FULL)
    assert result.recommended_amount == R  # exactly the requested amount, not the AI's figure
    assert result.rules == ()


@pytest.mark.parametrize(
    ("ai", "expected"),
    [
        ("799999", "799000"),  # just under 80%, rounded DOWN to the nearest 1,000
        ("637420", "637000"),  # the worked example from the policy
        ("500000", "500000"),
        ("200000", "200000"),  # exactly 20% is allowed
        ("200999", "200000"),
    ],
)
def test_between_20_and_80_percent_is_a_reduced_amount_rounded_down(ai: str, expected: str) -> None:
    result = judge(ai)
    assert (result.outcome, result.band) == (Outcome.APPROVE, Band.REDUCED)
    assert result.recommended_amount == D(expected)


@pytest.mark.parametrize("ai", ["199999", "100000", "1", "0"])
def test_below_20_percent_is_a_decline(ai: str) -> None:
    result = judge(ai)
    assert (result.outcome, result.band) == (Outcome.DECLINE, Band.DECLINE)
    assert result.recommended_amount is None
    assert result.rules == (DeclineRule.AMOUNT_BELOW_FLOOR,)


def test_the_floor_applies_after_rounding_down() -> None:
    # 20% of 1,000,500 is 200,100. 200,100 itself rounds down to 200,000, which is below the floor.
    assert judge("200100", D("1000500")).band is Band.DECLINE
    assert judge("201000", D("1000500")).band is Band.REDUCED
    # small amounts: 22.5% of 4,000 rounds down to zero, so it is below the floor
    assert judge("900", D("4000")).band is Band.DECLINE


def test_an_amount_above_the_request_is_never_recommended() -> None:
    with pytest.raises(PolicyInputError):
        judge("1000001")
    with pytest.raises(PolicyInputError):
        judge("-1")


# --- decline rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rule",
    [
        DeclineRule.INSOLVENCY,
        DeclineRule.SANCTIONS,
        DeclineRule.FRAUD_OR_REGULATORY,
        DeclineRule.GOING_CONCERN,
    ],
)
def test_each_verified_finding_alone_means_decline_whatever_the_amount(rule: DeclineRule) -> None:
    result = judge("1000000", findings=(rule,))
    assert (result.outcome, result.recommended_amount, result.rules) == (
        Outcome.DECLINE,
        None,
        (rule,),
    )


def test_several_findings_are_all_reported() -> None:
    result = judge(None, findings=(DeclineRule.SANCTIONS, DeclineRule.INSOLVENCY))
    assert result.rules == (DeclineRule.INSOLVENCY, DeclineRule.SANCTIONS)  # stable policy order


def test_weak_consolidated_financial_findings_mean_decline() -> None:
    result = judge("900000", weak=True)
    assert result.outcome is Outcome.DECLINE
    assert result.rules == (DeclineRule.FINANCIAL_FINDINGS_WEAK,)


def test_findings_and_weak_financials_together() -> None:
    result = judge(None, weak=True, findings=(DeclineRule.GOING_CONCERN,))
    assert result.rules == (DeclineRule.GOING_CONCERN, DeclineRule.FINANCIAL_FINDINGS_WEAK)


def test_an_unconfirmed_entity_is_a_decline_and_needs_no_amount_or_request() -> None:
    result = judge(None, None, status=CaseStatus.ENTITY_UNCONFIRMED)
    assert (result.outcome, result.recommended_amount) == (Outcome.DECLINE, None)
    assert result.rules == (DeclineRule.ENTITY_NOT_CONFIRMED,)


@pytest.mark.parametrize("status", [CaseStatus.DRAFT, CaseStatus.ENTITY_AMBIGUOUS])
def test_an_unresolved_entity_cannot_be_judged_at_all(status: CaseStatus) -> None:
    with pytest.raises(PolicyInputError, match="resolved"):
        judge("500000", status=status)


# --- inputs that cannot be judged ------------------------------------------------------------


def test_a_missing_request_or_amount_cannot_be_judged() -> None:
    with pytest.raises(PolicyInputError):
        judge("500000", None)
    with pytest.raises(PolicyInputError):
        judge("500000", D("0"))
    with pytest.raises(PolicyInputError):
        judge(None)


def test_rounding_down_never_rounds_up() -> None:
    assert round_down(D("999.99")) == D("0.00")
    assert round_down(D("1000")) == D("1000.00")
    assert round_down(D("1999.99")) == D("1000.00")


def test_money_stays_exact() -> None:
    result = judge("800000.00", D("1000000.00"))
    assert result.recommended_amount == D("1000000.00") and isinstance(
        result.recommended_amount, Decimal
    )
