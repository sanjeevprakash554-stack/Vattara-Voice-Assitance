"""Alembic environment configuration for database migrations."""

import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure backend directory is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.models import Base  # Loads all models (Business, User, Customer, Appointment, CallHistory, Reminder)

# Alembic Config object
config = context.config

# Interpret config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Read the database connection URL dynamically.

    Prioritizes explicit alembic config, then SQLALCHEMY_DATABASE_URI environment variable,
    and finally application settings.
    """
    configured_url = config.get_main_option("sqlalchemy.url")
    if configured_url and "driver://user:pass" not in configured_url:
        return configured_url
    if os.getenv("SQLALCHEMY_DATABASE_URI"):
        return os.environ["SQLALCHEMY_DATABASE_URI"]
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode without an active DBAPI connection."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live database connection."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
