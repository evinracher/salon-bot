import pytest
from httpx import AsyncClient

from app.chat.whatsapp_processor import process_whatsapp_inbound_job
from app.config import settings


@pytest.mark.asyncio
async def test_processor_runs_turn_and_sends_reply(
    client: AsyncClient,
    fake_graph,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = client
    sent: list[dict[str, str]] = []

    async def fake_send(*, to_wa_id: str, text: str) -> None:
        sent.append({"to_wa_id": to_wa_id, "text": text})

    monkeypatch.setattr(
        "app.chat.whatsapp_processor.send_whatsapp_text_message",
        fake_send,
    )
    monkeypatch.setattr(settings, "whatsapp_access_token", "token")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123456")

    from app.main import app

    await process_whatsapp_inbound_job(
        app,
        {
            "wa_id": "15559876543",
            "text": "Book a cut",
            "profile_name": "Alex",
            "message_id": "mid-1",
        },
    )

    assert len(fake_graph.invocations) == 1
    assert len(sent) == 1
    assert sent[0]["to_wa_id"] == "15559876543"
    assert sent[0]["text"] == "ok"


@pytest.mark.asyncio
async def test_processor_skips_agent_when_bot_disabled(
    client: AsyncClient,
    fake_graph,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, str]] = []

    async def fake_send(*, to_wa_id: str, text: str) -> None:
        sent.append({"to_wa_id": to_wa_id, "text": text})

    monkeypatch.setattr(
        "app.chat.whatsapp_processor.send_whatsapp_text_message",
        fake_send,
    )

    created = await client.post(
        "/chat/messages",
        json={
            "phone": "+15551110002",
            "customer_name": "Quiet",
            "content": "setup",
        },
    )
    conversation_id = created.json()["conversation"]["id"]
    await client.post(
        f"/chat/conversations/{conversation_id}/bot",
        json={"enabled": False},
    )

    invocations_before = len(fake_graph.invocations)

    from app.main import app

    await process_whatsapp_inbound_job(
        app,
        {
            "wa_id": "15551110002",
            "text": "Anyone there?",
            "profile_name": "Quiet",
            "message_id": "mid-2",
        },
    )

    assert len(fake_graph.invocations) == invocations_before
    assert sent == []
