"""add event_type column to event_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "event_log",
        sa.Column("event_type", sa.String(), nullable=False, server_default="step"),
    )


def downgrade() -> None:
    op.drop_column("event_log", "event_type")
