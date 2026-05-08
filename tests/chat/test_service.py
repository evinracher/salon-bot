import pytest

from app.chat.models.message import MessageRole
from app.chat.service import append_message
from app.db import get_session_maker


@pytest.mark.asyncio
async def test_append_message_dedupes_tool_call_id() -> None:
    session_maker = get_session_maker()
    async with session_maker() as session:
        _, first = await append_message(
            session,
            phone="3009001000",
            role=MessageRole.TOOL,
            content="tool payload",
            tool_call_id="call_dedupe_1",
        )
        _, second = await append_message(
            session,
            phone="3009001000",
            role=MessageRole.TOOL,
            content="tool payload duplicated",
            tool_call_id="call_dedupe_1",
        )
        assert first.id == second.id
