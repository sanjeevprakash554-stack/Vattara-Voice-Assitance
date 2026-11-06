"""Tests for the backend and database health check endpoints."""

from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.core.config import settings


def test_backend_health_endpoint(client: TestClient) -> None:
    """Test that GET /api/v1/health returns healthy backend status."""
    response = client.get(f"{settings.API_V1_STR}/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app_name"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data


def test_database_health_endpoint_success(client: TestClient) -> None:
    """Test that GET /api/v1/health/database returns healthy status when connection succeeds."""
    response = client.get(f"{settings.API_V1_STR}/health/database")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "dialect" in data
    assert "timestamp" in data
    assert data["error"] is None


def test_database_health_endpoint_failure(client: TestClient) -> None:
    """Test that GET /api/v1/health/database returns 503 Service Unavailable when DB connection fails."""
    with patch("app.api.routes.health.ping_database") as mock_ping:
        mock_ping.side_effect = OperationalError("connection refused", params=None, orig=Exception("Simulated connection error"))

        response = client.get(f"{settings.API_V1_STR}/health/database")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "Simulated connection error" in data["error"]
