"""badges: revocation reason, note and author; one active badge per employee

Revision ID: 0007
Revises: 0006
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

ACTIVE = "status = 'ACTIVE'"


def upgrade() -> None:
    with op.batch_alter_table("badges") as batch:
        batch.add_column(sa.Column("revoked_reason", sa.String(20), nullable=True))
        batch.add_column(sa.Column("revoked_note", sa.String(300), nullable=True))
        batch.add_column(sa.Column("revoked_by", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_badges_revoked_by_users", "users", ["revoked_by"], ["id"])
    # Older revocations had no reason recorded.
    op.execute("UPDATE badges SET revoked_reason = 'OTHER', revoked_note = 'Motif non enregistré (avant la version 0007)' "
               "WHERE status = 'REVOKED' AND revoked_reason IS NULL")
    # Repair any duplicate before the unique index: keep only the highest version active.
    op.execute("""
        UPDATE badges SET status = 'REVOKED', revoked_at = CURRENT_TIMESTAMP, revoked_reason = 'REPLACED',
               revoked_note = 'Doublon actif corrigé par la migration 0007'
        WHERE status = 'ACTIVE' AND EXISTS (
            SELECT 1 FROM badges newer
            WHERE newer.employee_id = badges.employee_id AND newer.status = 'ACTIVE'
              AND newer.version > badges.version)
    """)
    op.create_index("one_active_badge", "badges", ["employee_id"], unique=True,
                    postgresql_where=sa.text(ACTIVE), sqlite_where=sa.text(ACTIVE))


def downgrade() -> None:
    op.drop_index("one_active_badge", table_name="badges")
    with op.batch_alter_table("badges") as batch:
        batch.drop_constraint("fk_badges_revoked_by_users", type_="foreignkey")
        batch.drop_column("revoked_by")
        batch.drop_column("revoked_note")
        batch.drop_column("revoked_reason")
