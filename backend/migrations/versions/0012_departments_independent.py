"""departments: independent from entities, unique name

Departments with the same name (case-insensitive) in several entities are merged into one,
the employees pointing to the duplicates are moved to the kept department.

Revision ID: 0012
Revises: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM departments ORDER BY id")).all()
    kept: dict[str, int] = {}
    for department_id, name in rows:
        key = " ".join(name.split()).lower()
        if key in kept:
            connection.execute(sa.text("UPDATE employees SET department_id = :keep WHERE department_id = :dup"),
                               {"keep": kept[key], "dup": department_id})
            connection.execute(sa.text("DELETE FROM departments WHERE id = :dup"), {"dup": department_id})
        else:
            kept[key] = department_id
    with op.batch_alter_table("departments") as batch:
        batch.drop_column("entity_id")  # its foreign key goes with it
        batch.create_unique_constraint("uq_departments_name", ["name"])


def downgrade() -> None:
    with op.batch_alter_table("departments") as batch:
        batch.drop_constraint("uq_departments_name", type_="unique")
        batch.add_column(sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id"), nullable=True))
