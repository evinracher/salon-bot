from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.service import Service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    AppointmentUpdate,
)
from app.services.datetime_utils import (
    ensure_aware_in_timezone,
    is_future_in_reference_tz,
    is_slot_boundary_in_timezone,
    is_slot_duration_aligned,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _ensure_refs_exist(
    session: AsyncSession,
    customer_id: int,
    employee_id: int,
    service_id: int,
) -> None:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")


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
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_time must be after start_time",
        )


def _validate_future_start_time(start_time: datetime) -> None:
    if not is_future_in_reference_tz(start_time, reference_timezone_name=settings.timezone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time must be in the future",
        )


def _validate_slot_alignment(start_time: datetime, end_time: datetime) -> None:
    interval = settings.slot_interval_minutes

    aligned_start = is_slot_boundary_in_timezone(
        value=start_time,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_end = is_slot_boundary_in_timezone(
        value=end_time,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_duration = is_slot_duration_aligned(
        start=start_time,
        end=end_time,
        interval_minutes=interval,
    )

    if not (aligned_start and aligned_end and aligned_duration):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Appointment times must align to slot interval "
                f"({interval} minutes) in {settings.timezone}"
            ),
        )


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    session: SessionDep,
) -> Appointment:
    body = body.model_copy(
        update={
            "start_time": ensure_aware_in_timezone(body.start_time, settings.timezone),
            "end_time": ensure_aware_in_timezone(body.end_time, settings.timezone),
        }
    )
    await _ensure_refs_exist(session, body.customer_id, body.employee_id, body.service_id)
    _validate_slot_alignment(body.start_time, body.end_time)
    _validate_future_start_time(body.start_time)

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
        from_bound = ensure_aware_in_timezone(from_time, settings.timezone)
        stmt = stmt.where(Appointment.start_time >= from_bound)
    if to_time is not None:
        to_bound = ensure_aware_in_timezone(to_time, settings.timezone)
        stmt = stmt.where(Appointment.start_time <= to_bound)

    result = await session.scalars(stmt.order_by(Appointment.start_time, Appointment.id))
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
    target_customer_id = payload.get("customer_id", appointment.customer_id)
    target_start_time = ensure_aware_in_timezone(
        payload.get("start_time", appointment.start_time),
        settings.timezone,
    )
    target_end_time = ensure_aware_in_timezone(
        payload.get("end_time", appointment.end_time),
        settings.timezone,
    )
    target_status = payload.get("status", AppointmentStatus(appointment.status))

    _validate_time_window(target_start_time, target_end_time)
    _validate_slot_alignment(target_start_time, target_end_time)
    _validate_future_start_time(target_start_time)
    await _ensure_refs_exist(
        session,
        target_customer_id,
        target_employee_id,
        target_service_id,
    )

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
        if key == "start_time":
            value = target_start_time
        elif key == "end_time":
            value = target_end_time
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
