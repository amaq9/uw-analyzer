from datetime import datetime

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine

from app import __version__
from app.audit.events import Action, AuditSink, Outcome, PostgresAuditSink
from app.audit.recorder import record_event
from app.auth.deps import get_principal, require_permission
from app.auth.models import Permission, Principal
from app.auth.tokens import StubIdentityProvider, TokenVerifier, jwks_key_resolver
from app.config import AuthMode, Settings
from app.middleware import correlation_id_middleware


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


def create_app(settings: Settings | None = None, audit_sink: AuditSink | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]  # read from environment
    app = FastAPI(title="UW Analyzer API", version=__version__)
    app.middleware("http")(correlation_id_middleware)
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
    app.state.audit_sink = audit_sink or PostgresAuditSink(create_engine(settings.database_url))

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

    @app.get("/me", response_model=Me, tags=["auth"])
    def me(principal: Principal = Depends(get_principal)) -> Me:  # noqa: B008
        """Who the caller is and what they may do. Informational; grants nothing."""
        return Me(
            subject=principal.subject,
            tenant_id=principal.tenant_id,
            roles=sorted(r.value for r in principal.roles),
            permissions=sorted(p.value for p in principal.permissions),
        )

    @app.get("/audit-events", response_model=list[AuditEventOut], tags=["audit"])
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

    return app
