"""create appointments

Revision ID: 0004_appointments
Revises: 0003_employee_services
Create Date: 2026-05-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_appointments"
down_revision: str | Sequence[str] | None = "0003_employee_services"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(length=120), nullable=False),
        sa.Column("client_phone", sa.String(length=32), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
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
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="scheduled",
        ),
        sa.CheckConstraint(
            "end_time > start_time",
            name="ck_appointments_end_after_start",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled','confirmed','completed','cancelled','no_show')",
            name="ck_appointments_status_valid",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name=op.f("fk_appointments_employee_id_employees"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            name=op.f("fk_appointments_service_id_services"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointments")),
    )


def downgrade() -> None:
    op.drop_table("appointments")
