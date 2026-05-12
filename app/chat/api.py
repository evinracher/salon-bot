from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.runner import inject_manual_ai_message
from app.chat.deps import ensure_chat_available, get_compiled_graph
from app.chat.orchestration import process_inbound_chat_turn
from app.chat.schemas import (
    BotToggle,
    ChatPostResponse,
    ConversationRead,
    ManualAIMessageCreate,
    MessageCreate,
)
from app.chat.service import (
    get_conversation,
    set_bot_enabled,
)
from app.db import get_session

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(ensure_chat_available)],
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("/messages", response_model=ChatPostResponse)
async def post_message(
    body: MessageCreate,
    session: SessionDep,
    graph=Depends(get_compiled_graph),
) -> ChatPostResponse:
    turn = await process_inbound_chat_turn(
        graph=graph,
        session=session,
        phone=body.phone,
        content=body.content,
        customer_name=body.customer_name,
    )
    conversation_read = ConversationRead.model_validate(turn.conversation)
    return ChatPostResponse(conversation=conversation_read, bot_reply=turn.bot_reply)


@router.post("/conversations/{conversation_id}/bot", response_model=ConversationRead)
async def toggle_bot(
    conversation_id: int,
    body: BotToggle,
    session: SessionDep,
) -> ConversationRead:
    conversation = await set_bot_enabled(session, conversation_id, body.enabled)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return ConversationRead.model_validate(conversation)


@router.post("/conversations/{conversation_id}/manual-ai", status_code=status.HTTP_204_NO_CONTENT)
async def manual_ai_message(
    conversation_id: int,
    body: ManualAIMessageCreate,
    session: SessionDep,
    graph=Depends(get_compiled_graph),
) -> None:
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await inject_manual_ai_message(
        graph=graph,
        conversation_id=conversation.id,
        content=body.content,
    )
