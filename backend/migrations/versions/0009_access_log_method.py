"""access_logs.method: QR, typed matricule or console unblock

Revision ID: 0009
Revises: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("access_logs", sa.Column("method", sa.String(10), nullable=False, server_default="QR"))
    # Older lines: an unblock wrote the DEBLOQUE flag on its own line; a typed matricule had
    # "saisie manuelle" in its reason. Non-native enums store the member NAME.
    flags = "CAST(flags AS TEXT)"
    op.execute(f"UPDATE access_logs SET method = 'CONSOLE' WHERE {flags} LIKE '%DEBLOQUE%' AND operator_id IS NOT NULL "
               "AND device_id IS NULL")
    op.execute("UPDATE access_logs SET method = 'MANUAL' WHERE method = 'QR' AND reason LIKE '%saisie manuelle%'")
    op.create_index("ix_access_logs_employee_zone", "access_logs", ["employee_id", "zone_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_access_logs_employee_zone", table_name="access_logs")
    op.drop_column("access_logs", "method")
