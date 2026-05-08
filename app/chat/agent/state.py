from typing import Any

from typing_extensions import TypedDict


class ChatAgentState(TypedDict, total=False):
    messages: list[Any]
    phone: str
    customer_name: str | None
    pending_booking: dict[str, Any] | None
    preferences: dict[str, Any]
