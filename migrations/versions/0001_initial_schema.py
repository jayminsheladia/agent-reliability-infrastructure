"""initial schema: event_log, run_state

Revision ID: 0001
Revises:
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "event_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("agent_id", sa.String(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("input_state", postgresql.JSONB(), nullable=False),
        sa.Column("output_state", postgresql.JSONB(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("parent_step_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_step_id"], ["event_log.id"]),
    )
    op.create_index("ix_event_log_run_id", "event_log", ["run_id"])

    op.create_table(
        "run_state",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("current_state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("run_state")
    op.drop_index("ix_event_log_run_id", table_name="event_log")
    op.drop_table("event_log")
