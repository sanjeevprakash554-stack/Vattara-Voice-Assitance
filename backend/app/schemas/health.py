"""Pydantic schemas for root and health check endpoints."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class RootResponse(BaseModel):
    """Response schema for root / endpoint."""

    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="API semantic version")
    status: str = Field(..., description="Application operational status")
    environment: str = Field(..., description="Deployment environment")
    docs_url: str = Field(..., description="Interactive Swagger documentation URL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "app_name": "AI Voice Assistant",
                "version": "0.1.0",
                "status": "online",
                "environment": "development",
                "docs_url": "/docs",
            }
        }
    )


class HealthResponse(BaseModel):
    """Response schema for backend health check endpoint."""

    status: str = Field(..., description="Service health status ('healthy' or 'unhealthy')")
    app_name: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Runtime environment")
    timestamp: datetime = Field(..., description="UTC timestamp of the health check")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "app_name": "AI Voice Assistant",
                "version": "0.1.0",
                "environment": "development",
                "timestamp": "2026-11-06T12:00:00Z",
            }
        }
    )


class DatabaseHealthResponse(BaseModel):
    """Response schema for database connectivity health check."""

    status: str = Field(..., description="Status ('healthy' or 'unhealthy')")
    database: str = Field(..., description="Database connection state ('connected' or 'disconnected')")
    dialect: str = Field(..., description="SQLAlchemy database dialect")
    details: str = Field(..., description="Human-readable connection diagnosis")
    timestamp: datetime = Field(..., description="UTC timestamp of the check")
    error: str | None = Field(default=None, description="Error message if connection failed")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "database": "connected",
                "dialect": "postgresql",
                "details": "Database ping query succeeded (SELECT 1).",
                "timestamp": "2026-11-06T12:00:00Z",
                "error": None,
            }
        }
    )
