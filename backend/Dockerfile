# Multi-stage production Dockerfile for Vattara Voice Assistance Backend
FROM python:3.13-slim AS builder

WORKDIR /app

# Install system build dependencies for psycopg2 and audio tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final runtime image
FROM python:3.13-slim AS runner

WORKDIR /app

# Install runtime PostgreSQL client library and ffmpeg for audio transcoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source code and Alembic migrations
COPY . /app

# Create unprivileged system user for secure container execution
RUN useradd -u 1001 -m vattara && chown -R vattara:vattara /app
USER vattara

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
