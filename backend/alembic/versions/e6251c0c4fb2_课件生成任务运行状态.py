"""课件生成任务运行状态

Revision ID: e6251c0c4fb2
Revises: c41b8b24f2d7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e6251c0c4fb2"
down_revision: Union[str, None] = "c41b8b24f2d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "generation_jobs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("generation_jobs")}
    indexes = {index["name"] for index in inspector.get_indexes("generation_jobs")}

    if "job_type" not in columns:
        op.add_column("generation_jobs", sa.Column("job_type", sa.String(32), server_default="pptx", nullable=False))
    if "progress" not in columns:
        op.add_column("generation_jobs", sa.Column("progress", sa.Integer(), server_default="0", nullable=False))
    if "task_id" not in columns:
        op.add_column("generation_jobs", sa.Column("task_id", sa.String(255), nullable=True))
    if "request_json" not in columns:
        op.add_column("generation_jobs", sa.Column("request_json", sa.JSON(), server_default="{}", nullable=False))
    if "error_message" not in columns:
        op.add_column("generation_jobs", sa.Column("error_message", sa.Text(), nullable=True))
    if "ix_generation_jobs_task_id" not in indexes:
        op.create_index("ix_generation_jobs_task_id", "generation_jobs", ["task_id"], unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "generation_jobs" not in inspector.get_table_names():
        return
    op.drop_index("ix_generation_jobs_task_id", table_name="generation_jobs")
    op.drop_column("generation_jobs", "error_message")
    op.drop_column("generation_jobs", "request_json")
    op.drop_column("generation_jobs", "task_id")
    op.drop_column("generation_jobs", "progress")
    op.drop_column("generation_jobs", "job_type")
