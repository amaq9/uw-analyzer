from fastapi.testclient import TestClient

from app import __version__


def test_health_returns_ok_and_version(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_health_needs_no_authentication(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_unknown_route_returns_404(client: TestClient) -> None:
    assert client.get("/does-not-exist").status_code == 404


def test_health_rejects_post(client: TestClient) -> None:
    assert client.post("/health").status_code == 405
