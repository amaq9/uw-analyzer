import pytest
from pydantic import ValidationError

from app.config import AppEnv, AuthMode, Settings


def test_app_env_has_no_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


@pytest.mark.parametrize("env", [AppEnv.STAGING, AppEnv.PROD])
def test_stub_auth_is_refused_outside_local_and_test(env: AppEnv) -> None:
    with pytest.raises(ValidationError, match="stub"):
        Settings(app_env=env, auth_mode=AuthMode.STUB)


@pytest.mark.parametrize("env", [AppEnv.LOCAL, AppEnv.TEST])
def test_stub_auth_allowed_in_local_and_test(env: AppEnv) -> None:
    assert Settings(app_env=env, auth_mode=AuthMode.STUB).auth_mode is AuthMode.STUB


def test_oidc_is_the_default_and_requires_provider_settings() -> None:
    with pytest.raises(ValidationError, match="OIDC_ISSUER"):
        Settings(app_env=AppEnv.PROD)


def test_oidc_valid_when_fully_configured() -> None:
    settings = Settings(
        app_env=AppEnv.PROD,
        oidc_issuer="https://idp.example/",
        oidc_audience="uw-analyzer-api",
        oidc_jwks_url="https://idp.example/jwks.json",
    )
    assert settings.auth_mode is AuthMode.OIDC
