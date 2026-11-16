"""alerts (suspicious badge use) and travel_times (minimum walking time between two posts)

Revision ID: 0014
Revises: 0013
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", app.core.database.UtcDateTime(), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("badge_id", sa.Integer(), sa.ForeignKey("badges.id"), nullable=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=True),
        sa.Column("access_log_id", sa.Integer(), sa.ForeignKey("access_logs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("checkpoints.id"), nullable=True),
        sa.Column("message", sa.String(300), nullable=False),
        sa.Column("detail", app.core.database.JsonType, nullable=False),
        sa.Column("handled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("handled_at", app.core.database.UtcDateTime(), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
    )
    for column in ("created_at", "type", "status", "badge_id"):
        op.create_index(f"ix_alerts_{column}", "alerts", [column])
    op.create_table(
        "travel_times",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("checkpoint_a_id", sa.Integer(), sa.ForeignKey("checkpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkpoint_b_id", sa.Integer(), sa.ForeignKey("checkpoints.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_seconds", sa.Integer(), nullable=False),
        sa.UniqueConstraint("checkpoint_a_id", "checkpoint_b_id"),
    )
    # Reuse detection reads the last scan of a badge (Backend Schema: access_logs(badge_id, scanned_at DESC)).
    op.create_index("ix_access_logs_badge_time", "access_logs", ["badge_id", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_access_logs_badge_time", table_name="access_logs")
    op.drop_table("travel_times")
    for column in ("created_at", "type", "status", "badge_id"):
        op.drop_index(f"ix_alerts_{column}", table_name="alerts")
    op.drop_table("alerts")
