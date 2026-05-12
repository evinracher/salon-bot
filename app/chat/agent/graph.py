import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import SecretStr

from app.chat.agent.state import SalonState
from app.chat.agent.tools import ALL_TOOLS
from app.config import settings


@wrap_model_call(state_schema=SalonState) 
async def _groq_safe_messages_middleware(
    request: ModelRequest[None],
    handler: Callable[[ModelRequest[None]], Awaitable[ModelResponse[Any]]],
) -> ModelResponse[Any] | AIMessage:
    """Groq rejects tool messages whose content is not a non-empty string (e.g. []).
    Normalize only the message list passed to the model; checkpointed state is unchanged.
    """
    raw: list[AnyMessage] = list(request.state.get("messages") or [])
    fixed: list[AnyMessage] = []
    for m in raw:
        if isinstance(m, ToolMessage):
            c = m.content
            if isinstance(c, str):
                if len(c) == 0:
                    fixed.append(m.model_copy(update={"content": "{}"}))
                else:
                    fixed.append(m)
            else:
                fixed.append(
                    m.model_copy(update={"content": json.dumps(c, default=str)})
                )
        else:
            fixed.append(m)
    return await handler(request.override(messages=fixed))


def _langgraph_postgres_conn_string(database_url: str) -> str:
    """AsyncPostgresSaver expects a libpq URL (postgresql://), not SQLAlchemy async URL."""
    url = database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    # Match app/db.py: local Docker Postgres without SSL; libpq defaults differ from asyncpg.
    if ("127.0.0.1" in url or "localhost" in url) and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=disable"
    return url


@asynccontextmanager
async def graph_with_checkpointer() -> AsyncIterator[tuple[object, AsyncPostgresSaver]]:
    conn_string = _langgraph_postgres_conn_string(settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        model = ChatGroq(
            api_key=SecretStr(settings.groq_api_key) if settings.groq_api_key else None,
            model_name=settings.groq_model,
            temperature=0,
        )
        graph = create_agent(
            model=model,
            tools=ALL_TOOLS,
            state_schema=SalonState,
            checkpointer=checkpointer,
            middleware=[_groq_safe_messages_middleware],
        )
        yield graph, checkpointer
