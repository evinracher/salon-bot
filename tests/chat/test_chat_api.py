import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_manager_message_creates_conversation_and_message(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/chat/messages",
        json={
            "phone": "3001112233",
            "role": "manager",
            "content": "Handle this customer manually.",
            "customer_name": "Laura",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["conversation"]["phone"] == "3001112233"
    assert payload["conversation"]["customer_name"] == "Laura"
    assert payload["conversation"]["bot_enabled"] is True
    assert payload["conversation"]["bot_paused_until"] is not None
    assert payload["accepted_message"]["role"] == "manager"
    assert payload["bot_reply"] is None

    list_resp = await client.get("/chat/conversations/3001112233/messages")
    assert list_resp.status_code == 200
    messages = list_resp.json()
    assert len(messages) == 1
    assert messages[0]["content"] == "Handle this customer manually."


@pytest.mark.asyncio
async def test_chat_manager_message_does_not_reenable_disabled_bot(
    client: AsyncClient,
) -> None:
    toggle_resp = await client.post(
        "/chat/conversations/3005006000/bot",
        json={"enabled": False},
    )
    assert toggle_resp.status_code == 200

    resp = await client.post(
        "/chat/messages",
        json={
            "phone": "3005006000",
            "role": "manager",
            "content": "I will handle this chat.",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["conversation"]["bot_enabled"] is False
    assert payload["conversation"]["bot_paused_until"] is None
    assert payload["bot_reply"] is None


@pytest.mark.asyncio
async def test_chat_customer_message_when_bot_disabled_has_no_reply(
    client: AsyncClient,
) -> None:
    toggle_resp = await client.post(
        "/chat/conversations/3002223344/bot",
        json={"enabled": False},
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["bot_enabled"] is False

    msg_resp = await client.post(
        "/chat/messages",
        json={
            "phone": "3002223344",
            "role": "customer",
            "content": "I need a haircut tomorrow at 10",
        },
    )
    assert msg_resp.status_code == 200
    payload = msg_resp.json()
    assert payload["bot_reply"] is None
    assert payload["accepted_message"]["role"] == "customer"


@pytest.mark.asyncio
async def test_chat_customer_message_runs_agent_when_bot_active(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_turn(**kwargs) -> str:
        assert kwargs["phone"] == "3007778888"
        return "Sure, I can help you book that."

    monkeypatch.setattr("app.chat.api.get_compiled_graph", lambda _request: object())
    monkeypatch.setattr("app.chat.api.run_turn", fake_run_turn)

    resp = await client.post(
        "/chat/messages",
        json={
            "phone": "3007778888",
            "role": "customer",
            "content": "Can I book tomorrow at 2pm?",
            "customer_name": "Maria",
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["accepted_message"]["role"] == "customer"
    assert payload["bot_reply"] == "Sure, I can help you book that."


@pytest.mark.asyncio
async def test_chat_customer_message_returns_sanitized_error_on_agent_failure(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_run_turn(**kwargs) -> str:
        _ = kwargs
        raise RuntimeError("upstream timeout with sensitive details")

    monkeypatch.setattr("app.chat.api.get_compiled_graph", lambda _request: object())
    monkeypatch.setattr("app.chat.api.run_turn", fake_run_turn)

    resp = await client.post(
        "/chat/messages",
        json={
            "phone": "3007778899",
            "role": "customer",
            "content": "book me please",
        },
    )
    assert resp.status_code == 500
    assert resp.json()["detail"] == "chat agent failed to process message"
