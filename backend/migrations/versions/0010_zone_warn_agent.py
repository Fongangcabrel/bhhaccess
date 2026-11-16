"""zones.antipassback_warn_agent: warn the agent of a double entry in « Signalé » mode

Revision ID: 0010
Revises: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("zones", sa.Column("antipassback_warn_agent", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("zones", "antipassback_warn_agent")
