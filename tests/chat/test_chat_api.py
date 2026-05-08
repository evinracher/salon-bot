import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_post_message_creates_conversation_and_invokes_agent(
    client: AsyncClient,
    fake_graph,
) -> None:
    resp = await client.post(
        "/chat/messages",
        json={"phone": "+1-300-0001", "customer_name": "Ana", "content": "Hi"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation"]["id"] > 0
    assert body["conversation"]["bot_enabled"] is True
    assert body["bot_reply"] == "ok"
    assert len(fake_graph.invocations) == 1


@pytest.mark.asyncio
async def test_bot_disabled_skips_agent_invoke(client: AsyncClient, fake_graph) -> None:
    created = await client.post(
        "/chat/messages",
        json={"phone": "+1-300-0002", "customer_name": "BotOff", "content": "hello"},
    )
    conversation_id = created.json()["conversation"]["id"]
    toggle = await client.post(
        f"/chat/conversations/{conversation_id}/bot",
        json={"enabled": False},
    )
    assert toggle.status_code == 200

    resp = await client.post(
        "/chat/messages",
        json={"phone": "+1-300-0002", "content": "second"},
    )
    assert resp.status_code == 200
    assert resp.json()["bot_reply"] is None
    assert len(fake_graph.invocations) == 1


@pytest.mark.asyncio
async def test_manual_ai_message_uses_update_state(
    client: AsyncClient, fake_graph
) -> None:
    created = await client.post(
        "/chat/messages",
        json={"phone": "+1-300-0003", "customer_name": "Owner", "content": "hello"},
    )
    conversation_id = created.json()["conversation"]["id"]

    resp = await client.post(
        f"/chat/conversations/{conversation_id}/manual-ai",
        json={"content": "Custom owner reply"},
    )
    assert resp.status_code == 204
    assert len(fake_graph.updated_states) == 1
