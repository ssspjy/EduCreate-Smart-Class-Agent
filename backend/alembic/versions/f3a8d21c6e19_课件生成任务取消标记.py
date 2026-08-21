"""课件生成任务取消标记

Revision ID: f3a8d21c6e19
Revises: e6251c0c4fb2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a8d21c6e19"
down_revision: Union[str, None] = "e6251c0c4fb2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "generation_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("generation_jobs")}
    if "cancel_requested" not in columns:
        op.add_column(
            "generation_jobs",
            sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "generation_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("generation_jobs")}
    if "cancel_requested" in columns:
        op.drop_column("generation_jobs", "cancel_requested")
