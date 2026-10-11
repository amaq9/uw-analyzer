"""The underwriter's recorded decision on a draft recommendation (ADR 0005 items 7 and 8).

Only a named person records this, and it is the only decision in the system. The server never
fills it in. Adopt keeps the draft as is; change needs an outcome and a written reason; reject
sets the draft aside with a written reason and records no outcome."""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.recommendation.policy import Outcome

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

NOTICE = "Underwriter decision, recorded by a named person."


class DecisionAction(StrEnum):
    ADOPT = "ADOPT"
    CHANGE = "CHANGE"
    REJECT = "REJECT"


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    reason: Reason | None = None
    final_outcome: Outcome | None = Field(default=None, description="Change only")
    final_amount: Decimal | None = Field(
        default=None, gt=0, max_digits=18, decimal_places=2, description="Change to approve only"
    )

    @model_validator(mode="after")
    def _shape(self) -> Self:
        a = self.action
        if a is DecisionAction.ADOPT and (self.final_outcome or self.final_amount):
            raise ValueError("Adopt keeps the draft as it is; do not send an outcome or amount.")
        if a is DecisionAction.REJECT and (self.final_outcome or self.final_amount):
            raise ValueError("Reject records no outcome; do not send an outcome or amount.")
        if a in (DecisionAction.CHANGE, DecisionAction.REJECT) and not self.reason:
            raise ValueError("A written reason is required to change or reject a draft.")
        if a is DecisionAction.CHANGE:
            if self.final_outcome is None:
                raise ValueError("Say what the outcome is changed to.")
            if self.final_outcome is Outcome.APPROVE and self.final_amount is None:
                raise ValueError("An amount is needed when the outcome is to approve.")
            if self.final_outcome is Outcome.DECLINE and self.final_amount is not None:
                raise ValueError("Do not send an amount when the outcome is to decline.")
        return self


class DecisionRecord(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    draft_id: uuid.UUID
    tenant_id: str
    action: DecisionAction
    final_outcome: Outcome | None
    final_amount: Decimal | None
    currency: str | None
    reason: str | None
    agrees: bool
    decided_by: str
    decided_at: datetime


class DecisionOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    draft_id: uuid.UUID
    action: DecisionAction
    final_outcome: Outcome | None
    final_amount: Decimal | None
    currency: str | None
    reason: str | None
    agrees: bool
    decided_by: str
    decided_at: datetime
    notice: str = NOTICE
    test_product: bool = True


def to_out(record: DecisionRecord) -> DecisionOut:
    return DecisionOut(**record.model_dump(exclude={"tenant_id"}))
