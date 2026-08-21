"""Apply Alembic migrations, adopting pre-Alembic competition databases safely."""

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.config import BACKEND_ROOT
from app.db.session import engine

BASELINE_REVISION = "7849a7154002"


def upgrade_database() -> None:
    """Stamp the legacy create_all schema once, then upgrade to the current head."""
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    # SQLAlchemy masks passwords as *** in str(URL); Alembic needs the real
    # in-process URL and never logs this attribute.
    config.attributes["database_url"] = engine.url.render_as_string(hide_password=False)
    table_names = set(inspect(engine).get_table_names())
    if "materials" in table_names and "alembic_version" not in table_names:
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")


if __name__ == "__main__":
    upgrade_database()
