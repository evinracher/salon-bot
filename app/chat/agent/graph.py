import json
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

import groq
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command
from pydantic import SecretStr

from app.chat.agent.message_repair import ensure_tool_call_responses
from app.chat.agent.protocols import CompiledSalonAgent
from app.chat.agent.state import SalonState
from app.chat.agent.tools import ALL_TOOLS
from app.config import settings


def _coerce_tool_message_content(msg: ToolMessage) -> ToolMessage:
    """Groq rejects empty tool strings; non-strings must be JSON text."""
    c = msg.content
    if isinstance(c, str) and not c:
        return msg.model_copy(update={"content": "{}"})
    if isinstance(c, str):
        return msg
    return msg.model_copy(update={"content": json.dumps(c, default=str)})


def _build_groq_chat_model() -> BaseChatModel:
    """Primary ChatGroq plus optional fallbacks when Groq returns rate limits (429)."""
    api_key = SecretStr(settings.groq_api_key) if settings.groq_api_key else None
    primary = ChatGroq(
        api_key=api_key,
        model_name=settings.groq_model,
        temperature=0,
    )
    names = settings.groq_fallback_model_names
    if not names:
        return primary

    fallbacks = [
        ChatGroq(api_key=api_key, model_name=name, temperature=0) for name in names
    ]
    return cast(
        BaseChatModel,
        primary.with_fallbacks(
            fallbacks,
            exceptions_to_handle=(groq.RateLimitError,),
        ),
    )


def _build_openai_chat_model() -> BaseChatModel:
    api_key = SecretStr(settings.openai_api_key) if settings.openai_api_key else None
    return ChatOpenAI(
        api_key=api_key,
        model=settings.openai_model,
        temperature=0,
    )


def build_chat_model() -> BaseChatModel:
    """Chat model for the agent: Groq or OpenAI, from ``settings.chat_llm_provider``."""
    provider = (settings.chat_llm_provider or "groq").strip().lower()
    if provider == "openai":
        return _build_openai_chat_model()
    if provider == "groq":
        return _build_groq_chat_model()
    msg = (
        f"Unsupported chat_llm_provider={settings.chat_llm_provider!r}; "
        "use 'groq' or 'openai'"
    )
    raise ValueError(msg)


class SanitizeToolMessagesMiddleware(AgentMiddleware[AgentState[Any], None, Any]):
    """Normalize tool payloads; pad missing tool replies (OpenAI requires every call id)."""

    state_schema = SalonState
    tools: Sequence[BaseTool] = ()

    async def awrap_model_call(
        self,
        request: ModelRequest[None],
        handler: Callable[[ModelRequest[None]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any] | AIMessage:
        raw: list[AnyMessage] = list(request.state.get("messages") or [])
        fixed = [
            _coerce_tool_message_content(m) if isinstance(m, ToolMessage) else m
            for m in raw
        ]
        fixed = ensure_tool_call_responses(fixed)
        return await handler(request.override(messages=fixed))


class SafeToolErrorResponseMiddleware(AgentMiddleware):
    """Return structured JSON tool errors instead of failing the whole turn."""

    tools: Sequence[BaseTool] = ()

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:
        try:
            return await handler(request)
        except Exception as exc:
            tool_call_id = request.tool_call.get("id", "")
            tool_name = request.tool_call.get("name", "")
            error_payload = {
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                }
            }
            return ToolMessage(
                content=json.dumps(error_payload, default=str),
                name=tool_name,
                tool_call_id=tool_call_id,
                status="error",
            )


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
async def graph_with_checkpointer() -> AsyncIterator[
    tuple[CompiledSalonAgent, AsyncPostgresSaver]
]:
    conn_string = _langgraph_postgres_conn_string(settings.database_url)
    async with AsyncPostgresSaver.from_conn_string(conn_string) as checkpointer:
        await checkpointer.setup()
        model = build_chat_model()
        graph = create_agent(
            model=model,
            tools=ALL_TOOLS,
            state_schema=SalonState,
            checkpointer=checkpointer,
            middleware=[
                SanitizeToolMessagesMiddleware(),
                SafeToolErrorResponseMiddleware(),
            ],
        )
        yield cast(CompiledSalonAgent, graph), checkpointer
