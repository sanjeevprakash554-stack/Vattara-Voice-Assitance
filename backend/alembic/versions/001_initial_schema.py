"""Initial database schema with core models.

Revision ID: 001
Revises: 
Create Date: 2026-11-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial core database tables."""
    # businesses
    op.create_table(
        'businesses',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('vertical', sa.String(length=50), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('businesses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_businesses_email'), ['email'], unique=True)

    # assistant_configs
    op.create_table(
        'assistant_configs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('assistant_name', sa.String(length=100), nullable=False),
        sa.Column('language', sa.String(length=20), nullable=False),
        sa.Column('voice', sa.String(length=50), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('business_info', sa.Text(), nullable=True),
        sa.Column('working_hours', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('assistant_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assistant_configs_business_id'), ['business_id'], unique=True)

    # customers
    op.create_table(
        'customers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('total_calls', sa.Integer(), nullable=False),
        sa.Column('total_appointments', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_customers_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_customers_phone'), ['phone'], unique=False)

    # faqs
    op.create_table(
        'faqs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('faqs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_faqs_business_id'), ['business_id'], unique=False)

    # services
    op.create_table(
        'services',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_business_id'), ['business_id'], unique=False)

    # users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    # appointments
    op.create_table(
        'appointments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('service_id', sa.String(length=36), nullable=True),
        sa.Column('appointment_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_appointments_appointment_time'), ['appointment_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointments_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointments_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointments_service_id'), ['service_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_appointments_status'), ['status'], unique=False)

    # calls
    op.create_table(
        'calls',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('customer_id', sa.String(length=36), nullable=True),
        sa.Column('caller_name', sa.String(length=200), nullable=True),
        sa.Column('caller_phone', sa.String(length=50), nullable=False),
        sa.Column('call_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('recording_url', sa.String(length=500), nullable=True),
        sa.Column('initiated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('calls', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_calls_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_calls_caller_phone'), ['caller_phone'], unique=False)
        batch_op.create_index(batch_op.f('ix_calls_customer_id'), ['customer_id'], unique=False)

    # conversation_sessions
    op.create_table(
        'conversation_sessions',
        sa.Column('call_sid', sa.String(length=50), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('caller_phone', sa.String(length=50), nullable=False),
        sa.Column('customer_name', sa.String(length=200), nullable=True),
        sa.Column('service_id', sa.String(length=36), nullable=True),
        sa.Column('service_name', sa.String(length=200), nullable=True),
        sa.Column('appointment_datetime_iso', sa.String(length=50), nullable=True),
        sa.Column('step', sa.String(length=50), nullable=False),
        sa.Column('language', sa.String(length=20), nullable=False),
        sa.Column('intent', sa.String(length=50), nullable=True),
        sa.Column('booking_id', sa.String(length=36), nullable=True),
        sa.Column('dialog_history', sa.Text(), nullable=True),
        sa.Column('last_speech_result', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['appointments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('call_sid'),
    )
    with op.batch_alter_table('conversation_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversation_sessions_booking_id'), ['booking_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversation_sessions_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversation_sessions_call_sid'), ['call_sid'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversation_sessions_caller_phone'), ['caller_phone'], unique=False)

    # reminders
    op.create_table(
        'reminders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('appointment_id', sa.String(length=36), nullable=True),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('reminder_type', sa.String(length=30), nullable=False),
        sa.Column('scheduled_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['appointment_id'], ['appointments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reminders_appointment_id'), ['appointment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reminders_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reminders_customer_id'), ['customer_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reminders_scheduled_time'), ['scheduled_time'], unique=False)
        batch_op.create_index(batch_op.f('ix_reminders_status'), ['status'], unique=False)


def downgrade() -> None:
    """Drop initial core database tables in reverse dependency order."""
    op.drop_table('reminders')
    op.drop_table('conversation_sessions')
    op.drop_table('calls')
    op.drop_table('appointments')
    op.drop_table('users')
    op.drop_table('services')
    op.drop_table('faqs')
    op.drop_table('customers')
    op.drop_table('assistant_configs')
    op.drop_table('businesses')
