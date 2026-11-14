"""Add AI conversational engine configuration and telemetry fields.

Revision ID: 004
Revises: 003
Create Date: 2026-11-11 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, Sequence[str], None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ai_provider, ai_model, enable_tanglish to assistant_configs; detected_language, metadata_json to conversation_sessions."""
    with op.batch_alter_table('assistant_configs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_provider', sa.String(length=50), server_default='mock', nullable=False))
        batch_op.add_column(sa.Column('ai_model', sa.String(length=50), server_default='gpt-4o-mini', nullable=False))
        batch_op.add_column(sa.Column('enable_tanglish', sa.Boolean(), server_default='1', nullable=False))

    with op.batch_alter_table('conversation_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('detected_language', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('metadata_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove AI conversational engine fields."""
    with op.batch_alter_table('conversation_sessions', schema=None) as batch_op:
        batch_op.drop_column('metadata_json')
        batch_op.drop_column('detected_language')

    with op.batch_alter_table('assistant_configs', schema=None) as batch_op:
        batch_op.drop_column('enable_tanglish')
        batch_op.drop_column('ai_model')
        batch_op.drop_column('ai_provider')
