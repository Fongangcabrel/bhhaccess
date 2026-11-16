"""audit_entries: source IP address, index for the author filter

Revision ID: 0008
Revises: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_entries", sa.Column("ip", sa.String(45), nullable=True))
    op.create_index("ix_audit_entries_actor_id", "audit_entries", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_entries_actor_id", table_name="audit_entries")
    op.drop_column("audit_entries", "ip")
