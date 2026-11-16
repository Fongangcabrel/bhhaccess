"""units, paired devices, agents and post assignments

Revision ID: 0002
Revises: 0001
"""
import sqlalchemy as sa
from alembic import op

import app.core.database  # noqa: F401  (custom column types)

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

DEFAULT_UNIT = "Général"


def upgrade() -> None:
    # --- units ---------------------------------------------------------------
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
    )
    op.execute(sa.text("INSERT INTO units (name) VALUES (:n)").bindparams(n=DEFAULT_UNIT))
    op.add_column("zones", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.execute(sa.text("UPDATE zones SET unit_id = (SELECT id FROM units WHERE name = :n)").bindparams(n=DEFAULT_UNIT))
    op.alter_column("zones", "unit_id", nullable=False)
    op.create_foreign_key("zones_unit_id_fkey", "zones", "units", ["unit_id"], ["id"])
    op.create_index("ix_zones_unit_id", "zones", ["unit_id"])

    # --- devices -------------------------------------------------------------
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code_hash", sa.String(64), unique=True),
        sa.Column("code_expires_at", app.core.database.UtcDateTime()),
        sa.Column("token_hash", sa.String(64), unique=True),
        sa.Column("created_at", app.core.database.UtcDateTime(), nullable=False),
        sa.Column("paired_at", app.core.database.UtcDateTime()),
        sa.Column("last_seen_at", app.core.database.UtcDateTime()),
        sa.Column("revoked_at", app.core.database.UtcDateTime()),
    )

    # --- agents --------------------------------------------------------------
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("matricule", sa.String(40), unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "agent_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("checkpoint_id", sa.Integer(), sa.ForeignKey("checkpoints.id"), nullable=False),
        sa.Column("started_at", app.core.database.UtcDateTime(), nullable=False),
        sa.Column("ended_at", app.core.database.UtcDateTime()),
    )
    op.create_index("ix_agent_assignments_agent_id", "agent_assignments", ["agent_id"])
    op.create_index("ix_agent_assignments_checkpoint_id", "agent_assignments", ["checkpoint_id"])
    op.create_index("ix_agent_assignments_started_at", "agent_assignments", ["started_at"])

    # --- journal: who scanned (device/operator) and which agent was posted ----
    op.drop_constraint("access_logs_agent_id_fkey", "access_logs", type_="foreignkey")
    op.alter_column("access_logs", "agent_id", new_column_name="operator_id")
    op.create_foreign_key("access_logs_operator_id_fkey", "access_logs", "users", ["operator_id"], ["id"])
    op.add_column("access_logs", sa.Column("device_id", sa.Integer(), nullable=True))
    op.add_column("access_logs", sa.Column("agent_id", sa.Integer(), nullable=True))
    op.add_column("access_logs", sa.Column("agent_name", sa.String(160), nullable=True))
    op.create_foreign_key("access_logs_device_id_fkey", "access_logs", "devices", ["device_id"], ["id"])
    op.create_foreign_key("access_logs_agent_id_fkey", "access_logs", "agents", ["agent_id"], ["id"])
    op.create_index("ix_access_logs_agent_id", "access_logs", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_access_logs_agent_id", table_name="access_logs")
    op.drop_constraint("access_logs_agent_id_fkey", "access_logs", type_="foreignkey")
    op.drop_constraint("access_logs_device_id_fkey", "access_logs", type_="foreignkey")
    op.drop_column("access_logs", "agent_name")
    op.drop_column("access_logs", "agent_id")
    op.drop_column("access_logs", "device_id")
    op.drop_constraint("access_logs_operator_id_fkey", "access_logs", type_="foreignkey")
    op.alter_column("access_logs", "operator_id", new_column_name="agent_id")
    op.create_foreign_key("access_logs_agent_id_fkey", "access_logs", "users", ["agent_id"], ["id"])
    op.drop_table("agent_assignments")
    op.drop_table("agents")
    op.drop_table("devices")
    op.drop_index("ix_zones_unit_id", table_name="zones")
    op.drop_constraint("zones_unit_id_fkey", "zones", type_="foreignkey")
    op.drop_column("zones", "unit_id")
    op.drop_table("units")
