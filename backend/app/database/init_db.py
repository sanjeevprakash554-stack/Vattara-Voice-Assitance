"""Database initialization and baseline tenant provisioning."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.database.base import Base
from app.models.assistant import AssistantConfig, FAQ, Service
from app.models.business import Business
from app.models.integration import BusinessIntegration
from app.models.subscription import Invoice, Subscription
from app.models.user import User

logger = get_logger(__name__)


def init_db(db: Session) -> None:
    """Create all registered database tables and provision initial tenant if empty."""
    # Ensure all tables exist on the active session's bind
    Base.metadata.create_all(bind=db.get_bind())

    # Check if a business already exists
    existing_business = db.scalar(select(Business).limit(1))
    if existing_business:
        logger.info("Database already initialized with business: %s", existing_business.name)
        return

    logger.info("Provisioning baseline tenant for Vattara Voice Assistance...")

    # 1. Create Business Tenant
    business = Business(
        id="demo-biz-vattara-health",
        name="Vattara City Clinic & Diagnostics",
        vertical="clinic",
        phone="+91 44 2828 9000",
        email="contact@vattaraclinic.com",
        timezone="Asia/Kolkata",
        address="42, Anna Salai, Chennai, Tamil Nadu 600002",
        is_active=True,
    )
    db.add(business)

    # 2. Create Admin and Super Admin Users (Hardened for Production)
    superuser_password = settings.FIRST_SUPERUSER_PASSWORD
    superuser_email = settings.FIRST_SUPERUSER_EMAIL or "superadmin@vattara.com"

    if settings.ENVIRONMENT.lower() == "production":
        if not superuser_password:
            logger.warning(
                "Production environment detected: No FIRST_SUPERUSER_PASSWORD configured. "
                "Skipping initial superadmin seeding. Run python -m app.scripts.create_superuser to safely initialize."
            )
        else:
            super_admin_user = User(
                business_id=business.id,
                email=superuser_email,
                full_name="Platform Super Admin",
                hashed_password=get_password_hash(superuser_password),
                role="super_admin",
                is_active=True,
            )
            db.add(super_admin_user)
            logger.info("Successfully provisioned initial production superadmin (%s)", superuser_email)
    else:
        # Development / Testing environment
        dev_admin_pass = "Admin@123"
        dev_superadmin_pass = superuser_password or "SuperAdmin@123"

        admin_user = User(
            id="demo-user-admin",
            business_id=business.id,
            email="admin@vattara.com",
            full_name="Dr. Rajesh Kumar",
            hashed_password=get_password_hash(dev_admin_pass),
            role="admin",
            is_active=True,
        )
        db.add(admin_user)

        super_admin_user = User(
            id="demo-user-superadmin",
            business_id=business.id,
            email=superuser_email,
            full_name="Platform Super Admin",
            hashed_password=get_password_hash(dev_superadmin_pass),
            role="super_admin",
            is_active=True,
        )
        db.add(super_admin_user)

    # 3. Create Assistant Configuration
    assistant_config = AssistantConfig(
        id="demo-assistant-config",
        business_id=business.id,
        assistant_name="Vattara Voice AI",
        language="en-US",
        voice="alloy",
        ai_provider="gemini",
        ai_model="gemini-3.1-flash-lite",
        stt_provider="sarvam",
        tts_provider="sarvam",
        system_prompt=(
            "You are Vattara AI, the courteous and intelligent voice receptionist for "
            "Vattara City Clinic & Diagnostics. You handle patient triage, schedule appointments, "
            "explain consultation fees and clinical timings, and answer FAQs. Always be compassionate, "
            "precise, and professional."
        ),
        business_info=(
            "Vattara City Clinic & Diagnostics is a multi-specialty healthcare centre offering "
            "general physician consultations, cardiology checkups, pediatrics, and diagnostic lab services."
        ),
        working_hours=(
            '{"monday":{"open":"08:30","close":"20:00","enabled":true},'
            '"tuesday":{"open":"08:30","close":"20:00","enabled":true},'
            '"wednesday":{"open":"08:30","close":"20:00","enabled":true},'
            '"thursday":{"open":"08:30","close":"20:00","enabled":true},'
            '"friday":{"open":"08:30","close":"20:00","enabled":true},'
            '"saturday":{"open":"09:00","close":"18:00","enabled":true},'
            '"sunday":{"open":"10:00","close":"14:00","enabled":false}}'
        ),
        is_active=True,
    )
    db.add(assistant_config)

    # 4. Create Clinic Services
    services_data = [
        ("General Physician Consultation", "Routine health examination and diagnosis", 30, 500.0),
        ("Cardiology Consultation & ECG", "Comprehensive heart health evaluation", 45, 1200.0),
        ("Pediatric Health Checkup", "Complete child health and immunization review", 30, 700.0),
        ("Full Body Blood Diagnostics", "Complete blood count, lipid, and diabetes panel", 15, 1500.0),
        ("Dental Cleaning & Polish", "Preventative dental scaling and oral screening", 40, 800.0),
    ]
    for idx, (name, desc, duration, price) in enumerate(services_data, start=1):
        srv = Service(
            id=f"demo-service-{idx}",
            business_id=business.id,
            name=name,
            description=desc,
            duration_minutes=duration,
            price=price,
            is_active=True,
        )
        db.add(srv)

    # 5. Create Clinical FAQs
    faqs_data = [
        ("Appointments", "How do I book an appointment?", "You can book directly through this voice call, via our online portal, or by visiting our reception."),
        ("Consultation", "What is the consultation fee for a General Physician?", "Our General Physician consultation fee is ₹500."),
        ("Timings", "What are your outpatient clinic timings?", "We are open Monday to Friday 8:30 AM to 8:00 PM, and Saturday 9:00 AM to 6:00 PM."),
        ("Insurance", "Do you accept cashless health insurance?", "Yes, we support all major TPA and private health insurance cashless claims."),
        ("Emergency", "How are medical emergencies handled?", "Our triage unit provides immediate stabilization. For acute life-threatening situations, we coordinate immediate hospital ICU transfers."),
    ]
    for idx, (cat, q, a) in enumerate(faqs_data, start=1):
        faq = FAQ(
            id=f"demo-faq-{idx}",
            business_id=business.id,
            category=cat,
            question=q,
            answer=a,
            is_active=True,
        )
        db.add(faq)

    now = datetime.now(timezone.utc)

    # 6. Create Baseline Subscription & Invoice
    subscription = Subscription(
        id="demo-subscription-1",
        business_id=business.id,
        plan_name="professional",
        billing_cycle="monthly",
        status="active",
        current_period_start=now - timedelta(days=10),
        current_period_end=now + timedelta(days=20),
        monthly_call_minutes_limit=1500,
        used_call_minutes=0,
        max_assistants=2,
        max_staff=10,
    )
    db.add(subscription)

    invoice = Invoice(
        id="demo-invoice-1",
        business_id=business.id,
        subscription_id=subscription.id,
        invoice_number="INV-2026-001",
        amount=4999.0,
        currency="INR",
        status="paid",
        billing_date=now - timedelta(days=10),
        paid_at=now - timedelta(days=10),
    )
    db.add(invoice)

    # 7. Create Plivo Telephony Integration
    integration = BusinessIntegration(
        id="demo-integration-1",
        business_id=business.id,
        primary_provider="plivo",
        plivo_phone_number=settings.PLIVO_PHONE_NUMBER or "+918040008888",
        is_plivo_verified=bool(settings.is_plivo_configured),
        inbound_webhook_url="/api/v1/plivo/incoming",
    )
    db.add(integration)

    db.commit()
    logger.info("Baseline database provisioning complete!")
