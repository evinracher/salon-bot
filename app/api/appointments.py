from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.appointment import Appointment
from app.models.employee import Employee
from app.models.service import Service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    AppointmentUpdate,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _ensure_refs_exist(
    session: AsyncSession,
    employee_id: int,
    service_id: int,
) -> None:
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service not found"
        )


async def _has_conflict(
    session: AsyncSession,
    employee_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: int | None = None,
) -> bool:
    stmt = select(Appointment.id).where(
        Appointment.employee_id == employee_id,
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    return (await session.scalar(stmt.limit(1))) is not None


def _validate_time_window(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be after start_time",
        )


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    session: SessionDep,
) -> Appointment:
    await _ensure_refs_exist(session, body.employee_id, body.service_id)

    if body.status != AppointmentStatus.CANCELLED:
        has_conflict = await _has_conflict(
            session,
            body.employee_id,
            body.start_time,
            body.end_time,
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment overlaps existing booking for this employee",
            )

    payload = body.model_dump()
    payload["status"] = body.status.value
    appointment = Appointment(**payload)
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
async def list_appointments(
    session: SessionDep,
    employee_id: int | None = Query(default=None, gt=0),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
) -> list[Appointment]:
    stmt: Select[tuple[Appointment]] = select(Appointment)
    if employee_id is not None:
        stmt = stmt.where(Appointment.employee_id == employee_id)
    if status_filter is not None:
        stmt = stmt.where(Appointment.status == status_filter.value)
    if from_time is not None:
        stmt = stmt.where(Appointment.start_time >= from_time)
    if to_time is not None:
        stmt = stmt.where(Appointment.start_time <= to_time)

    result = await session.scalars(
        stmt.order_by(Appointment.start_time, Appointment.id)
    )
    return list(result.all())


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(appointment_id: int, session: SessionDep) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    session: SessionDep,
) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    payload = body.model_dump(exclude_unset=True)
    target_employee_id = payload.get("employee_id", appointment.employee_id)
    target_service_id = payload.get("service_id", appointment.service_id)
    target_start_time = payload.get("start_time", appointment.start_time)
    target_end_time = payload.get("end_time", appointment.end_time)
    target_status = payload.get("status", AppointmentStatus(appointment.status))

    _validate_time_window(target_start_time, target_end_time)
    await _ensure_refs_exist(session, target_employee_id, target_service_id)

    if target_status != AppointmentStatus.CANCELLED:
        has_conflict = await _has_conflict(
            session,
            target_employee_id,
            target_start_time,
            target_end_time,
            exclude_id=appointment_id,
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment overlaps existing booking for this employee",
            )

    for key, value in payload.items():
        setattr(
            appointment,
            key,
            value.value if isinstance(value, AppointmentStatus) else value,
        )

    await session.commit()
    await session.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(appointment_id: int, session: SessionDep) -> None:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(appointment)
    await session.commit()
