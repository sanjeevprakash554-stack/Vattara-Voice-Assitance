# Vattara Voice Assistance – Production Operations Runbook

This runbook outlines operational procedures for deploying, maintaining, backing up, and monitoring Vattara Voice Assistance in production environments.

---

## 1. Production Architecture Overview

The system runs as a multi-container isolated microservices architecture managed via Docker Compose:

```
[ Incoming Telephony & Web Traffic ]
                 │
                 ▼
      [ Nginx Reverse Proxy (80/443) ]
                 │
        ┌────────┴────────┐
        ▼                 ▼
 [ React SPA ]    [ FastAPI Backend (8000) ]
 (Frontend)               │
                ┌─────────┼─────────┐
                ▼         ▼         ▼
          [ PostgreSQL ] [ Redis ] [ AI/Telephony APIs ]
            (Port 5432)  (Cache)  (Deepgram, ElevenLabs,
                                   Twilio, Smartflo)
```

---

## 2. Deployment Procedures

### Initial Clean Deployment
```bash
# 1. Clone repository to deployment server
git clone https://github.com/vattara/vattara-voice-assistance.git /opt/vattara
cd /opt/vattara

# 2. Setup production environment file
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production   # Populate all production secrets and database passwords

# 3. Build and launch all container services
docker compose up -d --build

# 4. Verify system health and container statuses
docker compose ps
curl -f http://localhost:80/api/v1/health
```

### Zero-Downtime Application Updates
```bash
# 1. Pull latest verified release
git pull origin main

# 2. Rebuild images with no-cache for clean bundle
docker compose build backend frontend

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Gracefully reload services
docker compose up -d --no-deps backend frontend reminder_worker
```

---

## 3. Database Administration & Backup Procedures

### Automated Database Backup Script
Run daily via cron job (`/etc/cron.daily/vattara-backup`):
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/vattara"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
mkdir -p "$BACKUP_DIR"

# Dump PostgreSQL database using container exec
docker compose -f /opt/vattara/docker-compose.yml exec -T db pg_dump \
  -U vattara_user \
  -d vattara_production \
  --format=custom \
  --compress=9 > "$BACKUP_DIR/vattara_db_$TIMESTAMP.dump"

# Retain backups for 30 days
find "$BACKUP_DIR" -type f -name "vattara_db_*.dump" -mtime +30 -delete
```

### Database Restoration Procedure
```bash
# 1. Stop backend services to prevent write collisions
docker compose stop backend reminder_worker

# 2. Drop existing database and restore from dump
docker compose exec -T db dropdb -U vattara_user vattara_production
docker compose exec -T db createdb -U vattara_user vattara_production
cat /var/backups/vattara/vattara_db_<TIMESTAMP>.dump | \
  docker compose exec -T db pg_restore -U vattara_user -d vattara_production

# 3. Verify migration revision
docker compose exec backend alembic current

# 4. Restart backend services
docker compose start backend reminder_worker
```

---

## 4. Super Admin User Provisioning

To securely provision the platform Super Admin without writing plaintext credentials to disks or databases:
```bash
docker compose exec backend python -m app.scripts.create_superuser \
  --email "superadmin@vattara.com" \
  --password "YourMasterSecurePassword!2026"
```

Or run interactively (with hidden password prompt):
```bash
docker compose exec -it backend python -m app.scripts.create_superuser
```

---

## 5. Security & Rate Limiting Incident Response

### Brute-Force Rate Limiting Trip
If a customer or administrator is blocked by the sliding window rate limiter:
- Symptom: `HTTP 429 Too Many Requests` on `/api/v1/auth/login`.
- Remediation:
  - If benign lockout, wait 60 seconds for the sliding window to clear.
  - To immediately flush in-memory throttles:
    ```bash
    docker compose exec backend python -c "from app.core.rate_limiter import SlidingWindowRateLimiter; SlidingWindowRateLimiter.reset_all()"
    ```

### Emergency Human Receptionist Forwarding
If the AI voice service or telephony trunk encounters an outage:
- Assistant automatically redirects calls to the configured `fallback_number`.
- To update the fallback number immediately:
  Update `AssistantConfig.fallback_number` via Super Admin dashboard or directly in database.

---

## 6. Health Checks & Monitoring

- **API Liveness & Database Ping**: `GET /api/v1/health`
- **Dashboard Telephony Diagnostics**: `GET /api/v1/integrations`
- **Background Reminder Worker Status**: `docker compose logs -f reminder_worker`
