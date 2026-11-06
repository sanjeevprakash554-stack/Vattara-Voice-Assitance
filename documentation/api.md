# Vattara Voice Assistance - Complete API Documentation

## Base URLs

- **Local Development**: `http://127.0.0.1:8000`
- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc UI**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/api/v1/openapi.json`

---

## 1. Authentication (`/api/v1/auth`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/v1/auth/register` | Business Registration | Creates new organization, admin user, and initializes AI assistant config. Returns JWT. |
| **POST** | `/api/v1/auth/login` | User Login | Authenticates administrator with email & password, returns JWT token. |
| **GET** | `/api/v1/auth/me` | Current Profile | Retrieves active user profile and organization details. |
| **PUT** | `/api/v1/auth/profile` | Update Profile | Updates name, phone, address, or changes password. |
| **POST** | `/api/v1/auth/forgot-password` | Forgot Password | Dispatches password reset code simulation. |
| **POST** | `/api/v1/auth/reset-password` | Reset Password | Updates forgotten password with valid reset code. |

---

## 2. Business Dashboard (`/api/v1/dashboard`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/dashboard/stats` | Dashboard KPIs | Computes aggregate totals: incoming/outgoing calls, appointments, customers, successful, missed. |
| **GET** | `/api/v1/dashboard/activities` | Activity Feed | Returns chronological feed of recent calls, appointments, and reminders. |
| **GET** | `/api/v1/dashboard/analytics` | Telemetry Charts | Provides daily call trends, appointment status distribution, and call duration report. |

---

## 3. AI Assistant Configuration (`/api/v1/assistant`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/assistant` | Get Config | Retrieves current AI assistant name, language, voice, system prompt, and operating hours. |
| **PUT** | `/api/v1/assistant` | Update Config | Updates assistant persona, speech tone, instructions, and working hours schedule. |
| **POST** | `/api/v1/assistant/toggle` | Toggle Active State | Activates or deactivates the AI voice receptionist. |
| **GET** | `/api/v1/assistant/services` | List Services | Returns list of services offered by the business with duration & price. |
| **POST** | `/api/v1/assistant/services` | Add Service | Registers a new business service in the assistant catalog. |
| **PUT** | `/api/v1/assistant/services/{id}` | Update Service | Updates service name, duration, or fee. |
| **DELETE** | `/api/v1/assistant/services/{id}` | Delete Service | Removes a service from the catalog. |
| **GET** | `/api/v1/assistant/faqs` | List FAQs | Returns knowledge base FAQs used for caller inquiry answering. |
| **POST** | `/api/v1/assistant/faqs` | Add FAQ | Adds a new question and answer to the knowledge base. |
| **PUT** | `/api/v1/assistant/faqs/{id}` | Update FAQ | Edits FAQ question, answer, or category. |
| **DELETE** | `/api/v1/assistant/faqs/{id}` | Delete FAQ | Removes an FAQ from the knowledge base. |

---

## 4. Call Management (`/api/v1/calls`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/calls` | Call History | Filterable call history by type (incoming/outgoing), status (completed/missed), and search. |
| **GET** | `/api/v1/calls/{id}` | Call Details | Returns full call details including recording URL, summary, and audio transcript. |
| **POST** | `/api/v1/calls/simulate` | Simulate AI Call | Simulates an inbound or outbound call with realistic audio transcript and summary. |
| **POST** | `/api/v1/calls` | Log Call | Directly logs a call event. |

---

## 5. Appointment Management (`/api/v1/appointments`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/appointments` | List Appointments | Returns appointments with status filter (upcoming, completed, cancelled, rescheduled). |
| **GET** | `/api/v1/appointments/{id}` | Get Appointment | Returns appointment metadata, assigned service, and customer info. |
| **POST** | `/api/v1/appointments` | Book Appointment | Schedules an appointment, automatically linking or creating customer profile. |
| **PUT** | `/api/v1/appointments/{id}` | Update Appointment | Reschedules slot time or updates notes. |
| **POST** | `/api/v1/appointments/{id}/cancel` | Cancel Appointment | Cancels appointment with cancellation reason. |
| **POST** | `/api/v1/appointments/{id}/complete` | Complete Appointment | Marks appointment as completed. |

---

## 6. Customer Management (`/api/v1/customers`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/customers` | Customer Directory | Lists registered customers with search by name, phone number, or email. |
| **GET** | `/api/v1/customers/{id}` | Customer 360° | Returns customer profile with chronological timeline of calls and appointment history. |
| **POST** | `/api/v1/customers` | Create Customer | Registers a new customer profile. |
| **PUT** | `/api/v1/customers/{id}` | Update Customer | Updates customer contact details and notes. |
| **DELETE** | `/api/v1/customers/{id}` | Delete Customer | Removes customer record. |

---

## 7. Reminder Management (`/api/v1/reminders`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/reminders` | List Reminders | Lists scheduled notifications with status filter (pending, sent, failed). |
| **POST** | `/api/v1/reminders` | Schedule Reminder | Schedules an automated SMS, Voice Call, or WhatsApp notification. |
| **PUT** | `/api/v1/reminders/{id}` | Update Reminder | Edits reminder schedule or message copy. |
| **POST** | `/api/v1/reminders/{id}/send` | Send Immediately | Triggers manual dispatch of a pending reminder. |
| **DELETE** | `/api/v1/reminders/{id}` | Cancel Reminder | Cancels scheduled reminder. |

---

## 8. Reports and Analytics (`/api/v1/reports`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/reports/summary` | Analytics Report | Computes KPIs, conversion rate, fulfillment rate, call intent breakdown for selected range (today, 7d, 30d, year). |

---

## 9. Infrastructure Health Checks (`/api/v1/health`)

| Method | Path | Summary | Description |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/v1/health` | Backend Health | Returns backend service status for uptime monitoring. |
| **GET** | `/api/v1/health/database` | Database Health | Executes a `SELECT 1` ping across the SQLAlchemy pool. |
