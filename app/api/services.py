from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def create_service(body: ServiceCreate, session: SessionDep) -> Service:
    service = Service(**body.model_dump())
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service


@router.get("", response_model=list[ServiceRead])
async def list_services(session: SessionDep) -> list[Service]:
    result = await session.scalars(select(Service).order_by(Service.id))
    return list(result.all())


@router.get("/{service_id}", response_model=ServiceRead)
async def get_service(service_id: int, session: SessionDep) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return service


@router.patch("/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: int,
    body: ServiceUpdate,
    session: SessionDep,
) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(service, key, value)

    await session.commit()
    await session.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(service_id: int, session: SessionDep) -> None:
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(service)
    await session.commit()
