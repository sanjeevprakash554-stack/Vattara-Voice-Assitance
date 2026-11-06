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

## 6. Available API Endpoints (Phases 1 - 4)

| Tag | Method | Path | Summary | Access |
| :--- | :--- | :--- | :--- | :--- |
| **Authentication** | `POST` | `/api/v1/auth/register` | Business & Admin Registration | Public |
| **Authentication** | `POST` | `/api/v1/auth/login` | User Login & JWT Issuance | Public |
| **Authentication** | `GET` | `/api/v1/auth/me` | Authenticated User Profile | Bearer Token |
| **Authentication** | `PUT` | `/api/v1/auth/me` | Update User Profile | Bearer Token |
| **Authentication** | `POST` | `/api/v1/auth/change-password` | Change User Password | Bearer Token |
| **Users** | `POST` | `/api/v1/users` | Create Staff Member | Business Admin |
| **Users** | `GET` | `/api/v1/users` | List Staff in Business | Business Admin |
| **Users** | `GET` | `/api/v1/users/{id}` | Get Staff Member Details | Business Admin |
| **Users** | `PUT` | `/api/v1/users/{id}` | Update Staff Member | Business Admin |
| **Users** | `DELETE` | `/api/v1/users/{id}` | Deactivate Staff Member | Business Admin |
| **Business Profile**| `GET` | `/api/v1/business/profile` | Get Business Profile | Admin & Staff |
| **Business Profile**| `PUT` | `/api/v1/business/profile` | Update Business Details | Business Admin |
| **Working Hours** | `GET` | `/api/v1/business/working-hours` | Get Weekly Schedule | Admin & Staff |
| **Working Hours** | `PUT` | `/api/v1/business/working-hours` | Update Weekly Schedule | Business Admin |
| **Categories** | `POST` | `/api/v1/business/categories` | Create Service Category | Business Admin |
| **Categories** | `GET` | `/api/v1/business/categories` | List Service Categories | Admin & Staff |
| **Categories** | `GET` | `/api/v1/business/categories/{id}` | Get Category Details | Admin & Staff |
| **Categories** | `PUT` | `/api/v1/business/categories/{id}` | Update Service Category | Business Admin |
| **Categories** | `DELETE`| `/api/v1/business/categories/{id}`| Deactivate Category | Business Admin |
| **Services** | `POST` | `/api/v1/business/services` | Create Business Service | Business Admin |
| **Services** | `GET` | `/api/v1/business/services` | List & Filter Services | Admin & Staff |
| **Services** | `GET` | `/api/v1/business/services/{id}` | Get Service Details | Admin & Staff |
| **Services** | `PUT` | `/api/v1/business/services/{id}` | Update Business Service | Business Admin |
| **Services** | `DELETE`| `/api/v1/business/services/{id}`| Deactivate Service | Business Admin |
| **Customers** | `POST` | `/api/v1/customers` | Create Customer Profile | Admin & Staff |
| **Customers** | `GET` | `/api/v1/customers` | Search Customer Directory | Admin & Staff |
| **Customers** | `GET` | `/api/v1/customers/{id}` | Get Customer Details | Admin & Staff |
| **Customers** | `PUT` | `/api/v1/customers/{id}` | Update Customer Details | Admin & Staff |
| **Customers** | `DELETE`| `/api/v1/customers/{id}` | Deactivate Customer | Admin & Staff |
| **Customer History**|`GET` | `/api/v1/customers/{id}/history`| Customer Interaction History | Admin & Staff |
| **Super Admin** | `GET` | `/api/v1/admin/businesses` | List All Platform Tenants | Super Admin |
| **Super Admin** | `GET` | `/api/v1/admin/businesses/{id}` | Get Tenant Telemetry | Super Admin |
| **Super Admin** | `PATCH` | `/api/v1/admin/businesses/{id}/status` | Activate/Deactivate Tenant | Super Admin |
| **Health** | `GET` | `/` | Root Information | Public |
| **Health** | `GET` | `/api/v1/health` | Backend Health Probe | Public |
| **Health** | `GET` | `/api/v1/health/database` | PostgreSQL Health Probe | Public |

---

## 7. Running Automated Tests

Run the complete test suite with pytest:

```bash
# Inside the backend/ directory with detailed verbosity:
cd backend
pytest -v
```

All **84 automated tests** execute with strict tenant isolation, role verification, and database transaction rollbacks:
- **Root & Swagger Documentation** (3 tests)
- **Health Checks & Database Ping Diagnostics** (4 tests)
- **Alembic Database Migrations** (1 test)
- **SQLAlchemy Models & Database Relationships** (9 tests)
- **Authentication & Security** (16 tests)
- **Multi-Tenant User Management & RBAC** (9 tests)
- **Super Admin Platform Controls** (5 tests)
- **Multi-Tenancy Security & Data Leakage Prevention** (6 tests)
- **Business Profile Management** (5 tests)
- **Business Working Hours** (4 tests)
- **Service Categories & Business Services** (13 tests)
- **Customer Directory & Interaction Dossier** (9 tests)

---

## 8. License & Development Roadmap

1. [x] **Phase 1: Project Setup & FastAPI Foundation**
2. [x] **Phase 2: PostgreSQL Database Configuration & SQLAlchemy Models**
3. [x] **Phase 3: Authentication, Authorization, Staff Management & Multi-Tenant Security**
4. [x] **Phase 4: Business & Customer Management (Profile, Hours, Catalog, CRM, History)**
5. [ ] **Phase 5: Telephony Integration (Twilio Voice, Media WebSockets, Inbound/Outbound)**
6. [ ] **Phase 6: Conversational Engine (OpenAI Realtime API, Custom Tools, Booking Flow)**
7. [ ] **Phase 7: Calendar & Notification Integrations (Google Calendar, Twilio SMS)**
8. [ ] **Phase 8: Frontend Management Dashboard (React + Vite + Tailwind CSS)**
