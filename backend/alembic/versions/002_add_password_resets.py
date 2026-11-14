"""Add password_resets table for secure reset verification.

Revision ID: 002
Revises: 001
Create Date: 2026-11-11 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create password_resets table with audit indexes."""
    op.create_table(
        'password_resets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('password_resets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_resets_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_password_resets_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_password_resets_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    """Drop password_resets table."""
    op.drop_table('password_resets')
