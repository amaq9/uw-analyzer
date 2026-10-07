from datetime import datetime

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine

from app import __version__
from app.audit.events import Action, AuditSink, Outcome, PostgresAuditSink
from app.audit.recorder import record_event
from app.auth.deps import get_principal, require_permission
from app.auth.models import Permission, Principal
from app.auth.tokens import StubIdentityProvider, TokenVerifier, jwks_key_resolver
from app.cases.entity_router import router as entity_router
from app.cases.entity_store import PostgresEntityStore
from app.cases.router import router as cases_router
from app.cases.store import PostgresCaseStore
from app.config import AuthMode, Settings
from app.documents.router import router as documents_router
from app.documents.scanner import ClamAVScanner
from app.documents.service import DocumentService
from app.documents.storage import S3Storage
from app.documents.store import PostgresDocumentStore
from app.errors import ERROR_RESPONSES, register_error_handlers
from app.middleware import correlation_id_middleware, make_upload_size_guard


class Health(BaseModel):
    status: str
    version: str


class Me(BaseModel):
    subject: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]


class AuditEventOut(BaseModel):
    id: str
    occurred_at: datetime
    actor: str | None
    action: str
    outcome: str
    resource_type: str | None
    resource_id: str | None
    correlation_id: str
    details: dict[str, str]


def create_app(
    settings: Settings | None = None,
    audit_sink: AuditSink | None = None,
    case_store: PostgresCaseStore | None = None,
    entity_store: PostgresEntityStore | None = None,
    document_service: DocumentService | None = None,
) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]  # read from environment
    app = FastAPI(title="UW Analyzer API", version=__version__)
    max_upload_bytes = settings.max_upload_mb * 1024 * 1024
    # Registered first = innermost, so the correlation ID exists when the guard answers.
    app.middleware("http")(make_upload_size_guard(max_upload_bytes))
    app.middleware("http")(correlation_id_middleware)
    register_error_handlers(app)
    if settings.cors_allowed_origins:
        # Added last so it is outermost: preflight requests are answered before auth runs.
        # Auth uses a bearer header, not cookies, so credentials are deliberately not allowed.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
            allow_credentials=False,
            max_age=600,
        )

    # Engine creation does not connect; the first audit write does.
    engine = create_engine(settings.database_url)
    app.state.audit_sink = audit_sink or PostgresAuditSink(engine)
    app.state.case_store = case_store or PostgresCaseStore(engine)
    app.state.entity_store = entity_store or PostgresEntityStore(engine)
    if document_service is None and settings.documents_configured:
        assert settings.s3_access_key and settings.s3_secret_key  # noqa: S101
        assert settings.s3_endpoint_url and settings.s3_bucket and settings.clamav_host  # noqa: S101
        document_service = DocumentService(
            store=PostgresDocumentStore(engine),
            storage=S3Storage(
                endpoint_url=settings.s3_endpoint_url,
                bucket=settings.s3_bucket,
                access_key=settings.s3_access_key.get_secret_value(),
                secret_key=settings.s3_secret_key.get_secret_value(),
                region=settings.s3_region,
            ),
            scanner=ClamAVScanner(settings.clamav_host, settings.clamav_port),
            max_bytes=max_upload_bytes,
        )
    app.state.document_service = document_service  # None = uploads switched off (503)

    if settings.auth_mode is AuthMode.STUB:
        stub = StubIdentityProvider()
        app.state.stub_idp = stub
        app.state.token_verifier = TokenVerifier(
            issuer=stub.issuer, audience=stub.audience, key_resolver=stub.key_resolver
        )
    else:
        # Settings validation guarantees these are set in oidc mode.
        assert settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url  # noqa: S101
        app.state.token_verifier = TokenVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            key_resolver=jwks_key_resolver(settings.oidc_jwks_url),
        )

    @app.get("/health", response_model=Health, tags=["ops"])
    def health() -> Health:
        """Liveness check. Reports service status only; no case or tenant data."""
        return Health(status="ok", version=__version__)

    v1 = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)

    @v1.get("/me", response_model=Me, tags=["auth"])
    def me(principal: Principal = Depends(get_principal)) -> Me:  # noqa: B008
        """Who the caller is and what they may do. Informational; grants nothing."""
        return Me(
            subject=principal.subject,
            tenant_id=principal.tenant_id,
            roles=sorted(r.value for r in principal.roles),
            permissions=sorted(p.value for p in principal.permissions),
        )

    @v1.get("/audit-events", response_model=list[AuditEventOut], tags=["audit"])
    def list_audit_events(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        principal: Principal = Depends(require_permission(Permission.AUDIT_READ)),  # noqa: B008
    ) -> list[AuditEventOut]:
        """The caller's own tenant's audit events, newest first. Reading is itself audited."""
        events = request.app.state.audit_sink.list_for_tenant(principal.tenant_id, limit)
        record_event(
            request,
            Action.AUDIT_READ,
            Outcome.SUCCESS,
            tenant_id=principal.tenant_id,
            actor=principal.subject,
            details={"limit": str(limit)},
        )
        return [
            AuditEventOut(
                id=str(e.id),
                occurred_at=e.occurred_at,
                actor=e.actor,
                action=str(e.action),
                outcome=e.outcome.value,
                resource_type=e.resource_type,
                resource_id=e.resource_id,
                correlation_id=e.correlation_id,
                details={k: str(v) for k, v in e.details.items()},
            )
            for e in events
        ]

    v1.include_router(cases_router)
    v1.include_router(entity_router)
    v1.include_router(documents_router)
    app.include_router(v1)
    return app
