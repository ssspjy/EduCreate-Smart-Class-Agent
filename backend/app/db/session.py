"""Database session setup.

The skeleton defaults to SQLite for local development while keeping a
SQLAlchemy URL boundary that can later point at PostgreSQL.
"""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
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
    _ensure_embedding_column()


def _ensure_embedding_column() -> None:
    """Bootstrap the embedding column for pre-vector databases.

    Alembic will own schema evolution in the next phase. This idempotent
    bootstrap keeps an existing competition volume usable during rollout.
    """
    inspector = inspect(engine)
    if "chunks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("chunks")}
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            if "embedding" not in columns:
                connection.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding vector(1024)"))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                "ON chunks USING hnsw (embedding vector_cosine_ops)"
            ))
        elif "embedding" not in columns:
            connection.execute(text("ALTER TABLE chunks ADD COLUMN embedding VECTOR(1024)"))
