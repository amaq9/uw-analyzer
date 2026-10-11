"""Agreement view: how often the underwriter's recorded outcome matches the system's draft. This
is how the Product Owner tests the product (policy v1.0 test run). It reports counts and rows only:
no score, rating or ranking of anyone or anything (ADR 0004)."""

import uuid
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.auth.deps import require_permission
from app.auth.models import Permission, Principal
from app.recommendation.decision_schemas import DecisionAction
from app.recommendation.decision_store import underwriter_decisions as ud
from app.recommendation.policy import Outcome
from app.recommendation.store import draft_recommendations as dr

router = APIRouter(prefix="/agreement", tags=["agreement"])


class AgreementRow(BaseModel):
    case_id: uuid.UUID
    draft_id: uuid.UUID
    draft_version: int
    currency: str | None
    draft_outcome: Outcome
    draft_amount: Decimal | None
    ai_proposed_amount: Decimal | None
    action: DecisionAction
    final_outcome: Outcome | None
    final_amount: Decimal | None
    agrees: bool
    same_outcome: bool
    reason: str | None
    decided_by: str
    decided_at: datetime


class AgreementTotals(BaseModel):
    decided: int
    adopted: int
    changed: int
    rejected: int
    same_outcome: int
    different_outcome: int
    amount_differs_same_outcome: int


class AgreementReport(BaseModel):
    totals: AgreementTotals
    rows: list[AgreementRow]
    notice: str = (
        "Counts of how the underwriter's recorded outcomes compare with the system's drafts. "
        "A test-run measure only; it is not a score of the system or of any person."
    )
    test_product: bool = True


def _row(m: sa.RowMapping) -> AgreementRow:
    final_outcome = Outcome(m["final_outcome"]) if m["final_outcome"] else None
    return AgreementRow(
        case_id=m["case_id"],
        draft_id=m["draft_id"],
        draft_version=m["version"],
        currency=m["requested_currency"],
        draft_outcome=Outcome(m["outcome"]),
        draft_amount=m["recommended_amount"],
        ai_proposed_amount=m["ai_proposed_amount"],
        action=DecisionAction(m["action"]),
        final_outcome=final_outcome,
        final_amount=m["final_amount"],
        agrees=m["agrees"],
        same_outcome=final_outcome is not None and final_outcome.value == m["outcome"],
        reason=m["reason"],
        decided_by=m["decided_by"],
        decided_at=m["decided_at"],
    )


@router.get("", response_model=AgreementReport)
def agreement_report(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    principal: Principal = Depends(require_permission(Permission.CASE_READ)),  # noqa: B008
) -> AgreementReport:
    """Totals over all of this tenant's recorded decisions, and the newest `limit` rows."""
    stmt = (
        sa.select(
            ud.c.case_id,
            ud.c.draft_id,
            ud.c.action,
            ud.c.final_outcome,
            ud.c.final_amount,
            ud.c.agrees,
            ud.c.reason,
            ud.c.decided_by,
            ud.c.decided_at,
            dr.c.version,
            dr.c.outcome,
            dr.c.recommended_amount,
            dr.c.ai_proposed_amount,
            dr.c.requested_currency,
        )
        .join(dr, dr.c.id == ud.c.draft_id)
        .where(ud.c.tenant_id == principal.tenant_id)
        .order_by(ud.c.seq.desc())
    )
    engine = request.app.state.decision_store._engine  # noqa: SLF001
    with engine.connect() as conn:
        rows = [_row(m) for m in conn.execute(stmt).mappings().all()]
    same = [r for r in rows if r.same_outcome]
    totals = AgreementTotals(
        decided=len(rows),
        adopted=sum(r.action is DecisionAction.ADOPT for r in rows),
        changed=sum(r.action is DecisionAction.CHANGE for r in rows),
        rejected=sum(r.action is DecisionAction.REJECT for r in rows),
        same_outcome=len(same),
        different_outcome=sum(r.final_outcome is not None and not r.same_outcome for r in rows),
        amount_differs_same_outcome=sum(r.final_amount != r.draft_amount for r in same),
    )
    return AgreementReport(totals=totals, rows=rows[:limit])
