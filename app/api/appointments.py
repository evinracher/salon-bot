from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.appointment import Appointment
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    AppointmentUpdate,
)
from app.services.appointments import (
    AppointmentServiceError,
    create_appointment as create_appointment_svc,
    delete_appointment as delete_appointment_svc,
    get_appointment as get_appointment_svc,
    list_appointments as list_appointments_svc,
    update_appointment as update_appointment_svc,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _http(exc: AppointmentServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    session: SessionDep,
) -> Appointment:
    try:
        return await create_appointment_svc(session, body)
    except AppointmentServiceError as e:
        raise _http(e) from e


@router.get("", response_model=list[AppointmentRead])
async def list_appointments(
    session: SessionDep,
    employee_id: int | None = Query(default=None, gt=0),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
) -> list[Appointment]:
    return await list_appointments_svc(
        session,
        employee_id=employee_id,
        status_filter=status_filter,
        from_time=from_time,
        to_time=to_time,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(appointment_id: int, session: SessionDep) -> Appointment:
    appointment = await get_appointment_svc(session, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    session: SessionDep,
) -> Appointment:
    try:
        return await update_appointment_svc(session, appointment_id, body)
    except AppointmentServiceError as e:
        raise _http(e) from e


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(appointment_id: int, session: SessionDep) -> None:
    try:
        await delete_appointment_svc(session, appointment_id)
    except AppointmentServiceError as e:
        raise _http(e) from e
