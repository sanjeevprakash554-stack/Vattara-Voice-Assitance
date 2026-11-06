# Vattara Voice Assistance – AI Voice Receptionist & Telephony SaaS

**Vattara Voice Assistance** is an enterprise-grade, multi-tenant SaaS platform that automates incoming and outgoing business call reception, customer triage, intelligent appointment booking, and omnichannel reminders. Designed specifically for healthcare clinics, hospitals, hospitality resorts, beauty salons, and professional service centers.

---

## 🌟 Key Highlights & Capabilities

### 1. Futuristic Frontend Experience (React + Tailwind CSS + Framer Motion)
- **3D Abstract Voice Orb**: Reactive neural sphere with orbital rings, dynamic listening/speaking ripple pulses, and organic floating motion.
- **Dynamic Waveform Visualizer**: Multi-bar audio frequency spectrum visualizer with customizable gradient styling.
- **Interactive Live Call Simulator Sandbox**: Test inbound and outbound voice calls right in your browser with real speech synthesis and turn-by-turn conversational dialog.
- **Theme Customization System**:
  - Top navigation palette icon with floating slide-over drawer.
  - **12 Predefined Themes**: Obsidian Violet, Emerald Midnight, Burgundy Champagne, Cyberpunk Neon, Mocha Copper, Forest Lime, Midnight Plum Rose, Sand Terracotta, Arctic Graphite Mint, Indigo Solar Yellow, Slate Coral, Holographic Rainbow, and Signature Vattara.
  - **Light & Dark Surface Appearance**: Full high-contrast support across cards, inputs, and sidebars.
  - **Custom Accent Color**: Color picker with hex input and preset chips.
  - **Local Persistence**: Preferences saved automatically in `localStorage`.
- **Dynamic Recharts Synchronization**: Executive AreaCharts, BarCharts, and Donut charts adapt their fills, strokes, and tooltips to the active theme palette.

### 2. High-Performance Backend (FastAPI + SQLAlchemy 2.0 + SQLite/Postgres)
- **Zero-Setup Database**: Automatic SQLite fallback (`vattara.db`) with auto-table generation and instant demo clinic seed data.
- **Production PostgreSQL Ready**: Supports remote PostgreSQL pooling via `SQLALCHEMY_DATABASE_URI`.
- **JWT & PBKDF2-SHA256 Auth**: Secure multi-tenant authentication with role-based access control.
- **100% Automated Test Coverage**: Comprehensive Pytest suite covering all auth workflows, assistant configs, appointment booking, call simulation, reminders, and reports.

---

## 📂 Core Modules Implemented

| # | Module | Key Features |
| :--- | :--- | :--- |
| **1** | **Authentication** | Split-screen login with 3D Voice Orb, 3-step organization onboarding with industry vertical cards, password recovery. |
| **2** | **Business Dashboard** | Asymmetric flagship command center, hero Assistant Orb showcase, dual telephony throughput, Recharts AreaChart & fulfillment donut, real-time activity stream. |
| **3** | **AI Assistant Config** | Control center with sticky Voice Orb preview, 4 voice personas with browser audio sample playback, system prompt AI enhancer, service catalog, and FAQ knowledge base. |
| **4** | **Call Management** | Telephony console with Matrix Cards vs Timeline Stream toggle, inline audio frequency waveforms, caller sentiment badges, and deep inspection modal with audio scrubber. |
| **5** | **Appointments** | 7-day interactive date bar, dynamic agenda timeline, service & practitioner tags, slot rescheduling modal, and cancellation dialog. |
| **6** | **Customer CRM** | Directory grid, VIP loyalty badges, and slide-over deep dossier drawer with appointment history and call recording logs. |
| **7** | **Reminders** | Omnichannel dispatch center (SMS, AI Voice Call, WhatsApp), scheduled countdown timestamps, and "Dispatch Now" instant trigger with confetti feedback. |
| **8** | **Reports & Analytics** | Executive intelligence workspace, temporal call trajectory area chart, daily appointment disposition bar chart, and one-click CSV report export. |
| **9** | **Profile & Settings** | Organization metadata, business address and phone configuration, administrator credentials, 2FA status, and live copyable API tokens. |

---

## 🚀 Quick Start Guide

To run the complete full-stack application, open **two separate terminal windows**:

### 🟦 Terminal 1: Backend API Server
```powershell
# Navigate to backend and activate Python virtual environment
cd C:\Vattara-Voice-Assitance-main\backend
.\venv\Scripts\Activate.ps1

# Start the FastAPI Uvicorn server on port 8000
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base URL: **`http://127.0.0.1:8000`**
- Interactive Swagger Docs: **`http://127.0.0.1:8000/docs`**
- ReDoc Documentation: **`http://127.0.0.1:8000/redoc`**

---

### 🟧 Terminal 2: Frontend Client
```powershell
# Navigate to frontend and start the Vite development server
cd C:\Vattara-Voice-Assitance-main\frontend
npm run dev
```
- Web Application: **`http://localhost:5173`**

---

## 🔑 Demo Login Presets

The database automatically seeds on first launch with sample clinic records:
- **Email**: `admin@vattara.com`
- **Password**: `Admin@123`
*(Or click "Fill Demo Credentials" on the login screen for instant sign-in).*

---

## 🧪 Testing & Verification

### Run Backend Unit & Integration Tests
```powershell
cd C:\Vattara-Voice-Assitance-main
.\backend\venv\Scripts\python.exe -m pytest -v
```
*(All 11 tests pass with zero database dependency).*

### Run Frontend Production Build
```powershell
cd C:\Vattara-Voice-Assitance-main\frontend
npm run build
```
*(Vite compiles all 2,490+ modules with 0 errors).*

---

## 🛠️ Technology Stack Summary

- **Frontend**: React 18, Vite, Tailwind CSS, Framer Motion, Lucide React, Recharts, Axios, Canvas Confetti.
- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2, Passlib (PBKDF2-SHA256), Python-JOSE (JWT), SQLite / PostgreSQL.
- **Future PSTN Integrations**: Twilio Voice & SMS, OpenAI Realtime WebSocket API, Google Calendar API.
