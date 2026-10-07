"""FastAPI dependencies: authentication, permission checks, tenant isolation."""

import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import Permission, Principal
from app.auth.tokens import InvalidTokenError, TokenVerifier

logger = logging.getLogger("uw.auth")
_bearer = HTTPBearer(auto_error=False)


def get_principal(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> Principal:
    verifier: TokenVerifier = request.app.state.token_verifier
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        logger.warning("auth.rejected reason=%s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.") from None


def require_permission(permission: Permission) -> Callable[[Principal], Principal]:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:  # noqa: B008
        if not principal.has(permission):
            logger.warning(
                "authz.denied subject=%s tenant=%s permission=%s",
                principal.subject,
                principal.tenant_id,
                permission,
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted.")
        return principal

    return dependency


def assert_same_tenant(principal: Principal, resource_tenant_id: str) -> None:
    """Object-level tenant isolation. Cross-tenant access is denied and logged.

    Reports 404 (not 403) so a caller cannot learn that another tenant's object exists.
    """
    if principal.tenant_id != resource_tenant_id:
        logger.warning(
            "authz.cross_tenant_denied subject=%s tenant=%s",
            principal.subject,
            principal.tenant_id,
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
