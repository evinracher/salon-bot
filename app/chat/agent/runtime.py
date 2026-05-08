from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession

current_session: ContextVar[AsyncSession | None] = ContextVar(
    "chat_current_session", default=None
)
current_phone: ContextVar[str | None] = ContextVar("chat_current_phone", default=None)
current_booking_confirmed: ContextVar[bool] = ContextVar(
    "chat_current_booking_confirmed", default=False
)
