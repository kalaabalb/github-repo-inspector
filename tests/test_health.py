from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app, create_app


client = TestClient(app)


def test_health_returns_api_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "github-repo-inspector-api",
    }


def test_dynamic_local_web_origin_is_allowed_by_cors_policy() -> None:
    response = client.options(
        "/api/v1/repositories/inspect",
        headers={
            "Origin": "http://localhost:35321",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:35321"


def test_explicit_production_origin_is_allowed_by_cors_policy() -> None:
    production_app = create_app(
        Settings(cors_allowed_origins=("https://inspector.example.com",))
    )
    response = TestClient(production_app).options(
        "/health",
        headers={
            "Origin": "https://inspector.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://inspector.example.com"


def test_unknown_web_origin_is_not_allowed_by_cors_policy() -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://unexpected.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
