from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.runner import inject_manual_ai_message, run_turn
from app.chat.deps import ensure_chat_available, get_compiled_graph
from app.chat.schemas import (
    BotToggle,
    ChatPostResponse,
    ConversationRead,
    CustomerCreate,
    CustomerRead,
    ManualAIMessageCreate,
    MessageCreate,
)
from app.chat.service import (
    get_conversation,
    get_or_create_conversation_by_phone,
    set_bot_enabled,
)
from app.db import get_session
from app.models.customer import Customer

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    dependencies=[Depends(ensure_chat_available)],
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]

customers_router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("/messages", response_model=ChatPostResponse)
async def post_message(
    body: MessageCreate,
    session: SessionDep,
    graph=Depends(get_compiled_graph),
) -> ChatPostResponse:
    conversation = await get_or_create_conversation_by_phone(
        session=session,
        phone=body.phone,
        customer_name=body.customer_name,
    )
    conversation_read = ConversationRead.model_validate(conversation)
    if not conversation.bot_enabled:
        return ChatPostResponse(conversation=conversation_read, bot_reply=None)

    bot_reply = await run_turn(
        graph=graph,
        conversation=conversation,
        content=body.content,
        session=session,
    )
    return ChatPostResponse(conversation=conversation_read, bot_reply=bot_reply)


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


@router.post(
    "/conversations/{conversation_id}/manual-ai", status_code=status.HTTP_204_NO_CONTENT
)
async def manual_ai_message(
    conversation_id: int,
    body: ManualAIMessageCreate,
    request: Request,
    session: SessionDep,
    graph=Depends(get_compiled_graph),
) -> None:
    conversation = await get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await inject_manual_ai_message(
        graph=graph,
        request=request,
        conversation_id=conversation.id,
        content=body.content,
    )


@customers_router.post(
    "", response_model=CustomerRead, status_code=status.HTTP_201_CREATED
)
async def create_customer(body: CustomerCreate, session: SessionDep) -> Customer:
    exists = await session.scalar(
        select(Customer.id).where(Customer.phone == body.phone)
    )
    if exists is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer phone already exists",
        )
    customer = Customer(name=body.name, phone=body.phone, notes=body.notes)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


@customers_router.get("", response_model=list[CustomerRead])
async def list_customers(session: SessionDep) -> list[Customer]:
    return list((await session.scalars(select(Customer).order_by(Customer.id))).all())
