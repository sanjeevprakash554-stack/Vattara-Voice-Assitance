"""Comprehensive tests for SQLAlchemy models and database relationships."""

from datetime import date, datetime, time, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.appointment import Appointment
from app.models.business import Business
from app.models.call_history import CallHistory
from app.models.customer import Customer
from app.models.reminder import Reminder
from app.models.user import User


def test_create_business(db_session: Session) -> None:
    """Test creating a business record with audit timestamps."""
    business = Business(
        business_name="Metro City Hospital",
        business_type="hospital",
        email="contact@metrohospital.com",
        phone_number="+1-555-0199",
        address="100 Healthcare Blvd, Metro City",
    )
    db_session.add(business)
    db_session.flush()

    assert business.id is not None
    assert business.business_name == "Metro City Hospital"
    assert business.business_type == "hospital"
    assert business.created_at is not None
    assert business.updated_at is not None


def test_business_users_relationship(db_session: Session) -> None:
    """Test one-to-many relationship between Business and User."""
    business = Business(
        business_name="Grand Horizon Hotel",
        business_type="hotel",
        email="frontdesk@grandhorizon.com",
        phone_number="+1-555-0200",
    )
    db_session.add(business)
    db_session.flush()

    raw_password = "SecurePassword123!"
    user = User(
        business_id=business.id,
        full_name="Sarah Jenkins",
        email="sarah.jenkins@grandhorizon.com",
        password_hash=get_password_hash(raw_password),
        role="receptionist",
    )
    db_session.add(user)
    db_session.flush()

    assert user.id is not None
    assert user.business_id == business.id
    assert user.business.business_name == "Grand Horizon Hotel"
    assert len(business.users) == 1
    assert business.users[0].email == "sarah.jenkins@grandhorizon.com"

    # Password security check
    assert user.password_hash != raw_password
    assert verify_password(raw_password, user.password_hash) is True
    assert verify_password("WrongPassword!", user.password_hash) is False


def test_business_customers_relationship(db_session: Session) -> None:
    """Test one-to-many relationship between Business and Customer."""
    business = Business(
        business_name="Luxe Salon & Spa",
        business_type="salon",
        email="info@luxesalon.com",
    )
    db_session.add(business)
    db_session.flush()

    customer = Customer(
        business_id=business.id,
        customer_name="Alice Smith",
        phone_number="+1-555-1234",
        email="alice@example.com",
    )
    db_session.add(customer)
    db_session.flush()

    assert customer.id is not None
    assert customer.business.business_name == "Luxe Salon & Spa"
    assert len(business.customers) == 1
    assert business.customers[0].customer_name == "Alice Smith"


def test_appointment_relationships(db_session: Session) -> None:
    """Test Appointment relationships with Business and Customer."""
    business = Business(
        business_name="Apex Auto Care",
        business_type="automobile",
        email="service@apexauto.com",
    )
    db_session.add(business)
    db_session.flush()

    customer = Customer(
        business_id=business.id,
        customer_name="Bob Miller",
        phone_number="+1-555-5678",
        email="bob@example.com",
    )
    db_session.add(customer)
    db_session.flush()

    appointment = Appointment(
        business_id=business.id,
        customer_id=customer.id,
        appointment_date=date(2026, 12, 1),
        appointment_time=time(10, 30),
        service_name="Full Synthetic Oil Change & Brake Inspection",
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.flush()

    assert appointment.id is not None
    assert appointment.business.business_name == "Apex Auto Care"
    assert appointment.customer.customer_name == "Bob Miller"
    assert len(business.appointments) == 1
    assert len(customer.appointments) == 1
    assert customer.appointments[0].service_name == "Full Synthetic Oil Change & Brake Inspection"


def test_call_history_relationships(db_session: Session) -> None:
    """Test CallHistory relationship with Business and Customer."""
    business = Business(
        business_name="Summit Real Estate",
        business_type="real_estate",
        email="inquiries@summitrealty.com",
    )
    db_session.add(business)
    db_session.flush()

    customer = Customer(
        business_id=business.id,
        customer_name="David Wright",
        phone_number="+1-555-9876",
        email="david@example.com",
    )
    db_session.add(customer)
    db_session.flush()

    call = CallHistory(
        business_id=business.id,
        customer_id=customer.id,
        phone_number="+1-555-9876",
        call_type="inbound",
        call_status="completed",
        call_duration=145,
        recording_url="https://s3.amazonaws.com/voice-recordings/call_123.wav",
    )
    db_session.add(call)
    db_session.flush()

    assert call.id is not None
    assert call.business.business_name == "Summit Real Estate"
    assert call.customer is not None
    assert call.customer.customer_name == "David Wright"
    assert len(business.call_histories) == 1
    assert len(customer.call_histories) == 1


def test_reminder_relationships(db_session: Session) -> None:
    """Test Reminder relationships with Appointment and Business."""
    business = Business(
        business_name="CarePlus Dental Clinic",
        business_type="hospital",
        email="reception@careplusdental.com",
    )
    db_session.add(business)
    db_session.flush()

    customer = Customer(
        business_id=business.id,
        customer_name="Emma Watson",
        phone_number="+1-555-4321",
        email="emma@example.com",
    )
    db_session.add(customer)
    db_session.flush()

    appointment = Appointment(
        business_id=business.id,
        customer_id=customer.id,
        appointment_date=date(2026, 12, 10),
        appointment_time=time(14, 0),
        service_name="Annual Dental Cleaning",
        status="confirmed",
    )
    db_session.add(appointment)
    db_session.flush()

    reminder = Reminder(
        business_id=business.id,
        appointment_id=appointment.id,
        reminder_datetime=datetime(2026, 12, 9, 14, 0, tzinfo=timezone.utc),
        reminder_type="sms",
        status="pending",
    )
    db_session.add(reminder)
    db_session.flush()

    assert reminder.id is not None
    assert reminder.business.business_name == "CarePlus Dental Clinic"
    assert reminder.appointment.service_name == "Annual Dental Cleaning"
    assert len(business.reminders) == 1
    assert len(appointment.reminders) == 1
    assert appointment.reminders[0].reminder_type == "sms"


def test_cascade_delete_business(db_session: Session) -> None:
    """Verify that deleting a business cascades to delete all linked child records."""
    business = Business(
        business_name="Test Cascade Org",
        business_type="hotel",
        email="cascade@testhotel.com",
    )
    db_session.add(business)
    db_session.flush()

    user = User(
        business_id=business.id,
        full_name="Staff One",
        email="staff@testhotel.com",
        password_hash="hashed_pw",
        role="staff",
    )
    customer = Customer(
        business_id=business.id,
        customer_name="Guest One",
        phone_number="+1-555-0001",
    )
    db_session.add_all([user, customer])
    db_session.flush()

    appointment = Appointment(
        business_id=business.id,
        customer_id=customer.id,
        appointment_date=date(2026, 11, 20),
        appointment_time=time(9, 0),
        service_name="Suite Reservation",
    )
    db_session.add(appointment)
    db_session.flush()

    reminder = Reminder(
        business_id=business.id,
        appointment_id=appointment.id,
        reminder_datetime=datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc),
    )
    call = CallHistory(
        business_id=business.id,
        customer_id=customer.id,
        phone_number="+1-555-0001",
        call_type="inbound",
        call_status="completed",
        call_duration=60,
    )
    db_session.add_all([reminder, call])
    db_session.flush()

    # Delete business
    db_session.delete(business)
    db_session.flush()

    # All cascaded children should be deleted
    assert db_session.get(Business, business.id) is None
    assert db_session.get(User, user.id) is None
    assert db_session.get(Customer, customer.id) is None
    assert db_session.get(Appointment, appointment.id) is None
    assert db_session.get(Reminder, reminder.id) is None
    assert db_session.get(CallHistory, call.id) is None


def test_customer_delete_set_null_call_history(db_session: Session) -> None:
    """Verify that deleting a Customer sets customer_id to NULL on CallHistory, preserving call logs."""
    business = Business(
        business_name="Log Retention Corp",
        business_type="hospital",
        email="logs@retention.com",
    )
    db_session.add(business)
    db_session.flush()

    customer = Customer(
        business_id=business.id,
        customer_name="Transient Caller",
        phone_number="+1-555-9999",
    )
    db_session.add(customer)
    db_session.flush()

    call = CallHistory(
        business_id=business.id,
        customer_id=customer.id,
        phone_number="+1-555-9999",
        call_type="inbound",
        call_status="completed",
        call_duration=120,
    )
    db_session.add(call)
    db_session.flush()

    call_id = call.id
    customer_id = customer.id

    # Delete customer only
    db_session.delete(customer)
    db_session.flush()

    # Customer is deleted, but call record still exists with customer_id=None
    assert db_session.get(Customer, customer_id) is None
    preserved_call = db_session.get(CallHistory, call_id)
    assert preserved_call is not None
    assert preserved_call.customer_id is None
    assert preserved_call.business_id == business.id


def test_unique_email_constraint(db_session: Session) -> None:
    """Verify unique constraint on Business email."""
    business_1 = Business(
        business_name="Unique Clinic 1",
        business_type="hospital",
        email="duplicate@clinic.com",
    )
    db_session.add(business_1)
    db_session.flush()

    business_2 = Business(
        business_name="Unique Clinic 2",
        business_type="hospital",
        email="duplicate@clinic.com",
    )
    db_session.add(business_2)

    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
