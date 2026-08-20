"""Database session setup.

The skeleton defaults to SQLite for local development while keeping a
SQLAlchemy URL boundary that can later point at PostgreSQL.
"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import get_settings, resolve_runtime_path

settings = get_settings()


def _resolve_database_url(database_url: str) -> str:
    """Keep SQLite files anchored under backend/ when a relative path is used."""
    if not database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        return database_url

    raw_path = database_url.replace("sqlite:///", "", 1)
    sqlite_path = Path(raw_path)
    if sqlite_path.is_absolute():
        return database_url

    resolved = resolve_runtime_path(sqlite_path)
    return f"sqlite:///{resolved.as_posix()}"


database_url = _resolve_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Yield a scoped database session for FastAPI dependencies."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create local skeleton tables when auto-create is enabled."""
    if not settings.database_auto_create:
        return

    resolve_runtime_path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    if database_url.startswith("sqlite:///"):
        db_path = database_url.replace("sqlite:///", "", 1)
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
