"""Tests for the root application endpoint and documentation."""

from fastapi.testclient import TestClient
from app.core.config import settings


def test_root_endpoint_returns_success(client: TestClient) -> None:
    """Test that GET / returns 200 and expected metadata."""
    response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["status"] == "online"
    assert data["environment"] == settings.ENVIRONMENT
    assert data["docs_url"] == "/docs"


def test_openapi_schema_accessible(client: TestClient) -> None:
    """Test that the OpenAPI JSON specification is generated and reachable."""
    response = client.get(f"{settings.API_V1_STR}/openapi.json")

    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == settings.PROJECT_NAME
    assert data["info"]["version"] == settings.VERSION
    assert "/api/v1/health" in data["paths"]
    assert "/api/v1/health/database" in data["paths"]


def test_swagger_docs_accessible(client: TestClient) -> None:
    """Test that interactive Swagger documentation is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower()
