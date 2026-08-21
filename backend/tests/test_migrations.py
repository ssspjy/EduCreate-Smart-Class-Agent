"""Alembic migration coverage for databases created before task fields existed."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import BACKEND_ROOT


def test_legacy_material_table_upgrades_to_task_status_fields(tmp_path) -> None:
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE materials (id VARCHAR(36) PRIMARY KEY, status VARCHAR(32) NOT NULL)"
        ))

    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.attributes["database_url"] = database_url
    command.stamp(config, "7849a7154002")
    command.upgrade(config, "head")

    columns = {column["name"] for column in inspect(engine).get_columns("materials")}
    assert {"parse_progress", "task_id", "cancel_requested"} <= columns
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "f3a8d21c6e19"
