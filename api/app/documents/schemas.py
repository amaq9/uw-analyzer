import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class DocumentCategory(StrEnum):
    FINANCIAL_STATEMENT = "financial_statement"
    CREDIT_REPORT = "credit_report"
    SUPPORTING = "supporting"


class DocumentOut(BaseModel):
    """What the API returns about an uploaded document. Never the storage location."""

    id: uuid.UUID
    case_id: uuid.UUID
    category: DocumentCategory
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    scan_status: str
    uploaded_by: str
    uploaded_at: datetime


class DocumentRecord(DocumentOut):
    """Internal: also carries the tenant and the storage key."""

    tenant_id: str
    storage_key: str
