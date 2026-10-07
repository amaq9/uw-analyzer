"""JWT validation against an OIDC identity provider, plus a dev/test stub provider."""

import time
from collections.abc import Callable
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.models import Principal, Role

ALGORITHMS = ["RS256"]
KeyResolver = Callable[[str], Any]


class InvalidTokenError(Exception):
    """Raised for any token that must not authenticate. Message is safe to log, not to show."""


class TokenVerifier:
    """Validates signature, issuer, audience, expiry and required claims. Fails closed."""

    def __init__(self, *, issuer: str, audience: str, key_resolver: KeyResolver) -> None:
        self._issuer = issuer
        self._audience = audience
        self._key_resolver = key_resolver

    def verify(self, token: str) -> Principal:
        try:
            key = self._key_resolver(token)
            claims = jwt.decode(
                token,
                key=key,
                algorithms=ALGORITHMS,
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(type(exc).__name__) from exc

        tenant_id = claims.get("tenant_id")
        if not isinstance(tenant_id, str) or not tenant_id:
            raise InvalidTokenError("missing tenant_id")

        raw_roles = claims.get("roles", [])
        if not isinstance(raw_roles, list):
            raise InvalidTokenError("malformed roles")
        # Unknown role names grant nothing (deny by default).
        known = {r.value for r in Role}
        roles = frozenset(Role(r) for r in raw_roles if isinstance(r, str) and r in known)
        return Principal(subject=str(claims["sub"]), tenant_id=tenant_id, roles=roles)


def jwks_key_resolver(jwks_url: str) -> KeyResolver:
    """Resolve signing keys from the identity provider's JWKS endpoint (cached by PyJWT)."""
    client = jwt.PyJWKClient(jwks_url)
    return lambda token: client.get_signing_key_from_jwt(token).key


class StubIdentityProvider:
    """In-process identity provider for local and test use only (Settings forbids it elsewhere)."""

    issuer = "https://stub-idp.invalid/"
    audience = "uw-analyzer-api"

    def __init__(self) -> None:
        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def key_resolver(self, _token: str) -> Any:
        return self._private_key.public_key()

    def issue(
        self,
        *,
        subject: str,
        tenant_id: str | None,
        roles: list[str],
        ttl_seconds: int = 300,
        **overrides: Any,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": subject,
            "roles": roles,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        if tenant_id is not None:
            claims["tenant_id"] = tenant_id
        claims.update(overrides)
        return jwt.encode(claims, self._private_key, algorithm="RS256")
