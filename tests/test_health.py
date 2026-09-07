from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_api_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "github-repo-inspector-api",
    }


def test_local_web_origin_is_allowed_by_cors_policy() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_unknown_web_origin_is_not_allowed_by_cors_policy() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://unexpected.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
