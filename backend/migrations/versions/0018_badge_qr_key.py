"""badges.qr_key_id: key of the last QR produced for the badge (tâche 43)

New QR codes carry a key id so the signing key can be replaced; this column tells how many
active badges still have to be reprinted before a former key is removed.

Revision ID: 0018
Revises: 0017
"""
import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("badges") as batch:
        batch.add_column(sa.Column("qr_key_id", sa.String(length=8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("badges") as batch:
        batch.drop_column("qr_key_id")
