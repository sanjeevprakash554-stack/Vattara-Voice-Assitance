# AI Voice Assistant - API Documentation

## Base URLs

- **Local Development**: `http://127.0.0.1:8000`
- **Interactive Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc UI**: `http://127.0.0.1:8000/redoc`
- **OpenAPI Schema**: `http://127.0.0.1:8000/api/v1/openapi.json`

---

## 1. Authentication Endpoints (`/api/v1/auth`)

### 1.1 Business Registration
- **Endpoint**: `POST /api/v1/auth/register`
- **Tags**: `Authentication`
- **Description**: Atomic registration creating a new tenant organization and its initial `BUSINESS_ADMIN` user.
- **Request Body**:
```json
{
  "business_name": "Metro City Hospital",
  "business_type": "hospital",
  "business_email": "contact@metrohospital.com",
  "business_phone_number": "+1-555-0199",
  "business_address": "100 Healthcare Blvd, Metro City",
  "admin_full_name": "Dr. Sarah Jenkins",
  "admin_email": "sarah@metrohospital.com",
  "admin_password": "StrongPassword123!",
  "confirm_password": "StrongPassword123!"
}
```
- **Response**: `201 Created`
```json
{
  "business": {
    "id": 1,
    "business_name": "Metro City Hospital",
    "business_type": "hospital",
    "email": "contact@metrohospital.com",
    "phone_number": "+1-555-0199",
    "address": "100 Healthcare Blvd, Metro City",
    "is_active": true,
    "created_at": "2026-11-06T13:00:00Z"
  },
  "admin_user": {
    "id": 1,
    "business_id": 1,
    "full_name": "Dr. Sarah Jenkins",
    "email": "sarah@metrohospital.com",
    "role": "BUSINESS_ADMIN",
    "is_active": true,
    "created_at": "2026-11-06T13:00:00Z"
  },
  "message": "Business and administrator account registered successfully."
}
```

---

### 1.2 User Login (OAuth2 Compatible)
- **Endpoint**: `POST /api/v1/auth/login`
- **Tags**: `Authentication`
- **Description**: Authenticate via JSON or OAuth2 form-data and receive a cryptographically signed JWT bearer token.
- **Request Body (JSON)**:
```json
{
  "email": "sarah@metrohospital.com",
  "password": "StrongPassword123!"
}
```
*(Also accepts form-data with `username` and `password` for Swagger UI "Authorize" button).*
- **Response**: `200 OK`
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": 1,
    "business_id": 1,
    "full_name": "Dr. Sarah Jenkins",
    "email": "sarah@metrohospital.com",
    "role": "BUSINESS_ADMIN",
    "is_active": true,
    "created_at": "2026-11-06T13:00:00Z",
    "business_name": "Metro City Hospital",
    "business_type": "hospital"
  }
}
```

---

### 1.3 Get Current User Profile
- **Endpoint**: `GET /api/v1/auth/me`
- **Security**: `Bearer <token>`
- **Tags**: `Authentication`
- **Response**: `200 OK`
```json
{
  "id": 1,
  "business_id": 1,
  "full_name": "Dr. Sarah Jenkins",
  "email": "sarah@metrohospital.com",
  "role": "BUSINESS_ADMIN",
  "is_active": true,
  "created_at": "2026-11-06T13:00:00Z",
  "business_name": "Metro City Hospital",
  "business_type": "hospital"
}
```

---

### 1.4 Update User Profile
- **Endpoint**: `PUT /api/v1/auth/me`
- **Security**: `Bearer <token>`
- **Tags**: `Authentication`
- **Request Body**:
```json
{
  "full_name": "Dr. Sarah Jenkins, MD"
}
```
*(Role and business_id cannot be modified via profile update).*

---

### 1.5 Change Password
- **Endpoint**: `POST /api/v1/auth/change-password`
- **Security**: `Bearer <token>`
- **Tags**: `Authentication`
- **Request Body**:
```json
{
  "current_password": "StrongPassword123!",
  "new_password": "NewStrongPassword456!",
  "confirm_new_password": "NewStrongPassword456!"
}
```
- **Response**: `200 OK`
```json
{
  "message": "Password changed successfully."
}
```

---

## 2. Staff Management Endpoints (`/api/v1/users`)

All endpoints in this section are restricted to `BUSINESS_ADMIN` and automatically scoped to the authenticated tenant.

### 2.1 Create Staff Account
- **Endpoint**: `POST /api/v1/users`
- **Security**: `Bearer <BUSINESS_ADMIN_TOKEN>`
- **Tags**: `Users`
- **Request Body**:
```json
{
  "full_name": "Emily Watson",
  "email": "emily@metrohospital.com",
  "password": "StaffPassword123!",
  "role": "STAFF"
}
```
- **Response**: `201 Created`

---

### 2.2 List Business Staff
- **Endpoint**: `GET /api/v1/users?skip=0&limit=50`
- **Security**: `Bearer <BUSINESS_ADMIN_TOKEN>`
- **Tags**: `Users`
- **Response**: `200 OK` (list of users strictly within caller's business)

---

### 2.3 Get Staff Member Details
- **Endpoint**: `GET /api/v1/users/{user_id}`
- **Security**: `Bearer <BUSINESS_ADMIN_TOKEN>`
- **Tags**: `Users`
- **Response**: `200 OK` or `404 Not Found` if user belongs to another business

---

### 2.4 Update Staff Member
- **Endpoint**: `PUT /api/v1/users/{user_id}`
- **Security**: `Bearer <BUSINESS_ADMIN_TOKEN>`
- **Tags**: `Users`
- **Request Body**:
```json
{
  "full_name": "Emily Watson, RN",
  "role": "BUSINESS_ADMIN",
  "is_active": true
}
```

---

### 2.5 Deactivate Staff Member
- **Endpoint**: `DELETE /api/v1/users/{user_id}`
- **Security**: `Bearer <BUSINESS_ADMIN_TOKEN>`
- **Tags**: `Users`
- **Response**: `200 OK` (sets `is_active = false`)

---

## 3. Super Admin Endpoints (`/api/v1/admin`)

Restricted exclusively to `SUPER_ADMIN`.

### 3.1 List All Businesses
- **Endpoint**: `GET /api/v1/admin/businesses?skip=0&limit=50`
- **Security**: `Bearer <SUPER_ADMIN_TOKEN>`
- **Tags**: `Admin`

---

### 3.2 View Business Tenant Details
- **Endpoint**: `GET /api/v1/admin/businesses/{business_id}`
- **Security**: `Bearer <SUPER_ADMIN_TOKEN>`
- **Tags**: `Admin`
- **Response**: `200 OK` with counts for users, customers, appointments, and calls.

---

### 3.3 Activate or Deactivate Business Tenant
- **Endpoint**: `PATCH /api/v1/admin/businesses/{business_id}/status`
- **Security**: `Bearer <SUPER_ADMIN_TOKEN>`
- **Tags**: `Admin`
- **Request Body**:
```json
{
  "is_active": false
}
```
*(Deactivating a business immediately blocks all its users from logging in or using services).*

---

## 4. Business Management Endpoints (`/api/v1/business`)

### 4.1 Business Profile
- **GET `/api/v1/business/profile`**: View authenticated tenant profile (accessible by Admin & Staff).
- **PUT `/api/v1/business/profile`**: Update tenant profile fields (restricted to `BUSINESS_ADMIN`).
  - Fields: `business_name`, `business_type`, `email`, `phone_number`, `address`, `website`, `description`, `logo_url`, `timezone`.

### 4.2 Weekly Working Hours
- **GET `/api/v1/business/working-hours`**: Retrieve operating schedule (days 0–6: Monday–Sunday) with opening/closing times and `is_closed` flags.
- **PUT `/api/v1/business/working-hours`**: Create or update schedule for specified days (restricted to `BUSINESS_ADMIN`). Validates that `opening_time < closing_time` for open days.

### 4.3 Service Categories
- **POST `/api/v1/business/categories`**: Create service category (Admin only). Prevents duplicate active category names within tenant.
- **GET `/api/v1/business/categories`**: List tenant categories with optional `?is_active=true` filter.
- **GET `/api/v1/business/categories/{category_id}`**: Retrieve category details.
- **PUT `/api/v1/business/categories/{category_id}`**: Update category name, description, or status (Admin only).
- **DELETE `/api/v1/business/categories/{category_id}`**: Soft-deactivate category (`is_active = false`).

### 4.4 Business Services
- **POST `/api/v1/business/services`**: Create commercial service offering with duration, price, currency, and category mapping.
- **GET `/api/v1/business/services`**: List services with query filters:
  - `?category_id=<int>`
  - `?search=<text>` (case-insensitive name and description matching)
  - `?is_active=<bool>`
  - `?skip=0&limit=50` (pagination)
- **GET `/api/v1/business/services/{service_id}`**: Retrieve service details.
- **PUT `/api/v1/business/services/{service_id}`**: Update service offering attributes.
- **DELETE `/api/v1/business/services/{service_id}`**: Soft-deactivate service offering.

---

## 5. Customer Management Endpoints (`/api/v1/customers`)

### 5.1 Customer Directory
- **POST `/api/v1/customers`**: Register customer with `customer_name`, `phone_number`, `email`, `address`, `notes`. Prevents duplicate active phone numbers within the tenant.
- **GET `/api/v1/customers`**: Search customer directory:
  - `?search=<text>` (case-insensitive match against name, phone number, and email)
  - `?is_active=<bool>`
  - `?skip=0&limit=50`
- **GET `/api/v1/customers/{customer_id}`**: Retrieve customer profile.
- **PUT `/api/v1/customers/{customer_id}`**: Update customer contact details and notes.
- **DELETE `/api/v1/customers/{customer_id}`**: Soft-deactivate customer record (`is_active = false`).

### 5.2 Customer Interaction Dossier
- **GET `/api/v1/customers/{customer_id}/history`**: Comprehensive interaction history aggregation returning:
  - Full customer profile
  - Chronological list of appointments
  - Chronological list of telephony call history (types, status, duration, recording URLs)
  - `total_calls`: Integer count
  - `total_appointments`: Integer count
  - `last_interaction_date`: Computed most recent timestamp among calls and scheduled appointments

---

## 6. System Health Endpoints (`/api/v1/health`)

- **GET `/`**: Service root information.
- **GET `/api/v1/health`**: Backend operational status.
- **GET `/api/v1/health/database`**: Live PostgreSQL connectivity probe.
