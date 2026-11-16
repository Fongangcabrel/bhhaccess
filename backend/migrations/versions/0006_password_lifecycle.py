"""users: forced password change and password change date

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("password_changed_at", app.core.database.UtcDateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "must_change_password")
