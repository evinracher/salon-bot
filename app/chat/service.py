from datetime import datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.models.conversation import Conversation
from app.chat.models.message import Message, MessageRole
from app.config import settings


def _pause_until(minutes: int | None) -> datetime | None:
    if minutes is None:
        return None
    return datetime.now().astimezone() + timedelta(minutes=minutes)


async def get_or_create_conversation(
    session: AsyncSession, phone: str, customer_name: str | None = None
) -> Conversation:
    conversation = await session.get(Conversation, phone)
    if conversation is None:
        conversation = Conversation(phone=phone, customer_name=customer_name)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation

    if customer_name and not conversation.customer_name:
        conversation.customer_name = customer_name
        await session.commit()
        await session.refresh(conversation)
    return conversation


async def set_bot_enabled(
    session: AsyncSession,
    phone: str,
    enabled: bool,
    pause_minutes: int | None = None,
) -> Conversation:
    conversation = await get_or_create_conversation(session, phone=phone)
    conversation.bot_enabled = enabled
    conversation.bot_paused_until = _pause_until(pause_minutes)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def pause_bot(
    session: AsyncSession, phone: str, minutes: int | None = None
) -> Conversation:
    return await set_bot_enabled(
        session,
        phone=phone,
        enabled=True,
        pause_minutes=minutes
        if minutes is not None
        else settings.chat_manager_pause_minutes,
    )


async def apply_manager_pause(
    session: AsyncSession, phone: str, minutes: int | None = None
) -> Conversation:
    conversation = await get_or_create_conversation(session, phone=phone)
    if conversation.bot_enabled:
        conversation.bot_paused_until = _pause_until(
            minutes if minutes is not None else settings.chat_manager_pause_minutes
        )
        await session.commit()
        await session.refresh(conversation)
    return conversation


async def append_message(
    session: AsyncSession,
    *,
    phone: str,
    role: MessageRole,
    content: str,
    tool_calls: list[dict] | None = None,
    tool_call_id: str | None = None,
    provider_message_id: str | None = None,
) -> tuple[Conversation, Message]:
    conversation = await get_or_create_conversation(session, phone=phone)
    if role == MessageRole.TOOL and tool_call_id:
        existing = await session.scalar(
            select(Message).where(
                Message.conversation_phone == phone,
                Message.role == MessageRole.TOOL.value,
                Message.tool_call_id == tool_call_id,
            )
        )
        if existing is not None:
            return conversation, existing

    message = Message(
        conversation_phone=phone,
        role=role.value,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        provider_message_id=provider_message_id,
    )
    conversation.last_message_at = datetime.now().astimezone()
    session.add(message)
    await session.commit()
    await session.refresh(conversation)
    await session.refresh(message)
    return conversation, message


async def recent_messages(
    session: AsyncSession, *, phone: str, limit: int | None = None
) -> list[Message]:
    stmt: Select[tuple[Message]] = select(Message).where(
        Message.conversation_phone == phone
    )
    stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc()).limit(
        limit or settings.chat_history_window
    )
    result = await session.scalars(stmt)
    return list(result.all())[::-1]


def is_bot_active(conversation: Conversation) -> bool:
    if not conversation.bot_enabled:
        return False
    if conversation.bot_paused_until is None:
        return True
    return conversation.bot_paused_until <= datetime.now().astimezone()
