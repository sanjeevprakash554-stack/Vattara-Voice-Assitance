# AI Voice Assistant - API Documentation

## Base URLs

- **Local Development**: `http://127.0.0.1:8000`
- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc UI**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/api/v1/openapi.json`

---

## Initial Endpoints

### 1. Root Information

- **Endpoint**: `GET /`
- **Tags**: `Root`
- **Description**: Returns application identification, status, environment, and documentation links.

#### Response: `200 OK`
```json
{
  "app_name": "AI Voice Assistant",
  "version": "0.1.0",
  "status": "online",
  "environment": "development",
  "docs_url": "/docs"
}
```

---

### 2. Backend Health Status

- **Endpoint**: `GET /api/v1/health`
- **Tags**: `Health`
- **Description**: Lightweight health check endpoint for container orchestrators (e.g. Kubernetes liveness probe).

#### Response: `200 OK`
```json
{
  "status": "healthy",
  "app_name": "AI Voice Assistant",
  "version": "0.1.0",
  "environment": "development",
  "timestamp": "2026-11-06T06:40:00.000000Z"
}
```

---

### 3. Database Connectivity Health Check

- **Endpoint**: `GET /api/v1/health/database`
- **Tags**: `Health`
- **Description**: Performs a live test query (`SELECT 1`) against the PostgreSQL database engine.

#### Success Response: `200 OK`
```json
{
  "status": "healthy",
  "database": "connected",
  "dialect": "postgresql",
  "details": "Database ping query succeeded (SELECT 1).",
  "timestamp": "2026-11-06T06:40:00.000000Z",
  "error": null
}
```

#### Failure Response: `503 Service Unavailable`
```json
{
  "status": "unhealthy",
  "database": "disconnected",
  "dialect": "postgresql",
  "details": "Database ping query failed.",
  "timestamp": "2026-11-06T06:40:00.000000Z",
  "error": "could not connect to server: Connection refused"
}
```

---

## Standard Error Response Format

All error responses from the API adhere to structured JSON contracts:

### Client Error (`400 Bad Request` / `404 Not Found`)
```json
{
  "detail": "Descriptive error message"
}
```

### Validation Error (`422 Unprocessable Entity`)
```json
{
  "detail": "Request payload validation failed",
  "errors": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Server Error (`500 Internal Server Error`)
```json
{
  "detail": "Internal server error occurred. Please contact system support."
}
```
*(Full stack traces are captured in application logs and withheld from public responses for security).*
