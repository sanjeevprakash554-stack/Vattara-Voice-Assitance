"""Add business_hours, staff_schedules, and appointment scheduling fields.

Revision ID: 003
Revises: 002
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, Sequence[str], None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create business_hours and staff_schedules tables; add scheduling fields to appointments."""
    # 1. Create business_hours
    op.create_table(
        'business_hours',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('open_time', sa.String(length=8), nullable=False),
        sa.Column('close_time', sa.String(length=8), nullable=False),
        sa.Column('is_closed', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('business_hours', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_business_hours_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_business_hours_day_of_week'), ['day_of_week'], unique=False)

    # 2. Create staff_schedules
    op.create_table(
        'staff_schedules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('business_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('staff_name', sa.String(length=200), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.String(length=8), nullable=False),
        sa.Column('end_time', sa.String(length=8), nullable=False),
        sa.Column('break_start', sa.String(length=8), nullable=True),
        sa.Column('break_end', sa.String(length=8), nullable=True),
        sa.Column('slot_duration_minutes', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('staff_schedules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_staff_schedules_business_id'), ['business_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_staff_schedules_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_staff_schedules_day_of_week'), ['day_of_week'], unique=False)

    # 3. Add fields to appointments
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('staff_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('reschedule_reason', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('cancel_reason', sa.String(length=255), nullable=True))
        batch_op.create_foreign_key('fk_appointments_staff_id', 'users', ['staff_id'], ['id'], ondelete='SET NULL')
        batch_op.create_index(batch_op.f('ix_appointments_staff_id'), ['staff_id'], unique=False)


def downgrade() -> None:
    """Drop business_hours and staff_schedules; remove added fields from appointments."""
    with op.batch_alter_table('appointments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_appointments_staff_id'))
        batch_op.drop_constraint('fk_appointments_staff_id', type_='foreignkey')
        batch_op.drop_column('cancel_reason')
        batch_op.drop_column('reschedule_reason')
        batch_op.drop_column('staff_id')

    op.drop_table('staff_schedules')
    op.drop_table('business_hours')
