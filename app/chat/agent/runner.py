from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.prompts import build_system_prompt
from app.chat.agent.runtime import (
    current_booking_confirmed,
    current_phone,
    current_session,
)
from app.chat.models.message import MessageRole
from app.chat.service import append_message, get_or_create_conversation, recent_messages
from app.config import settings


def _is_booking_confirmation(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in {
        "yes",
        "y",
        "confirm",
        "confirmed",
        "go ahead",
        "ok proceed",
        "si",
        "sí",
    }


async def run_turn(
    *,
    graph: Any,
    session: AsyncSession,
    phone: str,
    customer_name: str | None,
    user_text: str,
) -> str:
    conversation = await get_or_create_conversation(
        session, phone=phone, customer_name=customer_name
    )
    history = await recent_messages(
        session, phone=phone, limit=settings.chat_history_window
    )

    input_messages: list[BaseMessage] = [
        SystemMessage(content=build_system_prompt(phone, conversation.customer_name))
    ]
    for msg in history:
        if msg.role in (MessageRole.CUSTOMER.value, MessageRole.MANAGER.value):
            input_messages.append(HumanMessage(content=msg.content))
        elif msg.role in (MessageRole.BOT.value, MessageRole.SYSTEM.value):
            input_messages.append(AIMessage(content=msg.content))

    token_session = current_session.set(session)
    token_phone = current_phone.set(phone)
    token_confirm = current_booking_confirmed.set(_is_booking_confirmation(user_text))
    try:
        result = await graph.ainvoke(
            {"messages": input_messages},
            config={
                "configurable": {"thread_id": phone},
                "recursion_limit": settings.chat_max_tool_iters,
            },
        )
    finally:
        current_booking_confirmed.reset(token_confirm)
        current_session.reset(token_session)
        current_phone.reset(token_phone)

    output_messages = result.get("messages", [])
    new_messages = output_messages

    for msg in new_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            tool_calls_payload: list[dict[str, Any]] = [
                dict(tc) for tc in msg.tool_calls
            ]
            await append_message(
                session,
                phone=phone,
                role=MessageRole.TOOL,
                content=msg.text or "tool_calls",
                tool_calls=tool_calls_payload,
            )
        if isinstance(msg, ToolMessage):
            await append_message(
                session,
                phone=phone,
                role=MessageRole.TOOL,
                content=str(msg.content),
                tool_call_id=msg.tool_call_id,
            )

    final_content = ""
    for msg in reversed(new_messages or output_messages):
        content = getattr(msg, "content", "")
        if content:
            final_content = content if isinstance(content, str) else str(content)
            break
    if not final_content:
        final_content = "Could you confirm the appointment details?"

    await append_message(
        session, phone=phone, role=MessageRole.BOT, content=final_content
    )
    return final_content
