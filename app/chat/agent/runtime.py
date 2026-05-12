from contextvars import ContextVar
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

current_session: ContextVar[AsyncSession | None] = ContextVar("chat_current_session", default=None)

pending_salon_state_patch: ContextVar[dict[str, Any] | None] = ContextVar(
    "pending_salon_state_patch", default=None
)


def merge_salon_state_patch(**kwargs: Any) -> None:
    """Merge keys into the per-turn patch bag (set by ``run_turn``). Values may be None."""
    bag = pending_salon_state_patch.get()
    if bag is None:
        return
    bag.update(kwargs)
