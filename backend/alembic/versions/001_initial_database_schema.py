"""create initial database models

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-06 12:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Businesses
    op.create_table(
        "businesses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_name", sa.String(length=255), nullable=False),
        sa.Column("business_type", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_businesses_id", "businesses", ["id"], unique=False)
    op.create_index("ix_businesses_business_name", "businesses", ["business_name"], unique=False)
    op.create_index("ix_businesses_business_type", "businesses", ["business_type"], unique=False)
    op.create_index("ix_businesses_email", "businesses", ["email"], unique=True)

    # 2. Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), server_default="receptionist", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_index("ix_users_business_id", "users", ["business_id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    # 3. Customers
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_id", "customers", ["id"], unique=False)
    op.create_index("ix_customers_business_id", "customers", ["business_id"], unique=False)
    op.create_index("ix_customers_customer_name", "customers", ["customer_name"], unique=False)
    op.create_index("ix_customers_phone_number", "customers", ["phone_number"], unique=False)
    op.create_index("ix_customers_email", "customers", ["email"], unique=False)

    # 4. Appointments
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("appointment_date", sa.Date(), nullable=False),
        sa.Column("appointment_time", sa.Time(), nullable=False),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="scheduled", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_appointments_id", "appointments", ["id"], unique=False)
    op.create_index("ix_appointments_business_id", "appointments", ["business_id"], unique=False)
    op.create_index("ix_appointments_customer_id", "appointments", ["customer_id"], unique=False)
    op.create_index("ix_appointments_appointment_date", "appointments", ["appointment_date"], unique=False)
    op.create_index("ix_appointments_status", "appointments", ["status"], unique=False)

    # 5. Call Histories
    op.create_table(
        "call_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("call_type", sa.String(length=50), nullable=False),
        sa.Column("call_status", sa.String(length=50), nullable=False),
        sa.Column("call_duration", sa.Integer(), server_default="0", nullable=False),
        sa.Column("recording_url", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_histories_id", "call_histories", ["id"], unique=False)
    op.create_index("ix_call_histories_business_id", "call_histories", ["business_id"], unique=False)
    op.create_index("ix_call_histories_customer_id", "call_histories", ["customer_id"], unique=False)
    op.create_index("ix_call_histories_phone_number", "call_histories", ["phone_number"], unique=False)
    op.create_index("ix_call_histories_call_type", "call_histories", ["call_type"], unique=False)
    op.create_index("ix_call_histories_call_status", "call_histories", ["call_status"], unique=False)

    # 6. Reminders
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("reminder_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reminder_type", sa.String(length=50), server_default="sms", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reminders_id", "reminders", ["id"], unique=False)
    op.create_index("ix_reminders_business_id", "reminders", ["business_id"], unique=False)
    op.create_index("ix_reminders_appointment_id", "reminders", ["appointment_id"], unique=False)
    op.create_index("ix_reminders_reminder_datetime", "reminders", ["reminder_datetime"], unique=False)
    op.create_index("ix_reminders_reminder_type", "reminders", ["reminder_type"], unique=False)
    op.create_index("ix_reminders_status", "reminders", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("reminders")
    op.drop_table("call_histories")
    op.drop_table("appointments")
    op.drop_table("customers")
    op.drop_table("users")
    op.drop_table("businesses")
