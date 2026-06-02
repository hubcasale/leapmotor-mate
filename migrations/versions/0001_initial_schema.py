"""initial schema baseline

Revision ID: 0001
Revises: None
Create Date: 2026-05-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create vehicle_snapshots if it doesn't exist (for fresh installs).
    # Existing databases already have this table — op.create_table is safe
    # because SQLite CREATE TABLE IF NOT EXISTS is the default behavior
    # when using batch mode.
    op.create_table(
        "vehicle_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("vin", sa.String(20), nullable=False, index=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        sa.Column("battery_soc", sa.Integer(), nullable=True),
        sa.Column("battery_current", sa.Float(), nullable=True),
        sa.Column("battery_voltage", sa.Float(), nullable=True),
        sa.Column("expected_mileage", sa.Integer(), nullable=True),
        sa.Column("total_mileage", sa.Integer(), nullable=True),
        sa.Column("energy_kwh", sa.Float(), nullable=True),
        sa.Column("outdoor_temp", sa.Integer(), nullable=True),
        sa.Column("is_charging", sa.Boolean(), nullable=True),
        sa.Column("is_plugged", sa.Boolean(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("charge_state", sa.Integer(), nullable=True),
        sa.Column("speed", sa.Integer(), nullable=True),
        sa.Column("is_parked", sa.Boolean(), nullable=True),
        sa.Column("is_locked", sa.Boolean(), nullable=True),
        sa.Column("tire_fl_pressure", sa.Float(), nullable=True),
        sa.Column("tire_fr_pressure", sa.Float(), nullable=True),
        sa.Column("tire_rl_pressure", sa.Float(), nullable=True),
        sa.Column("tire_rr_pressure", sa.Float(), nullable=True),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("vehicle_snapshots")
