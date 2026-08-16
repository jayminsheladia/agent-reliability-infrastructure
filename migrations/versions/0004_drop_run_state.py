"""drop unused run_state table

Day 1 scaffolded a separate "current state per run" table, but Day 5's
per-step output_state + pgvector retrieval design made it redundant —
it was never read or written by any application code.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("run_state")


def downgrade() -> None:
    op.create_table(
        "run_state",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("current_state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
