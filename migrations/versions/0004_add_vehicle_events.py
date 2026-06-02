"""add vehicle_events table for transition tracking

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "vehicle_events" not in inspector.get_table_names():
        op.create_table(
            "vehicle_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("vin", sa.String(20), nullable=False, index=True),
            sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
            sa.Column("event_type", sa.String(50), nullable=False, index=True),
            sa.Column("field_name", sa.String(50), nullable=False),
            sa.Column("old_value", sa.String(50), nullable=True),
            sa.Column("new_value", sa.String(50), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("vehicle_events")
