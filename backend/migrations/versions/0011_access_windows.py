"""authorisations: start date, author, weekly time slots (access_schedules)

Revision ID: 0011
Revises: 0010
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("zone_authorizations") as batch:
        batch.add_column(sa.Column("valid_from", app.core.database.UtcDateTime(), nullable=True))
        batch.add_column(sa.Column("granted_by", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_zone_authorizations_granted_by_users", "users", ["granted_by"], ["id"])
    op.create_table(
        "access_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authorization_id", sa.Integer(),
                  sa.ForeignKey("zone_authorizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekdays", app.core.database.JsonType, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
    )
    op.create_index("ix_access_schedules_authorization_id", "access_schedules", ["authorization_id"])


def downgrade() -> None:
    op.drop_index("ix_access_schedules_authorization_id", table_name="access_schedules")
    op.drop_table("access_schedules")
    with op.batch_alter_table("zone_authorizations") as batch:
        batch.drop_constraint("fk_zone_authorizations_granted_by_users", type_="foreignkey")
        batch.drop_column("granted_by")
        batch.drop_column("valid_from")
