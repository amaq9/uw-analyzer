from fastapi.testclient import TestClient

from app import __version__
from app.main import create_app

client = TestClient(create_app())


def test_health_returns_ok_and_version() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_unknown_route_returns_404() -> None:
    assert client.get("/does-not-exist").status_code == 404


def test_health_rejects_post() -> None:
    assert client.post("/health").status_code == 405
