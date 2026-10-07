"""Shapes for a draft recommendation: what an author may submit, and what the API returns.

The author supplies findings, reasons with evidence and the AI's proposed amount. The server
derives the outcome and the final amount from the policy, so an author cannot choose them.
"""

import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.recommendation.policy import POLICY_VERSION, Band, Outcome

NOTICE = "Draft recommendation for the underwriter. Not a decision."
PAYMENT_LIMITATION = "Payment behaviour was not assessed (data not used in this product)."
_HTTPS = re.compile(r"^https://[^\s/]+\S*$")

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ShortText = Annotated[Text, StringConstraints(max_length=200)]
FactorCode = Literal[
    "sector_outlook", "acceptable_not_strong", "missing_information", "concentration"
]
FindingCode = Literal["insolvency", "sanctions", "fraud_or_regulatory", "going_concern"]


class EvidenceRef(BaseModel):
    """Where a reason comes from. Documents must be real uploads of this case; web sources need a
    secure address, the date it was read, and the quoted words."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["document", "web"]
    document_id: uuid.UUID | None = None
    url: str | None = Field(default=None, max_length=500)
    retrieved_at: datetime | None = None
    quote: Annotated[Text, StringConstraints(max_length=300)]
    location: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _kind_rules(self) -> Self:
        if self.kind == "document":
            if self.document_id is None:
                raise ValueError("A document reference needs the document id.")
            if self.url or self.retrieved_at:
                raise ValueError("A document reference must not carry a web address.")
        else:
            if not (self.url and _HTTPS.fullmatch(self.url)):
                raise ValueError("A web source needs a secure (https) address.")
            if self.retrieved_at is None:
                raise ValueError("A web source needs the date and time it was read.")
            if self.document_id is not None:
                raise ValueError("A web reference must not carry a document id.")
        return self


class Reason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[Text, StringConstraints(max_length=500)]
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=5)


class DeclineFinding(BaseModel):
    """A finding that always means decline, but only once verified under the protocol."""

    model_config = ConfigDict(extra="forbid")

    code: FindingCode
    verified: bool
    evidence: list[EvidenceRef] = Field(min_length=1, max_length=5)


class Factor(BaseModel):
    """Something that lowered the proposed amount, and how."""

    model_config = ConfigDict(extra="forbid")

    code: FactorCode
    explanation: Annotated[Text, StringConstraints(max_length=400)]


class SourceInfo(BaseModel):
    """Who produced the draft and with what, so the run can be reproduced (P-10)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["claude_code_session"]
    model: ShortText
    skill_version: Annotated[Text, StringConstraints(max_length=50)]
    policy_version: Annotated[Text, StringConstraints(max_length=20)]

    @field_validator("policy_version")
    @classmethod
    def _approved_policy(cls, value: str) -> str:
        if value != POLICY_VERSION:
            raise ValueError(f"Only the approved policy version {POLICY_VERSION} can be used.")
        return value


class DraftImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_proposed_amount: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    financial_findings_weak: bool
    decline_findings: list[DeclineFinding] = Field(default_factory=list, max_length=10)
    factors: list[Factor] = Field(default_factory=list, max_length=4)
    summary: Annotated[Text, StringConstraints(max_length=600)]
    reasons: list[Reason] = Field(min_length=1, max_length=12)
    information_gaps: list[ShortText] = Field(default_factory=list, max_length=20)
    source: SourceInfo

    @model_validator(mode="after")
    def _unique_codes(self) -> Self:
        factor_codes = [f.code for f in self.factors]
        if len(set(factor_codes)) != len(factor_codes):
            raise ValueError("Each factor can be given once.")
        finding_codes = [f.code for f in self.decline_findings]
        if len(set(finding_codes)) != len(finding_codes):
            raise ValueError("Each finding can be given once.")
        return self


class DraftOut(BaseModel):
    """A draft recommendation for the underwriter. Always labelled; never a decision."""

    id: uuid.UUID
    case_id: uuid.UUID
    version: int
    outcome: Outcome
    band: Band
    requested_amount: Decimal | None
    requested_currency: str | None
    recommended_amount: Decimal | None
    ai_proposed_amount: Decimal | None
    rule_codes: list[str]
    summary: str
    reasons: list[Reason]
    decline_findings: list[DeclineFinding]
    factors: list[Factor]
    information_gaps: list[str]
    limitations: list[str]
    source: SourceInfo
    policy_version: str
    notice: str = NOTICE
    test_product: bool = True
    created_by: str
    created_at: datetime


class DraftRecord(BaseModel):
    """Internal: a stored draft (includes the tenant)."""

    id: uuid.UUID
    case_id: uuid.UUID
    tenant_id: str
    version: int
    outcome: Outcome
    band: Band
    requested_amount: Decimal | None
    requested_currency: str | None
    recommended_amount: Decimal | None
    ai_proposed_amount: Decimal | None
    rule_codes: list[str]
    content: dict[str, Any]
    source: dict[str, Any]
    policy_version: str
    created_by: str
    created_at: datetime


def to_out(record: DraftRecord) -> DraftOut:
    content = record.content
    return DraftOut(
        id=record.id,
        case_id=record.case_id,
        version=record.version,
        outcome=record.outcome,
        band=record.band,
        requested_amount=record.requested_amount,
        requested_currency=record.requested_currency,
        recommended_amount=record.recommended_amount,
        ai_proposed_amount=record.ai_proposed_amount,
        rule_codes=record.rule_codes,
        summary=content["summary"],
        reasons=[Reason(**r) for r in content["reasons"]],
        decline_findings=[DeclineFinding(**f) for f in content["decline_findings"]],
        factors=[Factor(**f) for f in content["factors"]],
        information_gaps=content["information_gaps"],
        limitations=[PAYMENT_LIMITATION],
        source=SourceInfo(**record.source),
        policy_version=record.policy_version,
        created_by=record.created_by,
        created_at=record.created_at,
    )
