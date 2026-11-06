"""Database connection engine and session dependency management.

Configures connection pooling, session lifecycle, and database health verification.
"""

from collections.abc import Generator
from typing import Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Configure engine arguments based on driver dialect
engine_kwargs: dict[str, Any] = {
    "pool_pre_ping": settings.DB_POOL_PRE_PING,
}

if settings.database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
        }
    )

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session scope for request lifecycles.

    Yields:
        Session: An active SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ping_database(db: Session) -> bool:
    """Execute a lightweight query to verify active database connectivity.

    Args:
        db: Active SQLAlchemy session.

    Returns:
        bool: True if connection query succeeded, False otherwise.
    """
    try:
        result = db.execute(text("SELECT 1"))
        return result.scalar() == 1
    except Exception as exc:
        logger.error("Database ping failed: %s", exc)
        raise
