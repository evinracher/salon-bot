"""Process WhatsApp inbound jobs: DB + agent turn + outbound reply."""

from __future__ import annotations

from typing import Any, cast

import structlog
from bullmq.job import Job
from fastapi import FastAPI

from app.chat.agent.protocols import CompiledSalonAgent
from app.chat.orchestration import process_inbound_chat_turn
from app.chat.whatsapp_client import send_whatsapp_text_message
from app.chat.whatsapp_schemas import normalize_customer_phone
from app.db import async_session_maker

logger = structlog.get_logger(__name__)


async def process_whatsapp_inbound_job(app: FastAPI, job_data: dict[str, Any]) -> None:
    """
    Upsert customer/conversation, run agent turn, send WhatsApp reply.

    Expected ``job_data`` keys: wa_id, text, optional profile_name, message_id.
    """
    wa_id = job_data.get("wa_id")
    text = job_data.get("text")
    profile_name = job_data.get("profile_name")
    message_id = job_data.get("message_id")

    if not isinstance(wa_id, str) or not isinstance(text, str):
        logger.warning("whatsapp_job_invalid_payload", job_data=job_data)
        return

    graph = getattr(app.state, "chat_graph", None)
    if graph is None or not getattr(app.state, "chat_available", False):
        logger.error("whatsapp_job_chat_unavailable")
        raise RuntimeError("Chat graph is not available")

    phone = normalize_customer_phone(wa_id)

    conversation_id: int | None = None
    async with async_session_maker() as session:
        turn = await process_inbound_chat_turn(
            graph=cast(CompiledSalonAgent, graph),
            session=session,
            phone=phone,
            content=text,
            customer_name=profile_name if isinstance(profile_name, str) else None,
        )
        conversation_id = turn.conversation.id
        if not turn.conversation.bot_enabled:
            logger.info(
                "whatsapp_skip_bot_disabled",
                conversation_id=turn.conversation.id,
                message_id=message_id,
            )
            return
        reply = turn.bot_reply

    if reply:
        await send_whatsapp_text_message(to_wa_id=wa_id, text=reply)
    else:
        logger.info(
            "whatsapp_empty_reply_skipped",
            conversation_id=conversation_id,
            message_id=message_id,
        )


async def bullmq_processor(app: FastAPI, job: Job, _token: str) -> None:
    """BullMQ worker callback."""
    await process_whatsapp_inbound_job(app, job.data)
