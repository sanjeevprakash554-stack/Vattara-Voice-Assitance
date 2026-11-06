"""Comprehensive automated test suite for Vattara Voice Assistance modules."""

from fastapi.testclient import TestClient
from app.core.config import settings


def test_auth_workflow(client: TestClient) -> None:
    """Test business registration, login, and profile retrieval."""
    # 1. Register Business
    register_payload = {
        "business_name": "Apex Dental Clinic",
        "vertical": "clinic",
        "business_phone": "+91 99887 76655",
        "business_email": "contact@apexdental.com",
        "admin_name": "Dr. Ananya Roy",
        "admin_email": "ananya@apexdental.com",
        "admin_password": "SecurePassword123",
        "address": "101 Cathedral Road, Chennai",
    }
    reg_res = client.post(f"{settings.API_V1_STR}/auth/register", json=register_payload)
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert "access_token" in reg_data
    assert reg_data["user"]["email"] == "ananya@apexdental.com"
    assert reg_data["business"]["name"] == "Apex Dental Clinic"
    token = reg_data["access_token"]

    # 2. Login
    login_res = client.post(
        f"{settings.API_V1_STR}/auth/login",
        json={"email": "ananya@apexdental.com", "password": "SecurePassword123"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data

    # 3. Get Profile (with Bearer token)
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get(f"{settings.API_V1_STR}/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["user"]["full_name"] == "Dr. Ananya Roy"
    assert me_data["business"]["vertical"] == "clinic"


def test_assistant_and_knowledge_base(client: TestClient) -> None:
    """Test AI assistant settings, services, and FAQ management."""
    # 1. Get Assistant Config
    cfg_res = client.get(f"{settings.API_V1_STR}/assistant")
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert "assistant_name" in cfg

    # 2. Update Assistant
    update_res = client.put(
        f"{settings.API_V1_STR}/assistant",
        json={
            "assistant_name": "Vattara Pro Voice",
            "language": "en-US",
            "voice": "nova",
            "system_prompt": "You are a professional medical clinic receptionist.",
            "business_info": "Premier clinic in Chennai.",
            "working_hours": "{}",
            "is_active": True,
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["assistant_name"] == "Vattara Pro Voice"

    # 3. Create and List Service
    srv_res = client.post(
        f"{settings.API_V1_STR}/assistant/services",
        json={
            "name": "Teeth Whitening",
            "description": "Laser teeth whitening session",
            "duration_minutes": 45,
            "price": 2500.0,
            "is_active": True,
        },
    )
    assert srv_res.status_code == 201
    srv_id = srv_res.json()["id"]

    list_srv = client.get(f"{settings.API_V1_STR}/assistant/services")
    assert list_srv.status_code == 200
    assert any(s["id"] == srv_id for s in list_srv.json())

    # 4. Create and List FAQ
    faq_res = client.post(
        f"{settings.API_V1_STR}/assistant/faqs",
        json={
            "category": "Pricing",
            "question": "Do you offer installment payment?",
            "answer": "Yes, we support 0% interest EMI options for treatments above ₹5000.",
            "is_active": True,
        },
    )
    assert faq_res.status_code == 201
    faq_id = faq_res.json()["id"]

    list_faqs = client.get(f"{settings.API_V1_STR}/assistant/faqs")
    assert list_faqs.status_code == 200
    assert any(f["id"] == faq_id for f in list_faqs.json())


def test_customers_and_appointments(client: TestClient) -> None:
    """Test customer creation, appointment booking, rescheduling, and cancellation."""
    # 1. Create Customer
    cust_res = client.post(
        f"{settings.API_V1_STR}/customers",
        json={
            "name": "Suresh Raina",
            "phone": "+91 91234 56789",
            "email": "suresh@example.com",
            "notes": "VIP Patient",
        },
    )
    assert cust_res.status_code == 201
    customer = cust_res.json()
    cust_id = customer["id"]

    # 2. Book Appointment
    appt_res = client.post(
        f"{settings.API_V1_STR}/appointments",
        json={
            "customer_id": cust_id,
            "appointment_time": "2026-11-10T10:30:00Z",
            "status": "upcoming",
            "notes": "Consultation for dental implant",
            "source": "ai_call",
        },
    )
    assert appt_res.status_code == 201
    appt = appt_res.json()
    appt_id = appt["id"]
    assert appt["status"] == "upcoming"

    # 3. Customer detail timeline
    cust_detail = client.get(f"{settings.API_V1_STR}/customers/{cust_id}")
    assert cust_detail.status_code == 200
    assert len(cust_detail.json()["appointments"]) >= 1

    # 4. Reschedule Appointment
    resched = client.put(
        f"{settings.API_V1_STR}/appointments/{appt_id}",
        json={"appointment_time": "2026-11-12T14:00:00Z", "status": "rescheduled"},
    )
    assert resched.status_code == 200
    assert resched.json()["status"] == "rescheduled"

    # 5. Cancel Appointment
    cancel_res = client.post(
        f"{settings.API_V1_STR}/appointments/{appt_id}/cancel?reason=Schedule%20Conflict"
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"


def test_call_management_and_simulation(client: TestClient) -> None:
    """Test call simulation, filtering, and retrieval."""
    # 1. Simulate an Inbound Call
    sim_res = client.post(
        f"{settings.API_V1_STR}/calls/simulate",
        json={
            "caller_name": "Divya Prakash",
            "caller_phone": "+91 98765 11223",
            "call_type": "incoming",
            "scenario": "Cardiology Booking",
            "duration_seconds": 120,
        },
    )
    assert sim_res.status_code == 201
    sim_data = sim_res.json()
    call_id = sim_data["id"]
    assert sim_data["status"] == "completed"
    assert "transcript" in sim_data

    # 2. List calls with filter
    list_res = client.get(f"{settings.API_V1_STR}/calls?call_type=incoming")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 3. Retrieve call detail
    detail_res = client.get(f"{settings.API_V1_STR}/calls/{call_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["caller_name"] == "Divya Prakash"


def test_reminders_and_reports(client: TestClient) -> None:
    """Test reminder dispatch and reports generation."""
    # 1. List Reminders
    rem_list = client.get(f"{settings.API_V1_STR}/reminders")
    assert rem_list.status_code == 200

    # 2. Dashboard Stats
    stats_res = client.get(f"{settings.API_V1_STR}/dashboard/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_incoming_calls" in stats
    assert "total_appointments" in stats

    # 3. Reports Summary
    rep_res = client.get(f"{settings.API_V1_STR}/reports/summary?range_type=7d")
    assert rep_res.status_code == 200
    rep = rep_res.json()
    assert "metrics" in rep
    assert "timeline" in rep

