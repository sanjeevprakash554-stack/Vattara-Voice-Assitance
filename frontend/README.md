# Vattara Voice Assistance - Frontend Client

This directory houses the modern, responsive React web client for the **Vattara Voice Assistance** multi-business SaaS platform.

## Technology Stack

- **Framework**: React 18
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Data Visualization**: Recharts
- **HTTP Client**: Axios with automatic JWT Bearer token management
- **Routing**: React Router DOM (v6)

## Implemented Pages & Modules

1. **Authentication (`/login`, `/register`, `/forgot-password`)**:
   - Split-screen modern auth UI.
   - Business registration with industry vertical selector (Clinic, Hotel, Salon, Auto Service, Real Estate, etc.).
   - Password reset verification flow.

2. **Business Dashboard (`/`)**:
   - 8 primary KPI cards (Incoming/Outgoing calls, Appointments, Customers, Success/Missed rates).
   - Interactive Recharts for daily call trends and appointment status distributions.
   - Live activity feed.
   - One-click "Test AI Call" simulator.

3. **AI Voice Assistant (`/assistant`)**:
   - Persona customization: Name, Voice tone selector (Alloy, Echo, Fable, Onyx, Nova, Shimmer), and Language selector.
   - System prompt and clinical business context editors.
   - Weekly operating hours scheduler.
   - Services catalog manager (Add, Edit, Delete).
   - Knowledge Base & FAQ manager (Add, Edit, Delete).
   - Master Assistant Activation toggle.

4. **Call History & Telemetry (`/calls`)**:
   - Direction filter (Incoming vs. Outgoing), status filter (Completed vs. Missed), and search.
   - Detailed inspection modal with audio recording playback simulator, timestamped transcripts, and AI-generated summaries.

5. **Appointment Management (`/appointments`)**:
   - Status filters: Upcoming, Completed, Rescheduled, Cancelled.
   - "Book Appointment" modal with customer and service selection.
   - Reschedule and cancellation dialogs with audit reasons.

6. **Customer Management (`/customers`)**:
   - Searchable customer directory.
   - Add new customer dialog.
   - Customer 360° timeline modal showing complete call and appointment history.

7. **Reminder Management (`/reminders`)**:
   - Automated SMS and outbound voice reminder schedule.
   - "Send Now" instant dispatch trigger.
   - Schedule new reminder modal.

8. **Reports & Analytics (`/reports`)**:
   - Timeframe filters (Today, 7 Days, 30 Days, Year-to-Date).
   - Conversion metrics, call volume trends, and caller intent breakdown.
   - CSV export capability.

9. **Settings & Profile (`/settings`)**:
   - Business organization settings, admin credentials, and telephony gateway status.

## Setup & Running the Frontend

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Start the Vite development server
npm run dev

# 3. Or build for production
npm run build
```
