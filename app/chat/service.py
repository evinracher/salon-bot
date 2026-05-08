from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.models.conversation import Conversation
from app.models.customer import Customer


async def get_or_create_customer_by_phone(
    session: AsyncSession,
    phone: str,
    customer_name: str | None = None,
) -> Customer:
    customer = await session.scalar(select(Customer).where(Customer.phone == phone))
    if customer is not None:
        if customer_name and customer.name != customer_name:
            customer.name = customer_name
            await session.commit()
            await session.refresh(customer)
        return customer

    customer = Customer(name=customer_name or "Customer", phone=phone)
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    return customer


async def get_or_create_conversation_by_phone(
    session: AsyncSession,
    phone: str,
    customer_name: str | None = None,
) -> Conversation:
    customer = await get_or_create_customer_by_phone(session, phone, customer_name)
    conversation = await session.scalar(
        select(Conversation).where(Conversation.customer_id == customer.id)
    )
    if conversation is not None:
        return conversation

    conversation = Conversation(customer_id=customer.id, bot_enabled=True)
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation(
    session: AsyncSession, conversation_id: int
) -> Conversation | None:
    return await session.get(Conversation, conversation_id)


async def set_bot_enabled(
    session: AsyncSession, conversation_id: int, enabled: bool
) -> Conversation | None:
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None:
        return None
    conversation.bot_enabled = enabled
    await session.commit()
    await session.refresh(conversation)
    return conversation
