"""Environment-validated settings. Fails closed: nothing here has an unsafe default."""

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PROD = "prod"


class AuthMode(StrEnum):
    STUB = "stub"
    OIDC = "oidc"


# An exact web origin: scheme, host and optional port. No path, no wildcard.
_ORIGIN = re.compile(r"^https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # No default: the environment must be stated explicitly.
    app_env: AppEnv
    auth_mode: AuthMode = AuthMode.OIDC

    # No default: audit events must always have a database to go to.
    database_url: str

    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None

    # Uploaded documents (FR-1.2). Optional as a group: when none are set, uploads are switched off
    # (the API answers 503 for them). When any is set, all of them must be.
    s3_endpoint_url: str | None = None
    s3_bucket: str | None = None
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str = "us-east-1"
    clamav_host: str | None = None
    clamav_port: int = 3310
    max_upload_mb: int = Field(default=20, ge=1, le=25)  # below the scanner's own 25 MB limit

    # Browser origins allowed to call the API (JSON list in the environment). Empty = none.
    cors_allowed_origins: list[str] = []

    @property
    def documents_configured(self) -> bool:
        return bool(
            self.s3_endpoint_url
            and self.s3_bucket
            and self.s3_access_key
            and self.s3_secret_key
            and self.clamav_host
        )

    @model_validator(mode="after")
    def _validate_documents(self) -> Self:
        values = [
            self.s3_endpoint_url,
            self.s3_bucket,
            self.s3_access_key,
            self.s3_secret_key,
            self.clamav_host,
        ]
        if any(values) and not all(values):
            raise ValueError(
                "Document uploads need S3_ENDPOINT_URL, S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY "
                "and CLAMAV_HOST together"
            )
        if (
            self.s3_endpoint_url
            and self.app_env in (AppEnv.STAGING, AppEnv.PROD)
            and not self.s3_endpoint_url.startswith("https://")
        ):
            raise ValueError("S3_ENDPOINT_URL must use https in staging and prod")
        return self

    @model_validator(mode="after")
    def _validate_cors(self) -> Self:
        for origin in self.cors_allowed_origins:
            if not _ORIGIN.fullmatch(origin):
                raise ValueError(
                    f"CORS_ALLOWED_ORIGINS entry {origin!r} must be an exact origin like "
                    "https://app.example.com (no wildcard, path or trailing slash)"
                )
            if self.app_env in (AppEnv.STAGING, AppEnv.PROD) and not origin.startswith("https://"):
                raise ValueError("CORS_ALLOWED_ORIGINS must use https in staging and prod")
        return self

    @model_validator(mode="after")
    def _validate_auth(self) -> Self:
        if self.auth_mode is AuthMode.STUB:
            if self.app_env not in (AppEnv.LOCAL, AppEnv.TEST):
                raise ValueError("AUTH_MODE=stub is only allowed when APP_ENV is local or test")
        elif not (self.oidc_issuer and self.oidc_audience and self.oidc_jwks_url):
            raise ValueError("AUTH_MODE=oidc requires OIDC_ISSUER, OIDC_AUDIENCE and OIDC_JWKS_URL")
        return self
