from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import AsyncClient
from langchain_core.messages import AIMessage

from app.main import app


class FakeGraph:
    def __init__(self) -> None:
        self.invocations: list[dict] = []
        self.updated_states: list[dict] = []

    async def ainvoke(self, values: dict, config: dict) -> dict:
        self.invocations.append({"values": values, "config": config})
        return {"messages": [AIMessage(content="ok")]}

    async def aupdate_state(self, config: dict, values: dict) -> None:
        self.updated_states.append({"config": config, "values": values})


@pytest_asyncio.fixture
async def fake_graph(client: AsyncClient) -> AsyncIterator[FakeGraph]:
    _ = client
    graph = FakeGraph()
    app.state.chat_graph = graph
    app.state.chat_available = True
    yield graph
