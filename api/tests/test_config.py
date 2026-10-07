import pytest
from pydantic import ValidationError

from app.config import AppEnv, AuthMode, Settings

DB = "postgresql+psycopg://u:p@localhost/db"


def test_app_env_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("env", [AppEnv.STAGING, AppEnv.PROD])
def test_stub_auth_is_refused_outside_local_and_test(env: AppEnv) -> None:
    with pytest.raises(ValidationError, match="stub"):
        Settings(app_env=env, auth_mode=AuthMode.STUB, database_url=DB)


@pytest.mark.parametrize("env", [AppEnv.LOCAL, AppEnv.TEST])
def test_stub_auth_allowed_in_local_and_test(env: AppEnv) -> None:
    assert (
        Settings(app_env=env, auth_mode=AuthMode.STUB, database_url=DB).auth_mode is AuthMode.STUB
    )


def test_oidc_is_the_default_and_requires_provider_settings() -> None:
    with pytest.raises(ValidationError, match="OIDC_ISSUER"):
        Settings(app_env=AppEnv.PROD, database_url=DB)


def test_oidc_valid_when_fully_configured() -> None:
    settings = Settings(
        app_env=AppEnv.PROD,
        oidc_issuer="https://idp.example/",
        oidc_audience="uw-analyzer-api",
        oidc_jwks_url="https://idp.example/jwks.json",
        database_url=DB,
    )
    assert settings.auth_mode is AuthMode.OIDC


def test_database_url_has_no_default() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(app_env=AppEnv.TEST, auth_mode=AuthMode.STUB)  # type: ignore[call-arg]
