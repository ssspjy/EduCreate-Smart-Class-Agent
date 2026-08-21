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
    _ensure_material_task_columns()
    _ensure_generation_job_columns()


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


def _ensure_material_task_columns() -> None:
    """Keep an existing local create_all database usable before Alembic adoption."""
    inspector = inspect(engine)
    if "materials" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("materials")}
    with engine.begin() as connection:
        if "parse_progress" not in columns:
            connection.execute(text(
                "ALTER TABLE materials ADD COLUMN parse_progress INTEGER NOT NULL DEFAULT 0"
            ))
        if "task_id" not in columns:
            connection.execute(text("ALTER TABLE materials ADD COLUMN task_id VARCHAR(255)"))
        if "cancel_requested" not in columns:
            connection.execute(text(
                "ALTER TABLE materials ADD COLUMN cancel_requested BOOLEAN NOT NULL DEFAULT 0"
            ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_materials_task_id ON materials (task_id)"
        ))


def _ensure_generation_job_columns() -> None:
    """Keep existing local SQLite generation_jobs tables compatible."""
    inspector = inspect(engine)
    if "generation_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("generation_jobs")}
    additions = {
        "job_type": "VARCHAR(32) NOT NULL DEFAULT 'pptx'",
        "progress": "INTEGER NOT NULL DEFAULT 0",
        "task_id": "VARCHAR(255)",
        "request_json": "JSON NOT NULL DEFAULT '{}'",
        "error_message": "TEXT",
    }
    with engine.begin() as connection:
        for column_name, definition in additions.items():
            if column_name not in columns:
                connection.execute(text(
                    f"ALTER TABLE generation_jobs ADD COLUMN {column_name} {definition}"
                ))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_generation_jobs_task_id ON generation_jobs (task_id)"
        ))
