"""Common API dependencies for dependency injection in endpoints."""

from collections.abc import Generator
from sqlalchemy.orm import Session
from app.database.connection import get_db

# Re-export get_db as standard session dependency
def get_db_session() -> Generator[Session, None, None]:
    """Yield database session for API routes."""
    yield from get_db()
