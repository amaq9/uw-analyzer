"""Analysis endpoint: turn a finished research run into findings and a draft recommendation.

`POST /cases/{id}/analysis` needs `draft:import`. The draft it makes goes through exactly the same
checks as any draft: the server's approved policy sets the outcome and amount, and only a named
person's recorded decision is a decision."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from app.analysis.service import AnalysisUnavailable, analyse
from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.cases.access import load_case_for
from app.recommendation.schemas import DraftOut

router = APIRouter(prefix="/cases", tags=["analysis"])


class AnalysisIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID | None = None


class SectionOut(BaseModel):
    key: str
    title: str
    assessment: str
    trend: str
    why: str
    flags: list[str]


class FactorOut(BaseModel):
    code: str
    explanation: str


class AnalysisOut(BaseModel):
    status: Literal["DRAFT_PREPARED", "NEEDS_REVIEW"]
    message: str
    sections: list[SectionOut]
    consolidated_assessment: str | None
    consolidated_why: str | None
    periods_reviewed: list[str]
    requested_amount: str | None
    proposed_amount: str | None
    currency: str | None
    factors: list[FactorOut]
    information_gaps: list[str]
    evidence_created: int
    claims_created: int
    draft: DraftOut | None
    review_item_id: uuid.UUID | None
    notice: str = (
        "The analyzer applies written rules to the retrieved figures. Its draft is a recommendation "
        "for the underwriter, not a decision."
    )


@router.post("/{case_id}/analysis", response_model=AnalysisOut, status_code=status.HTTP_201_CREATED)
def run_analysis(
    request: Request,
    case_id: uuid.UUID,
    body: AnalysisIn,
    principal: Principal = Depends(require_permission(Permission.DRAFT_IMPORT)),  # noqa: B008
) -> AnalysisOut:
    """Analyse the case's latest finished research run and prepare a draft recommendation."""
    case = load_case_for(request, principal, case_id)
    try:
        out = analyse(request, principal, case, body.run_id)
    except AnalysisUnavailable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None
    record_event(
        request,
        Action.ANALYSIS_RUN,
        Outcome.SUCCESS,
        tenant_id=principal.tenant_id,
        actor=principal.subject,
        resource_type="case",
        resource_id=str(case_id),
        details={
            "result": out.status,
            "evidence_created": str(out.evidence_created),
            "claims_created": str(out.claims_created),
        },
    )
    return AnalysisOut(
        status=out.status,  # type: ignore[arg-type]
        message=out.message,
        sections=[
            SectionOut(
                key=s.key,
                title=s.title,
                assessment=s.level.value,
                trend=s.trend,
                why=s.why,
                flags=s.flags,
            )
            for s in out.sections
        ],
        consolidated_assessment=out.consolidated[0].value if out.consolidated else None,
        consolidated_why=out.consolidated[1] if out.consolidated else None,
        periods_reviewed=out.periods,
        requested_amount=str(out.requested) if out.requested is not None else None,
        proposed_amount=str(out.proposed) if out.proposed is not None else None,
        currency=out.currency,
        factors=[FactorOut(code=f.code, explanation=f.explanation) for f in out.factors],
        information_gaps=out.gaps,
        evidence_created=out.evidence_created,
        claims_created=out.claims_created,
        draft=out.draft,
        review_item_id=out.escalation_id,
    )
