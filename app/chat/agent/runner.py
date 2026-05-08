from fastapi import Request
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.runtime import current_session
from app.chat.models.conversation import Conversation


def _thread_config(conversation_id: int) -> dict:
    return {"configurable": {"thread_id": str(conversation_id)}}


async def run_turn(
    graph,
    conversation: Conversation,
    content: str,
    session: AsyncSession,
) -> str:
    token = current_session.set(session)
    try:
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=content)]},
            config=_thread_config(conversation.id),
        )
    finally:
        current_session.reset(token)

    messages = result.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage) and isinstance(message.content, str):
            return message.content
    return ""


async def inject_manual_ai_message(
    graph,
    request: Request,
    conversation_id: int,
    content: str,
) -> None:
    _ = request
    await graph.aupdate_state(
        config=_thread_config(conversation_id),
        values={"messages": [AIMessage(content=content)]},
    )
