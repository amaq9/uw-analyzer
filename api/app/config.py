"""Environment-validated settings. Fails closed: nothing here has an unsafe default."""

from enum import StrEnum
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class AuthMode(StrEnum):
    STUB = "stub"
    OIDC = "oidc"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # No default: the environment must be stated explicitly.
    app_env: AppEnv
    auth_mode: AuthMode = AuthMode.OIDC

    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None

    @model_validator(mode="after")
    def _validate_auth(self) -> Self:
        if self.auth_mode is AuthMode.STUB:
            if self.app_env not in (AppEnv.LOCAL, AppEnv.TEST):
                raise ValueError("AUTH_MODE=stub is only allowed when APP_ENV is local or test")
        elif not (self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url):
            raise ValueError("AUTH_MODE=oidc requires OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL")
        return self
