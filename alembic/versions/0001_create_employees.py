"""create employees table

Revision ID: 0001_create_employees
Revises:
Create Date: 2026-05-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_employees"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employees_phone"),
        "employees",
        ["phone"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_employees_phone"), table_name="employees")
    op.drop_table("employees")
