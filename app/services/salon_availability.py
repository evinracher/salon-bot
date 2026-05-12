"""Shared availability slot computation for HTTP API and chat tools."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.appointment import Appointment
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.schemas.appointment import AppointmentStatus
from app.schemas.availability import AvailabilitySlot
from app.services.availability import (
    build_business_window,
    generate_candidate_slots,
    has_overlap,
)
from app.services.datetime_utils import normalize_to_second_in_timezone


async def compute_availability_slots(
    session: AsyncSession,
    *,
    service_id: int,
    date_value: date,
    employee_id: int | None,
    selected_duration_minutes: int,
) -> list[AvailabilitySlot]:
    """
    Return candidate slots for ``service_id`` on ``date_value``.

    When ``employee_id`` is set, only that employee is considered (must be linked to
    the service). Otherwise all employees linked to the service are considered per slot.
    """
    window = build_business_window(
        target_date=date_value,
        timezone_name=settings.timezone,
        open_time=settings.business_open_time,
        close_time=settings.business_close_time,
        business_days=settings.business_weekdays,
    )
    if window is None:
        return []
    open_dt, close_dt = window
    candidates = generate_candidate_slots(
        open_dt=open_dt,
        close_dt=close_dt,
        slot_interval_minutes=settings.slot_interval_minutes,
        service_duration_minutes=selected_duration_minutes,
    )
    if not candidates:
        return []

    if employee_id is not None:
        employee_ids = [employee_id]
    else:
        employee_ids = list(
            (
                await session.scalars(
                    select(EmployeeService.employee_id).where(
                        EmployeeService.service_id == service_id
                    )
                )
            ).all()
        )
    if not employee_ids:
        return []

    result = await session.execute(
        select(Appointment.employee_id, Appointment.start_time, Appointment.end_time).where(
            Appointment.employee_id.in_(employee_ids),
            Appointment.status != AppointmentStatus.CANCELLED.value,
            Appointment.start_time < close_dt,
            Appointment.end_time > open_dt,
        )
    )
    appointments_by_employee: dict[int, list[tuple[datetime, datetime]]] = {
        emp_id: [] for emp_id in employee_ids
    }
    for row_employee_id, row_start, row_end in result.all():
        appointments_by_employee[row_employee_id].append(
            (
                normalize_to_second_in_timezone(row_start, settings.timezone),
                normalize_to_second_in_timezone(row_end, settings.timezone),
            )
        )

    slots: list[AvailabilitySlot] = []
    for start, end in candidates:
        available_employee_ids = [
            candidate_employee_id
            for candidate_employee_id, appointments in appointments_by_employee.items()
            if not has_overlap(start=start, end=end, appointments=appointments)
        ]
        if available_employee_ids:
            slots.append(
                AvailabilitySlot(
                    start=start,
                    end=end,
                    employee_ids=sorted(available_employee_ids),
                )
            )
    return slots


async def resolve_service_duration_minutes(
    session: AsyncSession,
    *,
    service_id: int,
    duration_minutes: int | None,
) -> tuple[Service | None, int]:
    """Return service row and effective duration (override or service default)."""
    service = await session.get(Service, service_id)
    if service is None:
        return None, 0
    selected = duration_minutes if duration_minutes is not None else service.duration_minutes
    return service, selected
