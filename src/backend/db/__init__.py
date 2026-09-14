"""
src/backend/db package.

Re-exports the public database interface so other modules can import from
`src.backend.db` without knowing the internal file layout:

    from src.backend.db import Base, engine, SessionLocal, get_db, init_db
"""

from src.backend.db.database import (  # noqa: F401
    Base,
    DATABASE_URL,
    SessionLocal,
    engine,
    get_db,
    init_db,
)

__all__ = [
    "Base",
    "DATABASE_URL",
    "SessionLocal",
    "engine",
    "get_db",
    "init_db",
]
