import pytest

from app.chat.service import (
    get_or_create_conversation_by_phone,
    set_bot_enabled,
)
from app.db import async_session_maker


@pytest.mark.asyncio
async def test_get_or_create_conversation_by_phone_idempotent() -> None:
    async with async_session_maker() as session:
        first = await get_or_create_conversation_by_phone(
            session,
            phone="+1-999-0001",
            customer_name="Nora",
        )
        second = await get_or_create_conversation_by_phone(
            session,
            phone="+1-999-0001",
            customer_name="Nora Updated",
        )
        assert first.id == second.id


@pytest.mark.asyncio
async def test_set_bot_enabled_updates_flag() -> None:
    async with async_session_maker() as session:
        conversation = await get_or_create_conversation_by_phone(
            session,
            phone="+1-999-0002",
            customer_name="Luis",
        )
        updated = await set_bot_enabled(session, conversation.id, False)
        assert updated is not None
        assert updated.bot_enabled is False
