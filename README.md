# AI Voice Assistant - Production SaaS Platform

A production-ready, multi-business SaaS platform providing an AI-powered voice receptionist for hospitals, hotels, salons, automobile service centres, and real estate agencies.

---

## 1. Project Description

**AI Voice Assistant** is engineered to automate business call reception, handling inbound queries, appointment scheduling, reservations, customer support, and seamless escalation to human personnel.

### Target Business Verticals
- **Hospitals & Clinics**: Patient triage, department routing, doctor consultation scheduling, inquiry answering.
- **Hotels & Hospitality**: Room booking inquiries, concierge requests, amenities scheduling.
- **Salons & Spas**: Stylist appointment booking, service catalog pricing, slot management.
- **Automobile Service Centres**: Service booking, repair status lookups, roadside dispatch.
- **Real Estate Agencies**: Property inquiry qualification, site visit scheduling, agent handover.

---

## 2. Technology Stack

### Backend
- **Python 3.13+**
- **FastAPI**: Modern, high-performance web framework for APIs.
- **SQLAlchemy 2.0**: Type-safe Object Relational Mapper with connection pooling.
- **PostgreSQL**: Production-grade relational database for multi-tenant data.
- **Pydantic & Pydantic-Settings**: Data validation, schema contracts, and environment variable parsing.
- **Pytest & HTTPX**: Comprehensive automated testing framework.

### Frontend (Scaffolded for Next Phase)
- **React.js**
- **Vite**
- **Tailwind CSS**

### Planned Integrations
- **OpenAI Realtime API** (Ultra low-latency audio-in / audio-out speech agent)
- **Twilio Voice API** (Inbound & Outbound PSTN calling)
- **Twilio SMS** (Booking confirmations and notifications)
- **WebSockets** (Bidirectional real-time audio and dashboard streaming)
- **Redis & Celery** (Task queuing and background reminder jobs)
- **Google Calendar API** (Two-way appointment synchronization)

---

## 3. Folder Structure

```
AI-Voice-Assistant/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI entry point, lifespan, CORS, error handlers
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py               # Pydantic Settings & environment validation
│   │   │   ├── logging.py              # Structured application logging
│   │   │   └── security.py             # Security, JWT, and hashing architecture
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                 # SQLAlchemy DeclarativeBase & TimestampMixin
│   │   │   └── connection.py           # Engine pool, SessionLocal, get_db, ping_database
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                 # Dependency injection (e.g. get_db_session)
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── api.py              # Central v1 router aggregation
│   │   │       └── health.py           # Health and database connectivity checks
│   │   ├── models/
│   │   │   └── __init__.py             # SQLAlchemy ORM entity models (future phase)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py               # Pydantic response models
│   │   ├── services/
│   │   │   └── __init__.py             # Domain business logic (future phase)
│   │   └── utils/
│   │       └── __init__.py             # Reusable utility helpers
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Pytest fixtures and mock DB isolation
│   │   ├── test_root.py                # Tests for root & Swagger docs
│   │   └── test_health.py              # Tests for health & database probes
│   ├── .env.example                    # Template environment variables
│   ├── .gitignore                      # Backend-specific gitignore
│   ├── pytest.ini                      # Pytest configuration
│   └── requirements.txt                # Production and development dependencies
│
├── frontend/
│   ├── package.json                    # Frontend package definition
│   ├── .gitignore                      # Frontend-specific gitignore
│   └── README.md                       # Frontend overview and guidelines
│
├── documentation/
│   ├── architecture.md                 # System architecture and domain design
│   └── api.md                          # API specifications and endpoint reference
│
├── .gitignore                          # Root gitignore
├── pytest.ini                          # Root pytest runner configuration
└── README.md                           # Master project documentation
```

---

## 4. Installation & Setup Instructions

### Prerequisites
- Python 3.10+ (Python 3.13 tested and verified)
- PostgreSQL 14+ (or Docker for containerized database)
- Node.js 18+ (for frontend)

---

### Step 1: Clone the Repository
```bash
git clone <repository_url>
cd "AI Voice Assistant"
```

---

### Step 2: Virtual Environment Setup

#### On Windows (PowerShell):
```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1
```

#### On Linux / macOS:
```bash
# Navigate to backend directory
cd backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

---

### Step 3: Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 4: Environment Configuration

Copy the example configuration to create your active `.env` file:

```bash
# Inside the backend/ directory
cp .env.example .env
```

Customize the environment variables as needed:

```ini
# Core
PROJECT_NAME="AI Voice Assistant"
VERSION="0.1.0"
ENVIRONMENT="development"
DEBUG=true
LOG_LEVEL="INFO"
API_V1_STR="/api/v1"

# CORS
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://127.0.0.1:3000","http://127.0.0.1:5173"]

# PostgreSQL
POSTGRES_SERVER="localhost"
POSTGRES_PORT=5432
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="your_postgres_password"
POSTGRES_DB="ai_voice_assistant"

# Connection Pool
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_PRE_PING=true

# Security (JWT Architecture)
SECRET_KEY="replace-with-a-secure-random-key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=10080
```

---

### Step 5: Database Setup

Ensure PostgreSQL is running and create the platform database:

```sql
-- Connect to your PostgreSQL instance:
CREATE DATABASE ai_voice_assistant;
```

---

### Step 6: Apply Database Migrations (Alembic)

With your virtual environment activated and database credentials set in `.env`:

```bash
# Navigate to backend directory
cd backend

# Apply all migrations to the latest revision (head)
alembic upgrade head

# Rollback one migration (if needed)
alembic downgrade -1

# Rollback all migrations to base (if needed)
alembic downgrade base

# View migration history
alembic history --verbose
```

---

### Step 7: How to Run the FastAPI Server

With your virtual environment activated:

```bash
# Navigate to backend/ directory (if not already there)
cd backend

# Start development server with hot-reload enabled
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The server will initialize and bind to `http://127.0.0.1:8000`.

---

## 5. API Documentation URLs

Once the server is running, the interactive documentation interfaces are accessible at:

| Documentation Interface | URL |
| :--- | :--- |
| **Interactive Swagger UI** | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| **Alternative ReDoc UI** | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |
| **OpenAPI JSON Specification** | [http://127.0.0.1:8000/api/v1/openapi.json](http://127.0.0.1:8000/api/v1/openapi.json) |

---

## 6. Initial API Endpoints

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/` | Root Info | Returns application name, version, and operational status. |
| **GET** | `/api/v1/health` | Backend Health | Returns backend service status for uptime monitoring. |
| **GET** | `/api/v1/health/database` | Database Health | Executes a `SELECT 1` ping across the SQLAlchemy pool. |

---

## 7. Running Automated Tests

Run the complete test suite with pytest:

```bash
# From the project root:
pytest

# Or inside the backend/ directory with detailed verbosity:
cd backend
pytest -v
```

All 17 automated tests will execute with mock isolation and in-memory test databases:
- **Root & Swagger Documentation** (2 tests)
- **Health Checks & Database Ping Diagnostics** (4 tests)
- **Alembic Migration Forward & Rollback Life Cycle** (1 test)
- **SQLAlchemy Models & Multi-Tenant Relationships** (9 tests)
  - Business creation and audit timestamps
  - Business-User relationship and bcrypt password encryption
  - Business-Customer relationship
  - Customer-Appointment-Business relationships
  - CallHistory logging and customer link preservation
  - Appointment-Reminder relationship
  - Full Business cascade delete integrity
  - Customer delete `SET NULL` on CallHistory
  - Unique email constraints enforcement

---

## 8. License & Development Roadmap

This foundation serves as the core layer for upcoming milestones:
1. **Multi-tenant Business & User Management** (Authentication, JWT tokens, RBAC).
2. **Telephony Integration** (Twilio Voice, Media WebSockets).
3. **Conversational Engine** (OpenAI Realtime API, tool calling for bookings).
4. **Calendar & Notification Integrations** (Google Calendar, Twilio SMS).
5. **Frontend Management Dashboard** (React + Vite + Tailwind CSS).
