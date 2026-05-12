import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)

from app.chat.agent.graph import graph_with_checkpointer
from app.chat.api import customers_router, router as chat_router


@asynccontextmanager
async def chat_lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.chat_graph = None
    app.state.chat_checkpointer = None
    app.state.chat_available = False
    app.state.chat_init_error = None
    stack = AsyncExitStack()
    try:
        graph, checkpointer = await stack.enter_async_context(graph_with_checkpointer())
        app.state.chat_graph = graph
        app.state.chat_checkpointer = checkpointer
        app.state.chat_available = True
    except Exception as exc:
        app.state.chat_init_error = str(exc)
        logger.exception("chat_runtime_init_failed")
    yield
    await stack.aclose()


def register_chat_routers(app: FastAPI) -> None:
    app.include_router(customers_router)
    app.include_router(chat_router)
