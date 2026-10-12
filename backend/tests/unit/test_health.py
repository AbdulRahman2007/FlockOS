from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_process_liveness() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_reports_database_available(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_ready", lambda: True)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_returns_unavailable_when_database_is_down(monkeypatch) -> None:
    monkeypatch.setattr("app.main.database_ready", lambda: False)

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
