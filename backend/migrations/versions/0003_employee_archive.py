"""employee archiving: date, author and reason

Revision ID: 0003
Revises: 0002
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("employees", sa.Column("archived_at", app.core.database.UtcDateTime(), nullable=True))
    op.add_column("employees", sa.Column("archived_by", sa.Integer(), nullable=True))
    op.add_column("employees", sa.Column("archive_reason", sa.String(500), nullable=True))
    op.create_foreign_key("employees_archived_by_fkey", "employees", "users", ["archived_by"], ["id"])


def downgrade() -> None:
    op.drop_constraint("employees_archived_by_fkey", "employees", type_="foreignkey")
    op.drop_column("employees", "archive_reason")
    op.drop_column("employees", "archived_by")
    op.drop_column("employees", "archived_at")
