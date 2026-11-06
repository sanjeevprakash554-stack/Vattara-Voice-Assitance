"""add authentication status fields and nullable business for super admin

Revision ID: 002_auth_and_roles
Revises: 001_initial_schema
Create Date: 2026-11-06 12:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_auth_and_roles"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add is_active to businesses
    op.add_column(
        "businesses",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_businesses_is_active", "businesses", ["is_active"], unique=False)

    # 2. Add is_active to users
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)

    # 3. Allow business_id in users to be nullable for Super Admin platform operators
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "business_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    # 1. Revert business_id in users to nullable=False
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "business_id",
            existing_type=sa.Integer(),
            nullable=False,
        )

    # 2. Drop is_active from users
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_column("users", "is_active")

    # 3. Drop is_active from businesses
    op.drop_index("ix_businesses_is_active", table_name="businesses")
    op.drop_column("businesses", "is_active")
