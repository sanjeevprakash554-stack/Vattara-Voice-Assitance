"""Add SaaS platform subscriptions, usage limits, invoices, and tenant integrations.

Revision ID: 006
Revises: 005
Create Date: 2026-11-11 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, Sequence[str], None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 7 SaaS subscriptions, invoices, integrations, and assistant enhancements."""
    # 1. Add stt_provider, tts_provider, fallback_number to assistant_configs
    with op.batch_alter_table('assistant_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stt_provider', sa.String(length=50), server_default='deepgram', nullable=False))
        batch_op.add_column(sa.Column('tts_provider', sa.String(length=50), server_default='openai', nullable=False))
        batch_op.add_column(sa.Column('fallback_number', sa.String(length=50), nullable=True))

    # 2. Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('business_id', sa.String(length=36), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_name', sa.String(length=50), server_default='starter', nullable=False),
        sa.Column('billing_cycle', sa.String(length=20), server_default='monthly', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('monthly_call_minutes_limit', sa.Integer(), server_default='500', nullable=False),
        sa.Column('used_call_minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_assistants', sa.Integer(), server_default='1', nullable=False),
        sa.Column('max_staff', sa.Integer(), server_default='5', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('business_id', name='uq_subscriptions_business_id'),
    )
    op.create_index('ix_subscriptions_business_id', 'subscriptions', ['business_id'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])

    # 3. Create invoices table
    op.create_table(
        'invoices',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('business_id', sa.String(length=36), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('subscription_id', sa.String(length=36), sa.ForeignKey('subscriptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('amount', sa.Float(), server_default='0.0', nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='INR', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='paid', nullable=False),
        sa.Column('billing_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('pdf_url', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('invoice_number', name='uq_invoices_invoice_number'),
    )
    op.create_index('ix_invoices_business_id', 'invoices', ['business_id'])
    op.create_index('ix_invoices_subscription_id', 'invoices', ['subscription_id'])
    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'])
    op.create_index('ix_invoices_status', 'invoices', ['status'])

    # 4. Create business_integrations table
    op.create_table(
        'business_integrations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('business_id', sa.String(length=36), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('primary_provider', sa.String(length=50), server_default='twilio', nullable=False),
        sa.Column('twilio_account_sid', sa.String(length=100), nullable=True),
        sa.Column('twilio_phone_number', sa.String(length=50), nullable=True),
        sa.Column('is_twilio_verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('smartflo_caller_id', sa.String(length=50), nullable=True),
        sa.Column('smartflo_api_key', sa.String(length=100), nullable=True),
        sa.Column('is_smartflo_verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('exotel_sid', sa.String(length=100), nullable=True),
        sa.Column('exotel_caller_id', sa.String(length=50), nullable=True),
        sa.Column('is_exotel_verified', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('inbound_webhook_url', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('business_id', name='uq_business_integrations_business_id'),
    )
    op.create_index('ix_business_integrations_business_id', 'business_integrations', ['business_id'])


def downgrade() -> None:
    """Revert Phase 7 SaaS additions."""
    op.drop_index('ix_business_integrations_business_id', table_name='business_integrations')
    op.drop_table('business_integrations')

    op.drop_index('ix_invoices_status', table_name='invoices')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.drop_index('ix_invoices_subscription_id', table_name='invoices')
    op.drop_index('ix_invoices_business_id', table_name='invoices')
    op.drop_table('invoices')

    op.drop_index('ix_subscriptions_status', table_name='subscriptions')
    op.drop_index('ix_subscriptions_business_id', table_name='subscriptions')
    op.drop_table('subscriptions')

    with op.batch_alter_table('assistant_configs', schema=None) as batch_op:
        batch_op.drop_column('fallback_number')
        batch_op.drop_column('tts_provider')
        batch_op.drop_column('stt_provider')
