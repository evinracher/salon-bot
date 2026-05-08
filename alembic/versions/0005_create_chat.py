"""compatibility bridge for split chat migrations

Revision ID: 0005_create_chat
Revises: 0004_appointments
Create Date: 2026-05-08

"""

from collections.abc import Sequence

revision: str = "0005_create_chat"
down_revision: str | Sequence[str] | None = "0004_appointments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No-op bridge to preserve compatibility with databases that were
    # previously stamped/applied at 0005_create_chat.
    pass


def downgrade() -> None:
    pass
