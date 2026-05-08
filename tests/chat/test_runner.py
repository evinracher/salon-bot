from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from app.chat.agent.runner import _is_booking_confirmation, run_turn


class FakeGraph:
    async def ainvoke(self, payload: dict, config: dict) -> dict:
        assert config["configurable"]["thread_id"] == "3001234567"
        assert payload["messages"]
        return {"messages": [AIMessage(content="Booked for tomorrow at 10:00.")]}


@pytest.mark.asyncio
async def test_run_turn_returns_final_bot_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_or_create(session, phone: str, customer_name: str | None = None):
        return SimpleNamespace(phone=phone, customer_name=customer_name)

    async def fake_recent(session, *, phone: str, limit: int | None = None):
        return []

    async def fake_append(session, **kwargs):
        return (
            SimpleNamespace(phone=kwargs["phone"], customer_name=None),
            SimpleNamespace(content=kwargs["content"]),
        )

    monkeypatch.setattr(
        "app.chat.agent.runner.get_or_create_conversation", fake_get_or_create
    )
    monkeypatch.setattr("app.chat.agent.runner.recent_messages", fake_recent)
    monkeypatch.setattr("app.chat.agent.runner.append_message", fake_append)

    msg = await run_turn(
        graph=FakeGraph(),
        session=object(),  # type: ignore[arg-type]
        phone="3001234567",
        customer_name="Ana",
        user_text="please book tomorrow",
    )
    assert msg == "Booked for tomorrow at 10:00."


def test_is_booking_confirmation_variants() -> None:
    assert _is_booking_confirmation("yes")
    assert _is_booking_confirmation("Sí")
    assert _is_booking_confirmation("confirm")
    assert not _is_booking_confirmation("maybe")
    assert not _is_booking_confirmation("what times are available?")


class FakeToolGraph:
    async def ainvoke(self, payload: dict, config: dict) -> dict:
        _ = payload, config
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"id": "call_1", "name": "list_services", "args": {}},
                    ],
                ),
                ToolMessage(
                    content='[{"id":1,"name":"Haircut"}]', tool_call_id="call_1"
                ),
                AIMessage(content="Here are available services."),
            ]
        }


@pytest.mark.asyncio
async def test_run_turn_persists_tool_audit_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []

    async def fake_get_or_create(session, phone: str, customer_name: str | None = None):
        return SimpleNamespace(phone=phone, customer_name=customer_name)

    async def fake_recent(session, *, phone: str, limit: int | None = None):
        return []

    async def fake_append(session, **kwargs):
        captured.append(kwargs)
        return (
            SimpleNamespace(phone=kwargs["phone"], customer_name=None),
            SimpleNamespace(content=kwargs["content"]),
        )

    monkeypatch.setattr(
        "app.chat.agent.runner.get_or_create_conversation", fake_get_or_create
    )
    monkeypatch.setattr("app.chat.agent.runner.recent_messages", fake_recent)
    monkeypatch.setattr("app.chat.agent.runner.append_message", fake_append)

    msg = await run_turn(
        graph=FakeToolGraph(),
        session=object(),  # type: ignore[arg-type]
        phone="3001234567",
        customer_name="Ana",
        user_text="what services do you have?",
    )
    assert msg == "Here are available services."
    assert any(
        item["role"].value == "tool" and item.get("tool_calls") for item in captured
    )
    assert any(
        item["role"].value == "tool" and item.get("tool_call_id") == "call_1"
        for item in captured
    )
