from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent
from pydantic import SecretStr

from app.chat.agent.state import SalonState
from app.chat.agent.tools import ALL_TOOLS
from app.config import settings


def _checkpointer_conn_string(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


@asynccontextmanager
async def graph_with_checkpointer() -> AsyncIterator[tuple[object, AsyncPostgresSaver]]:
    conn_string = _checkpointer_conn_string(settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        model = ChatGroq(
            api_key=SecretStr(settings.groq_api_key) if settings.groq_api_key else None,
            model=settings.groq_model,
            temperature=0,
        )
        graph = create_react_agent(
            model=model,
            tools=ALL_TOOLS,
            state_schema=SalonState,
            checkpointer=checkpointer,
        )
        yield graph, checkpointer
