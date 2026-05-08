"""create chat tables

Revision ID: 0005_create_chat
Revises: 0004_appointments
Create Date: 2026-05-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_create_chat"
down_revision: str | Sequence[str] | None = "0004_appointments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("customer_name", sa.String(length=120), nullable=True),
        sa.Column(
            "bot_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("bot_paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("phone", name=op.f("pk_conversations")),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_phone", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tool_call_id", sa.String(length=128), nullable=True),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('customer','manager','bot','system','tool')",
            name="ck_messages_role_valid",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_phone"],
            ["conversations.phone"],
            name=op.f("fk_messages_conversation_phone_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint(
            "conversation_phone",
            "provider_message_id",
            name="uq_messages_conversation_provider_message_id",
        ),
    )

    op.create_index(
        "ix_messages_conversation_phone_created_at",
        "messages",
        ["conversation_phone", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_phone_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
