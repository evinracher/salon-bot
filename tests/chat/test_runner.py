from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.runner import inject_manual_ai_message, run_turn
from app.chat.models.conversation import Conversation


class DummyGraph:
    def __init__(self) -> None:
        self.last_invoke_config: dict | None = None
        self.last_update_config: dict | None = None

    async def ainvoke(self, values: dict, config: dict) -> dict:
        _ = values
        self.last_invoke_config = config
        return {"messages": [AIMessage(content="runner-ok")]}

    async def aupdate_state(self, config: dict, values: dict) -> None:
        _ = values
        self.last_update_config = config


@pytest.mark.asyncio
async def test_run_turn_uses_conversation_id_as_thread_id() -> None:
    graph = DummyGraph()
    conversation = cast(Conversation, SimpleNamespace(id=42))
    session = cast(AsyncSession, object())
    reply = await run_turn(graph, conversation, "hello", session=session)
    assert reply == "runner-ok"
    assert graph.last_invoke_config == {"configurable": {"thread_id": "42"}}


@pytest.mark.asyncio
async def test_manual_injection_updates_state_thread_id() -> None:
    graph = DummyGraph()
    await inject_manual_ai_message(
        graph,
        request=cast(Request, object()),
        conversation_id=7,
        content="manual",
    )
    assert graph.last_update_config == {"configurable": {"thread_id": "7"}}
