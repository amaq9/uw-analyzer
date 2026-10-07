"""The Product Owner's recommendation policy v1.0 (test run) as deterministic rules.

Whoever writes a draft (the AI, a Claude Code session, anyone) supplies findings and the AI's
proposed amount. These rules, not the author, decide the outcome and the final amount, so the
policy is enforced by the server. The policy text itself is private; only its numbers and
structure live here.

    entity cannot be confirmed or found                -> decline
    a VERIFIED insolvency, sanctions, fraud or serious
    regulatory action, or going-concern doubt          -> decline
    balance sheet, liquidity, gearing and cash flow
    weak on the consolidated findings                  -> decline
    otherwise the AI proposes an amount A against the limit requested R:
        A >= 80% of R                                  -> full approval (the full amount, R)
        20% <= A < 80% of R                            -> reduced approval, A rounded DOWN
        below 20% of R (also after rounding down)      -> decline
    An amount above R is never recommended.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum

from app.cases.schemas import CaseStatus

POLICY_VERSION = "1.0"
FLOOR_FRACTION = Decimal("0.20")
FULL_FRACTION = Decimal("0.80")
ROUND_DOWN_STEP = Decimal("1000")
CENTS = Decimal("0.01")


class Outcome(StrEnum):
    APPROVE = "APPROVE"
    DECLINE = "DECLINE"


class Band(StrEnum):
    FULL = "FULL"
    REDUCED = "REDUCED"
    DECLINE = "DECLINE"


class DeclineRule(StrEnum):
    ENTITY_NOT_CONFIRMED = "entity_not_confirmed"
    INSOLVENCY = "insolvency"
    SANCTIONS = "sanctions"
    FRAUD_OR_REGULATORY = "fraud_or_regulatory"
    GOING_CONCERN = "going_concern"
    FINANCIAL_FINDINGS_WEAK = "financial_findings_weak"
    AMOUNT_BELOW_FLOOR = "amount_below_floor"


FINDING_CODES = (
    DeclineRule.INSOLVENCY,
    DeclineRule.SANCTIONS,
    DeclineRule.FRAUD_OR_REGULATORY,
    DeclineRule.GOING_CONCERN,
)


class PolicyInputError(ValueError):
    """The inputs cannot be judged under the policy (a caller bug or a bad draft)."""


@dataclass(frozen=True)
class Derived:
    outcome: Outcome
    band: Band
    recommended_amount: Decimal | None
    rules: tuple[DeclineRule, ...]


def round_down(amount: Decimal) -> Decimal:
    return (
        (amount / ROUND_DOWN_STEP).to_integral_value(rounding=ROUND_FLOOR) * ROUND_DOWN_STEP
    ).quantize(CENTS)


def derive(
    *,
    case_status: CaseStatus,
    requested: Decimal | None,
    ai_proposed: Decimal | None,
    financial_findings_weak: bool,
    verified_findings: tuple[DeclineRule, ...],
) -> Derived:
    """Apply the policy. Raises PolicyInputError only for inputs that cannot be judged."""
    if case_status is CaseStatus.ENTITY_UNCONFIRMED:
        return Derived(Outcome.DECLINE, Band.DECLINE, None, (DeclineRule.ENTITY_NOT_CONFIRMED,))
    if case_status is not CaseStatus.ENTITY_RESOLVED:
        raise PolicyInputError("The legal entity must be resolved, or recorded as not confirmed.")

    rules: list[DeclineRule] = [r for r in FINDING_CODES if r in verified_findings]
    if financial_findings_weak:
        rules.append(DeclineRule.FINANCIAL_FINDINGS_WEAK)
    if rules:
        return Derived(Outcome.DECLINE, Band.DECLINE, None, tuple(rules))

    if requested is None or requested <= 0:
        raise PolicyInputError("The case has no requested exposure to compare an amount with.")
    if ai_proposed is None:
        raise PolicyInputError("An amount is needed unless a decline rule applies.")
    if ai_proposed < 0 or ai_proposed > requested:
        raise PolicyInputError("The proposed amount must be between zero and the amount requested.")

    if ai_proposed >= requested * FULL_FRACTION:
        return Derived(Outcome.APPROVE, Band.FULL, requested.quantize(CENTS), ())
    reduced = round_down(ai_proposed)
    if reduced < requested * FLOOR_FRACTION:
        return Derived(Outcome.DECLINE, Band.DECLINE, None, (DeclineRule.AMOUNT_BELOW_FLOOR,))
    return Derived(Outcome.APPROVE, Band.REDUCED, reduced, ())
