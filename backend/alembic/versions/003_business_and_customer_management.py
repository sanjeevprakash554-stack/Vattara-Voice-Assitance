"""add business profile fields, working hours, service categories, business services, and customer extension

Revision ID: 003_business_and_customer
Revises: 002_auth_and_roles
Create Date: 2026-11-06 13:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_business_and_customer"
down_revision: Union[str, None] = "002_auth_and_roles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend businesses table
    op.add_column("businesses", sa.Column("website", sa.String(length=255), nullable=True))
    op.add_column("businesses", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("businesses", sa.Column("logo_url", sa.String(length=1024), nullable=True))
    op.add_column("businesses", sa.Column("timezone", sa.String(length=50), server_default="UTC", nullable=False))

    # 2. Extend customers table
    op.add_column("customers", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("customers", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_index("ix_customers_is_active", "customers", ["is_active"], unique=False)

    # 3. Create business_working_hours table
    op.create_table(
        "business_working_hours",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("opening_time", sa.Time(), nullable=True),
        sa.Column("closing_time", sa.Time(), nullable=True),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "day_of_week", name="uq_business_day_of_week"),
    )
    op.create_index("ix_business_working_hours_id", "business_working_hours", ["id"], unique=False)
    op.create_index("ix_business_working_hours_business_id", "business_working_hours", ["business_id"], unique=False)
    op.create_index("ix_business_working_hours_day_of_week", "business_working_hours", ["day_of_week"], unique=False)

    # 4. Create service_categories table
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("category_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_categories_id", "service_categories", ["id"], unique=False)
    op.create_index("ix_service_categories_business_id", "service_categories", ["business_id"], unique=False)
    op.create_index("ix_service_categories_category_name", "service_categories", ["category_name"], unique=False)
    op.create_index("ix_service_categories_is_active", "service_categories", ["is_active"], unique=False)

    # 5. Create business_services table
    op.create_table(
        "business_services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("business_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("service_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="USD", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["service_categories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_business_services_id", "business_services", ["id"], unique=False)
    op.create_index("ix_business_services_business_id", "business_services", ["business_id"], unique=False)
    op.create_index("ix_business_services_category_id", "business_services", ["category_id"], unique=False)
    op.create_index("ix_business_services_service_name", "business_services", ["service_name"], unique=False)
    op.create_index("ix_business_services_is_active", "business_services", ["is_active"], unique=False)


def downgrade() -> None:
    # 1. Drop business_services table
    op.drop_table("business_services")

    # 2. Drop service_categories table
    op.drop_table("service_categories")

    # 3. Drop business_working_hours table
    op.drop_table("business_working_hours")

    # 4. Revert customers columns
    op.drop_index("ix_customers_is_active", table_name="customers")
    op.drop_column("customers", "is_active")
    op.drop_column("customers", "notes")
    op.drop_column("customers", "address")

    # 5. Revert businesses columns
    op.drop_column("businesses", "timezone")
    op.drop_column("businesses", "logo_url")
    op.drop_column("businesses", "description")
    op.drop_column("businesses", "website")
