"""Appointment booking orchestration (HTTP-agnostic)."""

from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appointment import Appointment
from app.models.employee import Employee
from app.models.service import Service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentStatus,
    AppointmentUpdate,
)
from app.services.datetime_utils import (
    is_future_in_reference_tz,
    is_slot_boundary_in_timezone,
    is_slot_duration_aligned,
)


class AppointmentServiceError(Exception):
    """Raised when an appointment operation is invalid."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def _ensure_refs_exist(
    session: AsyncSession,
    employee_id: int,
    service_id: int,
) -> None:
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise AppointmentServiceError(404, "Employee not found")
    service = await session.get(Service, service_id)
    if service is None:
        raise AppointmentServiceError(404, "Service not found")


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
        raise AppointmentServiceError(422, "end_time must be after start_time")


def _validate_future_start_time(start_time: datetime) -> None:
    if not is_future_in_reference_tz(start_time):
        raise AppointmentServiceError(422, "start_time must be in the future")


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
        raise AppointmentServiceError(
            422,
            (
                "Appointment times must align to slot interval "
                f"({interval} minutes) in {settings.timezone}"
            ),
        )


async def create_appointment(
    session: AsyncSession, body: AppointmentCreate
) -> Appointment:
    await _ensure_refs_exist(session, body.employee_id, body.service_id)
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
            raise AppointmentServiceError(
                409,
                "Appointment overlaps existing booking for this employee",
            )

    payload = body.model_dump()
    payload["status"] = body.status.value
    appointment = Appointment(**payload)
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


async def list_appointments(
    session: AsyncSession,
    *,
    employee_id: int | None = None,
    status_filter: AppointmentStatus | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
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


async def get_appointment(
    session: AsyncSession, appointment_id: int
) -> Appointment | None:
    return await session.get(Appointment, appointment_id)


async def list_appointments_by_phone(
    session: AsyncSession, phone: str
) -> list[Appointment]:
    stmt = (
        select(Appointment)
        .where(Appointment.client_phone == phone)
        .order_by(Appointment.start_time.desc(), Appointment.id.desc())
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def update_appointment(
    session: AsyncSession, appointment_id: int, body: AppointmentUpdate
) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentServiceError(404, "Not found")

    payload = body.model_dump(exclude_unset=True)
    target_employee_id = payload.get("employee_id", appointment.employee_id)
    target_service_id = payload.get("service_id", appointment.service_id)
    target_start_time = payload.get("start_time", appointment.start_time)
    target_end_time = payload.get("end_time", appointment.end_time)
    target_status = payload.get("status", AppointmentStatus(appointment.status))

    _validate_time_window(target_start_time, target_end_time)
    _validate_slot_alignment(target_start_time, target_end_time)
    _validate_future_start_time(target_start_time)
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
            raise AppointmentServiceError(
                409,
                "Appointment overlaps existing booking for this employee",
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


async def delete_appointment(session: AsyncSession, appointment_id: int) -> None:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise AppointmentServiceError(404, "Not found")
    await session.delete(appointment)
    await session.commit()
