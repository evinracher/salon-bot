from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.chat.agent.runner import run_turn
from app.chat.deps import ensure_chat_available, get_compiled_graph
from app.chat.models.conversation import Conversation
from app.chat.models.message import Message, MessageRole
from app.chat.schemas import (
    BotToggle,
    ChatPostResponse,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from app.chat.service import (
    apply_manager_pause,
    append_message,
    get_or_create_conversation,
    is_bot_active,
    recent_messages,
    set_bot_enabled,
)
from app.config import settings
from app.db import get_session

router = APIRouter(
    prefix="/chat", tags=["chat"], dependencies=[Depends(ensure_chat_available)]
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]
logger = structlog.get_logger(__name__)


@router.post("/messages", response_model=ChatPostResponse)
async def post_message(
    body: MessageCreate,
    request: Request,
    session: SessionDep,
) -> ChatPostResponse:
    conversation = await get_or_create_conversation(
        session, body.phone, customer_name=body.customer_name
    )
    _, accepted = await append_message(
        session,
        phone=body.phone,
        role=body.role,
        content=body.content,
        provider_message_id=body.provider_message_id,
    )

    bot_reply: str | None = None
    if body.role == MessageRole.MANAGER:
        conversation = await apply_manager_pause(
            session,
            phone=body.phone,
            minutes=settings.chat_manager_pause_minutes,
        )
    elif body.role == MessageRole.CUSTOMER and is_bot_active(conversation):
        graph = get_compiled_graph(request)
        try:
            bot_reply = await run_turn(
                graph=graph,
                session=session,
                phone=body.phone,
                customer_name=conversation.customer_name,
                user_text=body.content,
            )
        except Exception:
            logger.exception("chat_agent_failure", phone=body.phone)
            raise HTTPException(
                status_code=500,
                detail="chat agent failed to process message",
            ) from None

    return ChatPostResponse(
        conversation=ConversationRead.model_validate(conversation),
        accepted_message=MessageRead.model_validate(accepted),
        bot_reply=bot_reply,
    )


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(session: SessionDep) -> list[Conversation]:
    result = await session.scalars(
        select(Conversation).order_by(
            Conversation.last_message_at.desc(), Conversation.phone
        )
    )
    return list(result.all())


@router.get("/conversations/{phone}", response_model=ConversationRead)
async def get_conversation(phone: str, session: SessionDep) -> Conversation:
    row = await session.get(Conversation, phone)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return row


@router.get("/conversations/{phone}/messages", response_model=list[MessageRead])
async def get_messages(phone: str, session: SessionDep) -> list[Message]:
    return await recent_messages(session, phone=phone, limit=500)


@router.post("/conversations/{phone}/bot", response_model=ConversationRead)
async def toggle_bot(phone: str, body: BotToggle, session: SessionDep) -> Conversation:
    pause_minutes = body.pause_minutes if body.enabled else None
    return await set_bot_enabled(
        session=session, phone=phone, enabled=body.enabled, pause_minutes=pause_minutes
    )
