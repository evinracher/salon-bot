import pytest
from httpx import AsyncClient

from app.config import settings


@pytest.mark.asyncio
async def test_whatsapp_verify_returns_challenge(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "whatsapp_verify_token", "my-token")
    resp = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my-token",
            "hub.challenge": "challenge-text-123",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge-text-123"


@pytest.mark.asyncio
async def test_whatsapp_verify_rejects_bad_token(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "whatsapp_verify_token", "my-token")
    resp = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "x",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_whatsapp_post_enqueues_and_returns_200(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict] = []

    async def fake_enqueue(app, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)

    monkeypatch.setattr(
        "app.chat.whatsapp_api.enqueue_whatsapp_inbound",
        fake_enqueue,
    )

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [
                                {
                                    "wa_id": "15551234567",
                                    "profile": {"name": "Bob"},
                                },
                            ],
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.test1",
                                    "type": "text",
                                    "text": {"body": "Hello bot"},
                                },
                            ],
                        },
                    },
                ],
            },
        ],
    }
    resp = await client.post("/webhooks/whatsapp", json=payload)
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["wa_id"] == "15551234567"
    assert calls[0]["text"] == "Hello bot"
    assert calls[0]["profile_name"] == "Bob"
    assert calls[0]["message_id"] == "wamid.test1"


@pytest.mark.asyncio
async def test_whatsapp_post_invalid_json_still_200(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/webhooks/whatsapp",
        content=b"not-json{",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
