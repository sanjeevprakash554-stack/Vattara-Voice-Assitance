"""Tests for Alembic migration script execution and rollback."""

import os
from pathlib import Path
from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Verify that Alembic migrations apply cleanly and can be rolled back to base."""
    db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    # Set temporary database URL in environment for Alembic
    os.environ["SQLALCHEMY_DATABASE_URI"] = db_url

    ini_path = BACKEND_DIR / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    # Test UPGRADE to head
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "businesses",
        "users",
        "customers",
        "appointments",
        "call_histories",
        "reminders",
        "business_working_hours",
        "service_categories",
        "business_services",
        "alembic_version",
    }
    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"

    # Verify column structures on businesses table
    columns = {col["name"]: col for col in inspector.get_columns("businesses")}
    assert "business_name" in columns
    assert "business_type" in columns
    assert "email" in columns
    assert "is_active" in columns
    assert "website" in columns
    assert "timezone" in columns

    # Verify column structures on customers table
    cust_columns = {col["name"]: col for col in inspector.get_columns("customers")}
    assert "address" in cust_columns
    assert "notes" in cust_columns
    assert "is_active" in cust_columns

    # Verify column structures on users table
    user_columns = {col["name"]: col for col in inspector.get_columns("users")}
    assert "email" in user_columns
    assert "password_hash" in user_columns
    assert "is_active" in user_columns

    # Test DOWNGRADE to base
    command.downgrade(cfg, "base")

    inspector_after = inspect(engine)
    tables_after = set(inspector_after.get_table_names())
    for tbl in expected_tables - {"alembic_version"}:
        assert tbl not in tables_after, f"Table {tbl} was not dropped during downgrade"

    engine.dispose()
    # Clean up environment override
    os.environ.pop("SQLALCHEMY_DATABASE_URI", None)
