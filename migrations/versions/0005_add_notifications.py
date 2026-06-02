"""add notification channels, preferences, and geofences tables

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "notification_channels" not in inspector.get_table_names():
        op.create_table(
            "notification_channels",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("channel_type", sa.String(32), nullable=False),  # e.g. "telegram"
            sa.Column(
                "config_json", sa.Text(), nullable=False
            ),  # JSON blob with channel-specific config
            sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if "notification_preferences" not in inspector.get_table_names():
        op.create_table(
            "notification_preferences",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("channel_id", sa.Integer(), nullable=False, index=True),
            sa.Column(
                "event_type", sa.String(50), nullable=False
            ),  # e.g. "charge_start"
            sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
            sa.Column(
                "config_json", sa.Text(), nullable=True
            ),  # JSON for thresholds, timeouts, etc.
        )

    if "geofences" not in inspector.get_table_names():
        op.create_table(
            "geofences",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("vin", sa.String(20), nullable=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("radius_m", sa.Float(), nullable=False),
            sa.Column("notify_on_enter", sa.Boolean(), nullable=False, default=True),
            sa.Column("notify_on_exit", sa.Boolean(), nullable=False, default=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, default=True),
        )


def downgrade() -> None:
    op.drop_table("geofences")
    op.drop_table("notification_preferences")
    op.drop_table("notification_channels")
