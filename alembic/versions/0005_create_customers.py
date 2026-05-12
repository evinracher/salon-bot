"""create customers and normalize appointments

Revision ID: 0005_create_customers
Revises: 0004_appointments
Create Date: 2026-05-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_create_customers"
down_revision: str | Sequence[str] | None = "0004_appointments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("phone", name=op.f("uq_customers_phone")),
    )

    op.execute(
        """
        INSERT INTO customers (name, phone, notes, created_at, updated_at)
        SELECT
            COALESCE(NULLIF(TRIM(source.client_name), ''), 'Unknown') AS name,
            source.client_phone,
            NULL,
            NOW(),
            NOW()
        FROM (
            SELECT
                client_phone,
                client_name,
                ROW_NUMBER() OVER (
                    PARTITION BY client_phone
                    ORDER BY created_at DESC, id DESC
                ) AS rn
            FROM appointments
        ) AS source
        WHERE source.rn = 1
        """
    )

    op.add_column("appointments", sa.Column("customer_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE appointments AS a
        SET customer_id = c.id
        FROM customers AS c
        WHERE c.phone = a.client_phone
        """
    )
    op.alter_column("appointments", "customer_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_appointments_customer_id_customers"),
        "appointments",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("appointments", "client_phone")
    op.drop_column("appointments", "client_name")


def downgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("client_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "appointments",
        sa.Column("client_phone", sa.String(length=32), nullable=True),
    )
    op.execute(
        """
        UPDATE appointments AS a
        SET
            client_name = c.name,
            client_phone = c.phone
        FROM customers AS c
        WHERE c.id = a.customer_id
        """
    )
    op.alter_column("appointments", "client_name", nullable=False)
    op.alter_column("appointments", "client_phone", nullable=False)
    op.drop_constraint(
        op.f("fk_appointments_customer_id_customers"),
        "appointments",
        type_="foreignkey",
    )
    op.drop_column("appointments", "customer_id")
    op.drop_table("customers")
