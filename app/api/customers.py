from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _phone_taken(
    session: AsyncSession, phone: str, *, exclude_customer_id: int | None = None
) -> bool:
    stmt = select(Customer.id).where(Customer.phone == phone)
    if exclude_customer_id is not None:
        stmt = stmt.where(Customer.id != exclude_customer_id)
    return (await session.scalar(stmt)) is not None


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
async def create_customer(body: CustomerCreate, session: SessionDep) -> Customer:
    if await _phone_taken(session, body.phone):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer phone already exists",
        )
    customer = Customer(name=body.name, phone=body.phone, notes=body.notes)
    session.add(customer)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer phone already exists",
        ) from exc
    await session.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerRead])
async def list_customers(session: SessionDep) -> list[Customer]:
    result = await session.scalars(select(Customer).order_by(Customer.id))
    return list(result.all())


@router.get("/{customer_id}", response_model=CustomerRead)
async def get_customer(customer_id: int, session: SessionDep) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return customer


@router.patch("/{customer_id}", response_model=CustomerRead)
async def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    session: SessionDep,
) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    payload = body.model_dump(exclude_unset=True)
    new_phone = payload.get("phone")
    if isinstance(new_phone, str) and await _phone_taken(
        session, new_phone, exclude_customer_id=customer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer phone already exists",
        )

    for key, value in payload.items():
        setattr(customer, key, value)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer phone already exists",
        ) from exc
    await session.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(customer_id: int, session: SessionDep) -> None:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        await session.delete(customer)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete customer referenced by appointments",
        ) from exc
