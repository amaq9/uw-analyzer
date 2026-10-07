"""One place that finds a case and enforces tenant isolation, used by every case-related router."""

import uuid

from fastapi import HTTPException, Request, status

from app.auth.deps import assert_same_tenant
from app.auth.models import Principal
from app.cases.schemas import CaseRecord
from app.cases.store import PostgresCaseStore


def load_case_for(request: Request, principal: Principal, case_id: uuid.UUID) -> CaseRecord:
    """404 for a missing case. Another tenant's case looks missing too (and is audited)."""
    store: PostgresCaseStore = request.app.state.case_store
    record = store.get(case_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found.")
    assert_same_tenant(
        request, principal, record.tenant_id, resource_type="case", resource_id=str(case_id)
    )
    return record
