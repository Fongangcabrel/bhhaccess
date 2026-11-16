"""device_scopes: the units / zones / posts a phone covers (empty = whole site)

Revision ID: 0013
Revises: 0012
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_scopes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_id", sa.Integer(), sa.ForeignKey("units.id", ondelete="CASCADE"), nullable=True),
        sa.Column("zone_id", sa.Integer(), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=True),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("checkpoints.id", ondelete="CASCADE"), nullable=True),
        sa.CheckConstraint("(CASE WHEN unit_id IS NULL THEN 0 ELSE 1 END) + (CASE WHEN zone_id IS NULL THEN 0 ELSE 1 END)"
                        " + (CASE WHEN checkpoint_id IS NULL THEN 0 ELSE 1 END) = 1",
                           name="ck_device_scopes_one_target"),
    )
    op.create_index("ix_device_scopes_device_id", "device_scopes", ["device_id"])


def downgrade() -> None:
    op.drop_index("ix_device_scopes_device_id", table_name="device_scopes")
    op.drop_table("device_scopes")
