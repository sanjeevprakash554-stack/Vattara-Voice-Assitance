"""Add automated appointment reminders, outbound calling fields, and reminder settings.

Revision ID: 005
Revises: 004
Create Date: 2026-11-11 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, Sequence[str], None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 6 reminder enhancements and reminder_settings table."""
    # 1. Add outbound call tracking and retry fields to reminders
    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('call_sid', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False))
        batch_op.add_column(sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('customer_response', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('error_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('interval_tag', sa.String(length=20), nullable=True))
        batch_op.create_index('ix_reminders_call_sid', ['call_sid'], unique=False)

    # 2. Create reminder_settings table
    op.create_table(
        'reminder_settings',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('business_id', sa.String(length=36), sa.ForeignKey('businesses.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reminder_intervals_hours', sa.String(length=50), server_default='24,2', nullable=False),
        sa.Column('calling_start_time', sa.String(length=10), server_default='09:00', nullable=False),
        sa.Column('calling_end_time', sa.String(length=10), server_default='20:00', nullable=False),
        sa.Column('max_retries', sa.Integer(), server_default='3', nullable=False),
        sa.Column('retry_delay_minutes', sa.Integer(), server_default='15', nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('default_channel', sa.String(length=20), server_default='voice', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('business_id', name='uq_reminder_settings_business_id'),
    )
    op.create_index('ix_reminder_settings_business_id', 'reminder_settings', ['business_id'])


def downgrade() -> None:
    """Revert Phase 6 reminder enhancements."""
    op.drop_index('ix_reminder_settings_business_id', table_name='reminder_settings')
    op.drop_table('reminder_settings')

    with op.batch_alter_table('reminders', schema=None) as batch_op:
        batch_op.drop_index('ix_reminders_call_sid')
        batch_op.drop_column('interval_tag')
        batch_op.drop_column('error_message')
        batch_op.drop_column('customer_response')
        batch_op.drop_column('next_retry_at')
        batch_op.drop_column('max_retries')
        batch_op.drop_column('retry_count')
        batch_op.drop_column('call_sid')
