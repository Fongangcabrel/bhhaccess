"""devices.checkpoint_id / checkpoint_since: the post the phone currently holds (FR-33)

Each change of post chosen on the phone is written in the audit (device.post, before -> after).

Revision ID: 0016
Revises: 0015
"""
import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.add_column(sa.Column("checkpoint_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("checkpoint_since", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_devices_checkpoint_id", "checkpoints", ["checkpoint_id"], ["id"],
                                 ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("devices") as batch:
        batch.drop_constraint("fk_devices_checkpoint_id", type_="foreignkey")
        batch.drop_column("checkpoint_since")
        batch.drop_column("checkpoint_id")
