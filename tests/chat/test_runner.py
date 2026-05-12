from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request
from langchain_core.messages import AIMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.protocols import CompiledSalonAgent
from app.chat.agent.runner import inject_manual_ai_message, run_turn
from app.chat.models.conversation import Conversation
from app.config import settings
from app.models.employee import Employee
from app.models.service import Service


class DummyGraph:
    def __init__(self, *, state_values: dict | None = None) -> None:
        self.last_invoke_config: dict | None = None
        self.last_update_config: dict | None = None
        self.last_invoke_values: dict | None = None
        self.state_values: dict = dict(state_values or {})

    async def aget_state(self, config: dict) -> object:
        _ = config
        from types import SimpleNamespace

        return SimpleNamespace(values=dict(self.state_values))

    async def ainvoke(self, values: dict, config: dict) -> dict:
        self.last_invoke_values = values
        self.last_invoke_config = config
        return {"messages": [AIMessage(content="runner-ok")]}

    async def aupdate_state(self, config: dict, values: dict) -> None:
        self.last_update_config = config


@pytest.mark.asyncio
async def test_run_turn_uses_conversation_id_as_thread_id() -> None:
    graph = DummyGraph()
    conversation = cast(Conversation, SimpleNamespace(id=42, customer_id=99))
    session = cast(AsyncSession, object())
    reply = await run_turn(
        cast(CompiledSalonAgent, graph), conversation, "hello", session=session
    )
    assert reply == "runner-ok"
    assert graph.last_invoke_config is not None
    assert graph.last_invoke_config["configurable"] == {"thread_id": "42"}
    assert graph.last_invoke_config["recursion_limit"] == settings.chat_max_tool_iters


@pytest.mark.asyncio
async def test_manual_injection_updates_state_thread_id() -> None:
    graph = DummyGraph()
    await inject_manual_ai_message(
        cast(CompiledSalonAgent, graph),
        request=cast(Request, object()),
        conversation_id=7,
        content="manual",
    )
    assert graph.last_update_config is not None
    assert graph.last_update_config["configurable"] == {"thread_id": "7"}
    assert graph.last_update_config["recursion_limit"] == settings.chat_max_tool_iters


@pytest.mark.asyncio
async def test_run_turn_system_prompt_includes_preference_names() -> None:
    graph = DummyGraph(
        state_values={
            "preferred_service_id": 10,
            "preferred_employee_id": 20,
        }
    )
    conversation = cast(Conversation, SimpleNamespace(id=42, customer_id=99))

    class _Sess:
        async def get(self, model, ident):  # noqa: ANN001
            if model is Service and ident == 10:
                return SimpleNamespace(name="Color")
            if model is Employee and ident == 20:
                return SimpleNamespace(name="Jamie")
            return None

    session = cast(AsyncSession, _Sess())
    reply = await run_turn(
        cast(CompiledSalonAgent, graph), conversation, "hello", session=session
    )
    assert reply == "runner-ok"
    assert graph.last_invoke_values is not None
    msgs = graph.last_invoke_values["messages"]
    assert "Color" in msgs[0].content
    assert "Jamie" in msgs[0].content
