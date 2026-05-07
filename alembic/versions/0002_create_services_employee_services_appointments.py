"""create services

Revision ID: 0002_services_appointments
Revises: 0001_create_employees
Create Date: 2026-05-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_services_appointments"
down_revision: str | Sequence[str] | None = "0001_create_employees"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_services")),
    )


def downgrade() -> None:
    op.drop_table("services")
