from fastapi.testclient import TestClient

from app.main import app


def test_healthz() -> None:
    client = TestClient(app)
    assert client.get("/healthz").json() == {"status": "ok"}


def test_dashboard() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "MSX 网格量化控制台" in response.text
