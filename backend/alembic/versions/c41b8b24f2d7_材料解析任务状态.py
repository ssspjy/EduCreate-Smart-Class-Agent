"""材料解析任务状态

Revision ID: c41b8b24f2d7
Revises: 7849a7154002
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41b8b24f2d7"
down_revision: Union[str, None] = "7849a7154002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("materials")}
    indexes = {index["name"] for index in inspector.get_indexes("materials")}

    if "parse_progress" not in columns:
        op.add_column(
            "materials",
            sa.Column("parse_progress", sa.Integer(), server_default="0", nullable=False),
        )
    if "task_id" not in columns:
        op.add_column("materials", sa.Column("task_id", sa.String(length=255), nullable=True))
    if "cancel_requested" not in columns:
        op.add_column(
            "materials",
            sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
        )
    if "ix_materials_task_id" not in indexes:
        op.create_index("ix_materials_task_id", "materials", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_materials_task_id", table_name="materials")
    op.drop_column("materials", "cancel_requested")
    op.drop_column("materials", "task_id")
    op.drop_column("materials", "parse_progress")
