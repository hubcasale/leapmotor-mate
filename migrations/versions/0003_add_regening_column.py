"""add is_regening column to vehicle_snapshots

Revision ID: 0003
Revises: 0002
Create Date: 2025-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.add_column(sa.Column("is_regening", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.drop_column("is_regening")
