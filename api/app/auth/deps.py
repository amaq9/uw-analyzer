"""FastAPI dependencies: authentication, permission checks, tenant isolation.

Every denial is both logged (diagnostics) and written as an audit event.
"""

import logging
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.audit.events import Action, Outcome
from app.audit.recorder import record_event
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
        record_event(request, Action.AUTH_REJECTED, Outcome.DENIED, details={"reason": "no_token"})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.")
    try:
        return verifier.verify(credentials.credentials)
    except InvalidTokenError as exc:
        logger.warning("auth.rejected reason=%s", exc)
        record_event(request, Action.AUTH_REJECTED, Outcome.DENIED, details={"reason": str(exc)})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required.") from None


def require_permission(permission: Permission) -> Callable[[Request, Principal], Principal]:
    def dependency(
        request: Request,
        principal: Principal = Depends(get_principal),  # noqa: B008
    ) -> Principal:
        if not principal.has(permission):
            logger.warning(
                "authz.denied subject=%s tenant=%s permission=%s",
                principal.subject,
                principal.tenant_id,
                permission,
            )
            record_event(
                request,
                Action.AUTHZ_DENIED,
                Outcome.DENIED,
                tenant_id=principal.tenant_id,
                actor=principal.subject,
                details={"permission": permission.value},
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not permitted.")
        return principal

    return dependency


def assert_same_tenant(
    request: Request,
    principal: Principal,
    resource_tenant_id: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    """Object-level tenant isolation. Cross-tenant access is denied, logged and audited.

    Reports 404 (not 403) so a caller cannot learn that another tenant's object exists.
    The audit event is filed under the caller's tenant and never names the other tenant.
    """
    if principal.tenant_id != resource_tenant_id:
        logger.warning(
            "authz.cross_tenant_denied subject=%s tenant=%s",
            principal.subject,
            principal.tenant_id,
        )
        record_event(
            request,
            Action.CROSS_TENANT_DENIED,
            Outcome.DENIED,
            tenant_id=principal.tenant_id,
            actor=principal.subject,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
