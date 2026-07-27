from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_ok_status_and_version() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "version" in payload
    assert payload["version"] == "0.1.0"
