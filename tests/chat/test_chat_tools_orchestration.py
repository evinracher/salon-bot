import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.chat.agent.runtime import current_session
from app.chat.agent.tools import check_availability
from app.chat.orchestration import process_inbound_chat_turn
from app.config import settings
from app.db import async_session_maker


def _availability_test_date() -> str:
    """Tomorrow in salon TZ so ``check_availability`` accepts the date."""
    today = datetime.now(ZoneInfo(settings.timezone)).date()
    return (today + timedelta(days=1)).isoformat()


@pytest.mark.asyncio
async def test_check_availability_tool_returns_grouped_dayparts(
    client: AsyncClient,
) -> None:
    employee = (
        await client.post(
            "/employees",
            json={"name": "ToolEmp", "phone": "+1-422-2222"},
        )
    ).json()
    service = (
        await client.post(
            "/services",
            json={
                "name": "ToolSvc",
                "duration_minutes": 30,
                "price": "35.00",
            },
        )
    ).json()
    link = await client.post(
        "/employee-services",
        json={"employee_id": employee["id"], "service_id": service["id"]},
    )
    assert link.status_code == 201

    async with async_session_maker() as session:
        token = current_session.set(session)
        try:
            raw = await check_availability.ainvoke(
                {
                    "service_id": service["id"],
                    "date_value": _availability_test_date(),
                },
            )
        finally:
            current_session.reset(token)

    payload = json.loads(raw)
    assert payload["service"]["name"] == "ToolSvc"
    grouped = payload["grouped"]
    assert "slots_by_daypart" in grouped
    assert grouped["daypart_labels"]["morning"] == "Mañana"


@pytest.mark.asyncio
async def test_orchestration_skips_graph_when_bot_disabled(
    client: AsyncClient,
    fake_graph,
) -> None:
    created = await client.post(
        "/chat/messages",
        json={
            "phone": "+1-500-0001",
            "customer_name": "Off",
            "content": "hello",
        },
    )
    conversation_id = created.json()["conversation"]["id"]
    await client.post(
        f"/chat/conversations/{conversation_id}/bot",
        json={"enabled": False},
    )
    before = len(fake_graph.invocations)

    async with async_session_maker() as session:
        turn = await process_inbound_chat_turn(
            graph=fake_graph,
            session=session,
            phone="+1-500-0001",
            content="second",
        )

    assert turn.bot_reply is None
    assert len(fake_graph.invocations) == before
