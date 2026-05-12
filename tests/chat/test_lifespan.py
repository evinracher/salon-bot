from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI

from app.main import lifespan


@pytest.mark.asyncio
async def test_lifespan_initializes_chat_runtime(monkeypatch) -> None:
    called = {"entered": False}

    @asynccontextmanager
    async def fake_graph_ctx() -> AsyncIterator[tuple[object, object]]:
        called["entered"] = True
        yield object(), object()

    monkeypatch.setattr("app.chat.bootstrap.graph_with_checkpointer", fake_graph_ctx)
    app = FastAPI()
    async with lifespan(app):
        assert called["entered"] is True
        assert app.state.chat_available is True
