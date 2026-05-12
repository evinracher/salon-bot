"""Shared inbound chat turn: conversation upsert, bot gate, agent run."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.protocols import CompiledSalonAgent
from app.chat.agent.runner import run_turn
from app.chat.models.conversation import Conversation
from app.chat.service import get_or_create_conversation_by_phone


@dataclass(frozen=True)
class InboundChatTurnResult:
    conversation: Conversation
    """Bot reply text, or None when bot is disabled or reply is empty."""
    bot_reply: str | None


async def process_inbound_chat_turn(
    *,
    graph: CompiledSalonAgent,
    session: AsyncSession,
    phone: str,
    content: str,
    customer_name: str | None = None,
) -> InboundChatTurnResult:
    """
    Upsert customer/conversation, optionally run the agent.

    Used by the simulated HTTP chat endpoint and the WhatsApp worker so behavior
    stays aligned.
    """
    conversation = await get_or_create_conversation_by_phone(
        session=session,
        phone=phone,
        customer_name=customer_name,
    )
    if not conversation.bot_enabled:
        return InboundChatTurnResult(conversation=conversation, bot_reply=None)

    reply = await run_turn(
        graph=graph,
        conversation=conversation,
        content=content,
        session=session,
    )
    stripped = reply.strip() if reply else ""
    return InboundChatTurnResult(
        conversation=conversation,
        bot_reply=stripped if stripped else None,
    )
