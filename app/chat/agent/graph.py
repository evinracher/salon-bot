from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import SecretStr

from app.chat.agent.tools import ALL_TOOLS
from app.config import settings


def build_graph(checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
    api_key = SecretStr(settings.groq_api_key) if settings.groq_api_key else None
    model = ChatGroq(model=settings.groq_model, api_key=api_key)
    return create_react_agent(
        model=model,
        tools=ALL_TOOLS,
        checkpointer=checkpointer,
        debug=False,
    )


@asynccontextmanager
async def graph_with_checkpointer() -> AsyncIterator[
    tuple[CompiledStateGraph, AsyncPostgresSaver]
]:
    async with AsyncPostgresSaver.from_conn_string(
        settings.database_url
    ) as checkpointer:
        await checkpointer.setup()
        graph = build_graph(checkpointer)
        yield graph, checkpointer
