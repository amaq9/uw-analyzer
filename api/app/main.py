from fastapi import Depends, FastAPI
from pydantic import BaseModel

from app import __version__
from app.auth.deps import get_principal
from app.auth.models import Principal
from app.auth.tokens import StubIdentityProvider, TokenVerifier, jwks_key_resolver
from app.config import AuthMode, Settings


class Health(BaseModel):
    status: str
    version: str


class Me(BaseModel):
    subject: str
    tenant_id: str
    roles: list[str]
    permissions: list[str]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]  # read from environment
    app = FastAPI(title="UW Analyzer API", version=__version__)

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

    return app
