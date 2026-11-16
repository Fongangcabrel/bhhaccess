"""zones: code, description, sensitivity, activation; checkpoints: activation

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("zones", sa.Column("code", sa.String(20), nullable=True))
    op.create_unique_constraint("zones_code_key", "zones", ["code"])
    op.add_column("zones", sa.Column("description", sa.String(500), nullable=True))
    # Non-native enums store the member *name* (as in 0001), hence STANDARD / RESTRICTED / CRITICAL.
    op.add_column("zones", sa.Column("sensitivity", sa.String(10), nullable=False, server_default="STANDARD"))
    op.add_column("zones", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("checkpoints", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("checkpoints", "is_active")
    op.drop_column("zones", "is_active")
    op.drop_column("zones", "sensitivity")
    op.drop_column("zones", "description")
    op.drop_constraint("zones_code_key", "zones", type_="unique")
    op.drop_column("zones", "code")
