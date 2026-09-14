"""
Database engine, session factory, and declarative Base.

All SQLAlchemy models import Base from this module so that every table
is registered on the same metadata instance before create_all() is called.

Configuration is driven entirely by environment variables loaded from .env
(via python-dotenv in main.py).  No credentials are hardcoded here.

SQLite / PostgreSQL compatibility note
--------------------------------------
The only SQLite-specific code is the `check_same_thread=False` connect argument
required for FastAPI's threaded request handling.  That argument is NOT passed
for PostgreSQL.  Switching to PostgreSQL requires only changing DATABASE_URL in
the environment — no code changes are needed.

PostGIS / GeoAlchemy2 geometry columns are NOT used in Step 1.
When added in a later step, they can be introduced as additional column
definitions in the relevant model files without affecting anything here.
"""

import os
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Load .env from <repo_root>/src/.env or <repo_root>/.env (whichever exists).
# python-dotenv is a no-op when neither file is present (e.g. CI with env vars
# set directly), so this is safe in all environments.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", "src", ".env"),
    override=False,
)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "sqlite:///./supply_chain.db"
)


# ---------------------------------------------------------------------------
# SQLAlchemy Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def _build_engine(url: str):
    """
    Build a SQLAlchemy engine from a connection URL.

    SQLite requires check_same_thread=False for FastAPI's threaded usage.
    PostgreSQL does not accept that argument, so it is conditionally applied.
    """
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)


engine = _build_engine(DATABASE_URL)


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session and ensure it is closed after the request.

    Usage in a route:
        db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables that are registered on Base.metadata.

    This is a non-destructive operation: existing tables are not dropped or
    modified.  It is equivalent to running CREATE TABLE IF NOT EXISTS for
    each model.

    Must be called AFTER all model modules have been imported so that their
    table definitions are registered on Base.metadata.
    """
    # Import models here (not at module level) to avoid circular imports while
    # still ensuring every model is registered before create_all runs.
    import src.backend.models  # noqa: F401 — side-effect import registers all models

    Base.metadata.create_all(engine)
