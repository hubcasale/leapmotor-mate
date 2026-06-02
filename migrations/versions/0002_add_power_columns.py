"""add charging and discharging power columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.add_column(sa.Column("charging_power_kw", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("discharge_power_kw", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("vehicle_snapshots") as batch_op:
        batch_op.drop_column("discharge_power_kw")
        batch_op.drop_column("charging_power_kw")
